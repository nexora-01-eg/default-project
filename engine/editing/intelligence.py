"""Phase 10 — professional editing intelligence (measurements + refinement).

Layered on the Phase 8 base EDL (never rewritten here): BASE EDL ->
INTELLIGENCE ANALYSIS -> REFINEMENT -> FINAL EDL + metadata.

Rules of this module:
  - Measurements only, except two documented refinements (UNSAFE revert,
    opt-in repetition removal). No rendering, no FFmpeg, no models, no
    network. `validate_edl` is imported from Phase 9 execution for
    invariant checking only — the render path is never touched.
  - Every non-trivial statement carries Evidence (8 fields, no vague reasons).
  - Confidence values are labeled rule confidences, never probabilities.
  - Conservative defaults: refinement only ever KEEPs more (safety net),
    unless repetition removal is explicitly enabled.
"""
from __future__ import annotations

import statistics
import time
from dataclasses import asdict
from pathlib import Path

from engine.analysis.fillers import filler_set, normalize_token
from engine.core import config as config_mod
from engine.core.logging_utils import log_event
from engine.core.models import (
    CutSafety,
    Evidence,
    IntelligenceReport,
    JumpCutCandidate,
    PacingMetrics,
    RepetitionCandidate,
    SceneSpeechMetrics,
)
from engine.core.pipeline import cache_key, cached, store
from engine.core.project_store import (
    load_project,
    mark_stage,
    project_dir,
    write_artifact,
)
from engine.editing.decisions import hash_analysis
from engine.rendering.execution import edl_hash, validate_edl

INTEL_VERSION = "1.0.0"
ENGINE_TAG = "phase10-1.0"

INTEL_KEYS = ("intel_safety_net", "intel_safety_mode",
              "intel_repetition_removal", "intel_repetition_min_words",
              "intel_min_keep_s", "intel_min_remove_s",
              "intel_enable_jumpcut", "intel_enable_pacing",
              "intel_enable_repetition", "intel_word_gap_s")


class IntelError(RuntimeError):
    pass


def resolve_intel_policy(overrides: dict | None = None) -> dict:
    cfg = config_mod.resolve(overrides=overrides)
    policy = {k: cfg[k] for k in INTEL_KEYS}
    if policy["intel_safety_mode"] not in ("conservative", "strict"):
        raise IntelError("intel_safety_mode must be conservative|strict")
    for key in ("intel_repetition_min_words",):
        try:
            policy[key] = int(policy[key])
        except (TypeError, ValueError):
            raise IntelError(f"policy {key} must be an integer") from None
    for key in ("intel_min_keep_s", "intel_min_remove_s", "intel_word_gap_s"):
        try:
            policy[key] = float(policy[key])
        except (TypeError, ValueError):
            raise IntelError(f"policy {key} must be a number") from None
    if policy["intel_repetition_min_words"] < 2:
        raise IntelError("intel_repetition_min_words must be >= 2")
    if policy["intel_min_keep_s"] < 0 or policy["intel_min_remove_s"] <= 0:
        raise IntelError("intel_min_keep_s >= 0 and intel_min_remove_s > 0 required")
    if policy["intel_word_gap_s"] <= 0:
        raise IntelError("intel_word_gap_s must be > 0")
    for key in ("intel_safety_net", "intel_repetition_removal",
                "intel_enable_jumpcut", "intel_enable_pacing",
                "intel_enable_repetition"):
        policy[key] = bool(policy[key])
    return policy


def _r6(x: float) -> float:
    return round(float(x), 6)


def _overlap(a_start: float, a_end: float, b_start: float, b_end: float) -> float:
    return min(a_end, b_end) - max(a_start, b_start)


def _ev(evidence_type: str, source: str, start: float, end: float,
        metric: str, value, threshold, explanation: str) -> Evidence:
    return Evidence(evidence_type=evidence_type, source=source,
                    start=_r6(start), end=_r6(end), metric=metric,
                    value=value, threshold=threshold, explanation=explanation)


_TERMINAL_PUNCT = (".", "?", "!", "…", "؟")


def _norm_words(transcript: dict) -> tuple[list[dict], set[str]]:
    """Flatten transcript words with filler flags. Returns (words, filler_hits)."""
    language = transcript.get("language", "") or ""
    supported = filler_set(language)
    words: list[dict] = []
    for seg in transcript.get("segments", []) or []:
        for w in seg.get("words", []) or []:
            try:
                ws, we = float(w["start"]), float(w["end"])
            except (KeyError, TypeError, ValueError):
                continue
            if not we > ws:
                continue
            text = str(w.get("word", ""))
            norm = normalize_token(text)
            if not norm:
                continue
            words.append({"word": text, "norm": norm, "start": ws, "end": we,
                          "segment_id": seg.get("id"),
                          "probability": float(w.get("probability", 0.0) or 0.0),
                          "is_filler": norm in supported,
                          "terminal": text.rstrip().endswith(_TERMINAL_PUNCT)})
    words.sort(key=lambda x: (x["start"], x["end"]))
    return words, supported


def _scene_list(scenes: dict) -> list[dict]:
    return sorted(scenes.get("scenes", []) or [], key=lambda s: (s["start"], s["end"]))


# ---------------- 4A-C: scene metrics ----------------

def scene_metrics(scenes: dict, words: list[dict]) -> tuple[list[SceneSpeechMetrics], float]:
    out: list[SceneSpeechMetrics] = []
    for sc in _scene_list(scenes):
        ss, se = float(sc["start"]), float(sc["end"])
        speech_s = sum(_overlap(ws["start"], ws["end"], ss, se)
                       for ws in words if _overlap(ws["start"], ws["end"], ss, se) > 0)
        dur = se - ss
        density = round(speech_s / dur, 4) if dur > 0 else 0.0
        wc = sum(1 for ws in words if ws["start"] >= ss and ws["end"] <= se)
        out.append(SceneSpeechMetrics(scene_id=int(sc.get("scene_id", -1)),
                                      start=ss, end=se, duration=round(dur, 6),
                                      speech_duration=round(speech_s, 6),
                                      speech_density=density, word_count=wc))
    durations = [m.duration for m in out]
    median = round(statistics.median(durations), 6) if durations else 0.0
    for m in out:  # flags only — never deletions
        if median > 0 and m.duration > 2.0 * median:
            m.duration_outlier = "long"
        elif median > 0 and m.duration < 0.5 * median:
            m.duration_outlier = "short"
    return out, median


# ---------------- 4D/8: continuity + preferred points ----------------

def continuity(scenes: dict, words: list[dict], window: float = 1.0) -> list[dict]:
    result = []
    bounds = _scene_list(scenes)
    for left, right in zip(bounds, bounds[1:]):
        b = float(right["start"])
        before = [w for w in words if b - window <= w["end"] <= b]
        after = [w for w in words if b < w["start"] <= b + window]
        continues = bool(before and after) and not before[-1]["terminal"]
        result.append({"boundary": b,
                       "scene_before": left.get("scene_id"), "scene_after": right.get("scene_id"),
                       "words_before": [{"word": w["word"], "start": w["start"], "end": w["end"]}
                                        for w in before],
                       "words_after": [{"word": w["word"], "start": w["start"], "end": w["end"]}
                                       for w in after],
                       "continues_likely": continues,
                       "sentence_terminated": bool(before) and before[-1]["terminal"]})
    return result


def sentence_signals(words: list[dict]) -> dict:
    total = len(words)
    punct = sum(1 for w in words if w["terminal"])
    return {"total_words": total, "punctuated_words": punct,
            "coverage": round(punct / total, 4) if total else 0.0,
            "limitation": ("Whisper word tokens rarely carry sentence punctuation; "
                           "sentence-boundary inference is heuristic. Cut placement "
                           "prefers word gaps, silence, and scene boundaries instead.")}


def preferred_points(words: list[dict], silences: list[dict], scenes: dict,
                     gap_min: float) -> list[dict]:
    """Rank safer cut points. Scores are ordinal preferences, not probabilities."""
    points: list[dict] = []
    for a, b in zip(words, words[1:]):
        gap = b["start"] - a["end"]
        if gap >= gap_min:
            points.append({"start": _r6(a["end"]), "end": _r6(b["start"]),
                           "kind": "word_gap",
                           "score": round(min(1.0, 0.3 + gap), 3)})
    for sc in _scene_list(scenes)[1:]:
        b = float(sc["start"])
        in_silence = any(s["start"] - 1e-6 <= b <= s["end"] + 1e-6 for s in silences)
        in_gap = any(p["start"] - 1e-6 <= b <= p["end"] + 1e-6 for p in points)
        score = 1.0 if (in_silence or in_gap) else 0.6
        points.append({"start": _r6(b), "end": _r6(b), "kind": "scene_boundary",
                       "score": score})
    points.sort(key=lambda p: (p["start"], p["end"]))
    return points


# ---------------- 6: pacing ----------------

def pacing_metrics(scenes: dict, words: list[dict], silences: list[dict],
                   duration: float) -> PacingMetrics:
    bounds = _scene_list(scenes)
    durs = [float(s["end"]) - float(s["start"]) for s in bounds]
    minutes = duration / 60.0 if duration > 0 else 0.0
    speech_s = sum(w["end"] - w["start"] for w in words)
    return PacingMetrics(
        scene_count=len(bounds),
        avg_shot_duration=round(sum(durs) / len(durs), 3) if durs else 0.0,
        median_shot_duration=round(statistics.median(durs), 3) if durs else 0.0,
        scene_changes_per_min=round(max(0, len(bounds) - 1) / minutes, 3) if minutes else 0.0,
        words_per_min=round(len(words) / (speech_s / 60.0), 2) if speech_s > 0 else 0.0,
        pauses_per_min=round(len(silences) / minutes, 3) if minutes else 0.0,
        avg_pause_duration=round(sum(s["duration"] for s in silences) / len(silences), 3)
        if silences else 0.0)


# ---------------- 7: repetition ----------------

def repetition_candidates(words: list[dict], min_words: int) -> list[RepetitionCandidate]:
    """Maximal exact repeats over normalized content tokens (fillers dropped,
    positions kept). O(n^2) worst case; transcripts are small. Similarity is
    1.0 by construction (exact match only) — no fuzzy invention."""
    toks = [(w["norm"], w) for w in words if not w["is_filler"]]
    n = len(toks)
    seen: set[tuple] = set()
    out: list[RepetitionCandidate] = []
    for i in range(n):
        for j in range(i + 1, n):
            if toks[i][0] != toks[j][0]:
                continue
            length = 0
            while (i + length < n and j + length < n
                   and toks[i + length][0] == toks[j + length][0]
                   and (i + length) < j):  # non-overlapping occurrences
                length += 1
            if length < min_words or (i, j, length) in seen:
                continue
            # Maximality: not extendable backward, not contained in a longer hit.
            if i > 0 and j > 0 and toks[i - 1][0] == toks[j - 1][0]:
                continue
            key = (i, j, length)
            seen.add(key)
            text = " ".join(toks[i + k][0] for k in range(length))
            spans = [{"start": _r6(toks[i][1]["start"]),
                      "end": _r6(toks[i + length - 1][1]["end"]),
                      "segment_id": toks[i][1]["segment_id"]},
                     {"start": _r6(toks[j][1]["start"]),
                      "end": _r6(toks[j + length - 1][1]["end"]),
                      "segment_id": toks[j][1]["segment_id"]}]
            occ = (spans[0]["start"], spans[0]["end"], spans[1]["start"], spans[1]["end"])
            ev = [_ev("repetition_match", "transcript", occ[0], occ[3],
                      "matched_words", length, min_words,
                      f"exact {length}-word repeat at {occ[0]:.2f}s and {occ[2]:.2f}s")]
            out.append(RepetitionCandidate(text=text, spans=spans, similarity=1.0,
                                           confidence=0.6, evidence=ev))
    out.sort(key=lambda c: c.spans[0]["start"])
    return out


# ---------------- 4E: cut safety ----------------

def assess_removal(start: float, end: float, decision_id: str, ctx: dict) -> CutSafety:
    """Technical safety only: SAFE | CAUTION | UNSAFE with per-check evidence."""
    words: list[dict] = ctx["words"]
    refs: set[tuple] = ctx.get("referenced_fillers", set())
    supported: set[str] = ctx.get("filler_set", set())
    scenes: list[dict] = ctx.get("scenes", [])
    neighbors: list[dict] = ctx.get("neighbors", [])
    min_keep: float = ctx.get("min_keep", 0.5)
    min_remove: float = ctx.get("min_remove", 0.2)
    punctuated: bool = ctx.get("punctuated", False)
    evidence: list[Evidence] = []
    level = 0  # 0 SAFE, 1 CAUTION, 2 UNSAFE

    def flag(new_level: int, ev: Evidence):
        nonlocal level
        evidence.append(ev)
        level = max(level, new_level)

    for w in words:
        ov = _overlap(start, end, w["start"], w["end"])
        if ov <= 1e-6:
            continue
        key = (w.get("segment_id"), w["norm"], round(w["start"], 3))
        if not w["is_filler"]:
            flag(2, _ev("word_overlap", "transcript", max(start, w["start"]),
                        min(end, w["end"]), "overlap_s", round(ov, 3), 0.0,
                        f"removal overlaps meaningful word {w['word']!r}"))
        elif key not in refs:
            flag(1, _ev("filler_overlap_unplanned", "transcript",
                        max(start, w["start"]), min(end, w["end"]),
                        "overlap_s", round(ov, 3), 0.0,
                        f"removal touches unreferenced filler {w['word']!r}"))
    # Scene crossing (base engine pre-splits; flag any inconsistency).
    containing = [s for s in scenes
                  if float(s["start"]) - 1e-6 <= start and end <= float(s["end"]) + 1e-6]
    if not containing:
        flag(2, _ev("scene_crossing", "scenes", start, end, "contained", False, True,
                    "removal is not contained in a single scene"))
    # Tight padding to neighboring speech.
    gaps = [w["start"] - end for w in words if w["start"] >= end - 1e-6]
    gaps += [start - w["end"] for w in words if w["end"] <= start + 1e-6]
    if gaps:
        nearest = min(g for g in gaps if g >= -1e-6)
        if 0 <= nearest < 0.05:
            flag(1, _ev("tight_padding", "transcript", start, end,
                        "nearest_word_gap_s", round(nearest, 3), 0.05,
                        "cut lands within 50 ms of a word edge"))
    # Sentence split (only when punctuation signals exist at all).
    if punctuated:
        prev = [w for w in words if w["end"] <= start + 1e-6]
        nxt = [w for w in words if w["start"] >= end - 1e-6]
        if (prev and nxt and not prev[-1]["terminal"]
                and (nxt[0]["start"] - prev[-1]["end"]) < 1.0
                and not prev[-1]["is_filler"] and not nxt[0]["is_filler"]):
            flag(1, _ev("sentence_split", "transcript", start, end,
                        "split_inside_sentence", True, False,
                        f"removal sits inside a sentence ({prev[-1]['word']!r}…{nxt[0]['word']!r})"))
    for nb in neighbors:
        if nb.get("action") == "KEEP":
            dur = float(nb["end"]) - float(nb["start"])
            if dur < min_keep - 1e-6:
                flag(1, _ev("short_keep", "edl", float(nb["start"]), float(nb["end"]),
                            "keep_duration_s", round(dur, 3), min_keep,
                            "neighboring keep is shorter than minimum"))
    if (end - start) < min_remove - 1e-6:
        flag(2, _ev("short_removal", "edl", start, end,
                    "removal_duration_s", round(end - start, 3), min_remove,
                    "removal shorter than minimum (engine inconsistency)"))
    checks_run = 5 + (1 if punctuated else 0)
    if not evidence:
        # A clean verdict still records what was checked: traceability
        # applies to non-trivial decisions, not only to flagged ones.
        evidence.append(_ev("safety_summary", "edl", start, end,
                            "checks_passed", checks_run, checks_run,
                            f"{checks_run}/{checks_run} safety checks passed"))
    return CutSafety(decision_id=decision_id, start=_r6(start), end=_r6(end),
                     status=("SAFE", "CAUTION", "UNSAFE")[level], evidence=evidence)


# ---------------- 5: jump cuts ----------------

def jump_cut_candidates(decisions: list[dict]) -> list[JumpCutCandidate]:
    """A removal between two same-scene KEEPs likely breaks visual continuity.
    Cross-scene gaps are natural cuts, not jump cuts. Metadata only."""
    out: list[JumpCutCandidate] = []
    for prev, cur, nxt in zip(decisions, decisions[1:], decisions[2:]):
        if not (prev.get("action") == "KEEP" and cur.get("action") == "REMOVE"
                and nxt.get("action") == "KEEP"):
            continue
        gap = float(cur["end"]) - float(cur["start"])
        same = (int(prev.get("scene_id", -1)) == int(nxt.get("scene_id", -1))
                and int(prev.get("scene_id", -1)) >= 0)
        potential = bool(same and gap < 2.0)
        ev = [_ev("jump_cut_gap", "edl", float(cur["start"]), float(cur["end"]),
                  "gap_s", round(gap, 3), 2.0,
                  f"removed {gap:.2f}s between keeps in "
                  f"{'same' if same else 'different'} scenes")]
        out.append(JumpCutCandidate(
            gap_start=float(cur["start"]), gap_end=float(cur["end"]),
            gap_duration=round(gap, 6),
            before_scene_id=int(prev.get("scene_id", -1)),
            after_scene_id=int(nxt.get("scene_id", -1)),
            same_scene=same, potential_jump_cut=potential, evidence=ev))
    return out


# ---------------- report + refinement ----------------

def analyze_intelligence(audio: dict, transcript: dict, scenes: dict,
                         edl: dict, duration: float,
                         policy: dict) -> IntelligenceReport:
    """Pure analysis. Raises IntelError on missing/invalid inputs."""
    t0 = time.perf_counter()
    if not isinstance(audio, dict) or not isinstance(audio.get("silence"), list):
        raise IntelError("missing/invalid audio analysis (need silence[])")
    if not isinstance(transcript, dict) or "segments" not in transcript:
        raise IntelError("missing/invalid transcript analysis")
    if not isinstance(scenes, dict) or not scenes.get("scenes"):
        raise IntelError("missing/invalid scene analysis (need scenes[])")
    if not isinstance(edl, dict) or not edl.get("decisions"):
        raise IntelError("missing/invalid base EDL (run edit first)")
    words, supported = _norm_words(transcript)
    silences = [{"start": float(s["start"]), "end": float(s["end"]),
                 "duration": float(s.get("duration", float(s["end"]) - float(s["start"])))}
                for s in audio.get("silence", [])]
    metrics, median = scene_metrics(scenes, words)
    pacing = pacing_metrics(scenes, words, silences, duration) \
        if policy["intel_enable_pacing"] else PacingMetrics()
    reps = repetition_candidates(words, policy["intel_repetition_min_words"]) \
        if policy["intel_enable_repetition"] else []
    points = preferred_points(words, silences, scenes, gap_min=0.15)
    punct = sum(1 for w in words if w["terminal"]) > 0
    decisions = edl.get("decisions", [])
    safety: list[CutSafety] = []
    for i, d in enumerate(decisions):
        if d.get("action") != "REMOVE":
            continue
        neighbors = ([decisions[i - 1]] if i > 0 else []) + \
                    ([decisions[i + 1]] if i + 1 < len(decisions) else [])
        refs = {(r.get("segment_id"),
                 normalize_token(str(r.get("word", ""))),
                 round(float(r.get("start", 0)), 3))
                for r in (d.get("word_refs", []) or [])}
        safety.append(assess_removal(float(d["start"]), float(d["end"]),
                                     str(d.get("decision_id", "")), {
                                         "words": words, "referenced_fillers": refs,
                                         "filler_set": set(supported),
                                         "scenes": _scene_list(scenes),
                                         "neighbors": neighbors,
                                         "min_keep": policy["intel_min_keep_s"],
                                         "min_remove": policy["intel_min_remove_s"],
                                         "punctuated": punct}))
    jumps = jump_cut_candidates(decisions) if policy["intel_enable_jumpcut"] else []
    return IntelligenceReport(
        source=str(edl.get("source", "")), duration=duration, policy=dict(policy),
        scene_metrics=metrics, median_scene_duration=median, pacing=pacing,
        continuity=continuity(scenes, words), repetitions=reps, jump_cuts=jumps,
        cut_safety=safety, preferred_points=points,
        sentence_signals={"total_words": len(words),
                          "punctuated_words": sum(1 for w in words if w["terminal"]),
                          "coverage": round(sum(1 for w in words if w["terminal"]) / len(words), 4) if words else 0.0,
                          "limitation": ("Whisper word tokens rarely carry sentence punctuation; "
                                         "sentence-boundary inference is heuristic.")},
        processing_s=round(time.perf_counter() - t0, 3))


def _split_keep_for_repetition(keep: dict, span: dict, min_keep: float
                               ) -> list[dict] | None:
    """Split one KEEP around a repetition span. None when unsafe to do so."""
    ks, ke = float(keep["start"]), float(keep["end"])
    ss, se = float(span["start"]), float(span["end"])
    if not (ks < ss - 1e-6 and se + 1e-6 < ke):
        return None  # must sit strictly inside a single keep
    if min(ss - ks, ke - se) < min_keep - 1e-6:
        return None  # remnants too short: keep the speech
    base = {k: keep[k] for k in ("reason", "confidence", "scene_id") if k in keep}
    left = dict(keep, start=ks, end=ss)
    mid = dict(keep, start=ss, end=se, action="REMOVE", reason="repetition",
               confidence=0.6, word_refs=[{**span, "role": "repeated_occurrence"}],
               metadata={**(keep.get("metadata", {}) or {}),
                         "provenance": {"original_action": "KEEP",
                                        "original_reason": keep.get("reason", ""),
                                        "rule": "repetition_removal",
                                        "refined_by": ENGINE_TAG}})
    right = dict(keep, start=se, end=ke)
    return [left, mid, right]


def refine_edl(edl: dict, report: IntelligenceReport,
               policy: dict) -> tuple[dict, list[dict]]:
    """Apply conservative refinements. Returns (refined_edl, changes).

    Default: revert UNSAFE removals (strict: +CAUTION) to KEEP with
    provenance. Opt-in: repetition removal. Result re-validated; any
    violation raises IntelError instead of shipping a broken EDL.
    """
    from engine.rendering.execution import validate_edl
    strict = policy["intel_safety_mode"] == "strict"
    revert_statuses = {"UNSAFE"} | ({"CAUTION"} if strict else set())
    safety_by_id = {s.decision_id: s for s in report.cut_safety}
    refined: list[dict] = []
    changes: list[dict] = []
    for d in edl.get("decisions", []):
        dec = dict(d)
        if (dec.get("action") == "REMOVE" and policy["intel_safety_net"]
                and dec.get("decision_id") in safety_by_id
                and safety_by_id[dec["decision_id"]].status in revert_statuses):
            st = safety_by_id[dec["decision_id"]].status
            changes.append({"decision_id": dec.get("decision_id"), "from": "REMOVE",
                            "to": "KEEP", "rule": "safety_revert",
                            "evidence": [asdict(e) for e in
                                         safety_by_id[dec["decision_id"]].evidence]})
            dec["action"] = "KEEP"
            dec["reason"] = "safety_revert"
            dec["confidence"] = 1.0
            dec["metadata"] = {**(dec.get("metadata", {}) or {}),
                               "provenance": {"original_action": "REMOVE",
                                              "original_reason": d.get("reason", ""),
                                              "rule": "safety_revert",
                                              "safety_status": st,
                                              "refined_by": ENGINE_TAG}}
        refined.append(dec)

    if policy["intel_repetition_removal"]:
        for cand in report.repetitions:
            for occ in cand.spans[1:]:  # keep first occurrence, remove repeats
                span = {"start": occ["start"], "end": occ["end"],
                        "segment_id": occ.get("segment_id")}
                placed = False
                for i, dec in enumerate(refined):
                    if dec.get("action") != "KEEP":
                        continue
                    # Base EDL never straddles scenes (Phase 8 pre-split), so
                    # strict containment in one KEEP implies one scene.
                    parts = _split_keep_for_repetition(
                        dec, span, policy["intel_min_keep_s"])
                    if parts is None:
                        continue
                    refined[i:i + 1] = parts
                    changes.append({"decision_id": dec.get("decision_id"),
                                    "from": "KEEP", "to": "REMOVE(part)",
                                    "rule": "repetition_removal",
                                    "evidence": [asdict(e) for e in cand.evidence]})
                    placed = True
                    break
                if not placed:
                    report.warnings.append(
                        f"repetition at {span['start']}-{span['end']} not placed "
                        f"(remnants too short or crosses keeps)")

    # Renumber deterministically, keep originals in provenance.
    seq = 0
    for dec in refined:
        seq += 1
        meta = dec.get("metadata", {}) or {}
        if "provenance" in meta:
            meta["provenance"] = {**meta["provenance"],
                                  "original_id": dec.get("decision_id")}
        dec["metadata"] = meta
        dec["decision_id"] = f"ref_{seq:04d}"

    out = dict(edl, decisions=refined,
               policy={**(edl.get("policy", {}) or {}), "intel": dict(policy)},
               warnings=list(edl.get("warnings", [])) + list(report.warnings))
    kept = round(sum(float(d["end"]) - float(d["start"]) for d in refined
                     if d.get("action") == "KEEP"), 6)
    removed = round(sum(float(d["end"]) - float(d["start"]) for d in refined
                        if d.get("action") == "REMOVE"), 6)
    out["decision_count"] = len(refined)
    out["kept_duration"] = kept
    out["removed_duration"] = removed
    out["removal_ratio"] = round(removed / float(edl.get("duration", 0)), 6) \
        if edl.get("duration") else 0.0
    issues = validate_edl(out, edl.get("duration"))
    if issues:
        raise IntelError(f"refinement broke EDL invariants: {issues[:3]}")
    return out, changes


def _versions() -> dict:
    import platform
    return {"python": platform.python_version(), "engine": "0.1.0"}


def run_intelligence_for_project(project_id: str,
                                 policy_overrides: dict | None = None) -> dict:
    """Load base EDL + cached analyses, analyze, refine, cache, log."""
    import json
    project = load_project(project_id)
    pid = project.id
    log_file = project_dir(pid) / "logs" / "run.jsonl"
    policy = resolve_intel_policy(policy_overrides)

    def _load(name: str, required: bool = True) -> dict | None:
        p = project_dir(pid) / "analysis" / name
        if not p.is_file():
            if required:
                raise IntelError(f"missing analysis artifact analysis/{name} "
                                 f"(run analyze/transcribe/scenes/edit first)")
            return None
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise IntelError(f"corrupt analysis artifact analysis/{name}: {exc}") from exc

    edl_path = project_dir(pid) / "edit" / "edit_decision.json"
    if not edl_path.is_file():
        raise IntelError("missing base EDL edit/edit_decision.json (run edit first)")
    try:
        edl = json.loads(edl_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise IntelError(f"corrupt base EDL: {exc}") from exc
    audio = _load("audio_analysis.json")
    transcript = _load("transcript.json")
    scenes = _load("scenes.json", required=False)
    if scenes is None:
        if _project_audio_only(pid, project.input_path):
            duration = float(audio.get("audio_duration") or 0)
            scenes = {"duration": duration,
                      "scenes": [{"scene_id": 0, "start": 0.0, "end": duration,
                                  "duration": duration, "start_frame": 0, "end_frame": 0}]}
        else:
            raise IntelError("missing analysis artifact analysis/scenes.json")
    duration = float(edl.get("duration") or 0)
    if duration <= 0:
        raise IntelError("base EDL has no usable duration")

    refs = {"audio": hash_analysis(audio), "transcript": hash_analysis(transcript),
            "scenes": hash_analysis(scenes)}
    key = cache_key(project.input_path, "intelligence",
                    {"edl_hash": edl_hash(edl), **refs,
                     "policy": policy, "intel_version": INTEL_VERSION})
    t0 = time.perf_counter()
    hit = cached(key)
    if hit is not None:
        payload = json.loads(hit.read_text(encoding="utf-8"))
        payload["intelligence"]["cached"] = True
        payload["refined_edl"]["cached"] = True
        write_artifact(pid, "edit", "edit_intelligence.json", payload["intelligence"])
        write_artifact(pid, "edit", "refined_edit_decision.json", payload["refined_edl"])
        mark_stage(project, "intelligence", "cached", "edit/edit_intelligence.json")
        log_event(log_file, "intelligence", "analyze", "cached",
                  time.perf_counter() - t0, "edit/edit_intelligence.json",
                  _versions(), {"scenes": len(payload["intelligence"].get("scene_metrics", [])),
                                "changes": len(payload["intelligence"].get("refined_changes", []))})
        return {"project": pid, "cached": True,
                "intelligence": payload["intelligence"],
                "refined_edl": payload["refined_edl"]}

    report = analyze_intelligence(audio, transcript, scenes, edl, duration, policy)
    refined, changes = refine_edl(edl, report, policy)
    report.refined_edl_hash = edl_hash(refined)
    report.refined_changes = changes
    intel_payload, refined_payload = asdict(report), refined
    write_artifact(pid, "edit", "edit_intelligence.json", intel_payload)
    write_artifact(pid, "edit", "refined_edit_decision.json", refined_payload)
    store(key, {"intelligence": intel_payload, "refined_edl": refined_payload})
    mark_stage(project, "intelligence", "done", "edit/edit_intelligence.json")
    log_event(log_file, "intelligence", "analyze", "ok", time.perf_counter() - t0,
              "edit/edit_intelligence.json", _versions(),
              {"scenes": len(report.scene_metrics), "changes": len(changes),
               "repetitions": len(report.repetitions),
               "jump_cuts": len(report.jump_cuts)})
    return {"project": pid, "cached": False,
            "intelligence": intel_payload, "refined_edl": refined_payload}


def _project_audio_only(pid: str, input_path: str) -> bool:
    import json
    media = project_dir(pid) / "analysis" / "media_info.json"
    if media.is_file():
        try:
            return not bool(json.loads(media.read_text(encoding="utf-8")).get("video_codec"))
        except (json.JSONDecodeError, AttributeError):
            pass
    try:
        from engine.core.media import probe
        return not bool(probe(input_path).video_codec)
    except Exception:
        return False
