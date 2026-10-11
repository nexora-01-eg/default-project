"""Phase 12 — professional editor brain. Decision layer ABOVE analyses.

8 passes: understand -> structure -> density/hook/story -> pacing ->
candidates (cuts/jump/broll/visual/audio/repetition) -> safety/conflicts ->
ranking -> master plan. Pure functions on analysis dicts; no rendering,
no downloads, no media fetching, no timeline mutation.

Standing rules: KEEP on ambiguity; safety vetoes (never overridden, not
even by --aggressive); outliers/risks flagged, never deleted for being
outliers; repetitions are candidates, never auto-trims; priority and
confidence are separate dimensions; no combined magic scores.
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
    AudioRecommendation,
    BrollOpportunity,
    ConflictResolution,
    CutCandidate,
    DensityWindow,
    EditorialRepetition,
    Evidence,
    HookAssessment,
    ProfessionalEditPlan,
    QualityRisk,
    StorySegment,
    StyleProfile,
    VisualChange,
)
from engine.core.pipeline import cache_key, cached, store
from engine.core.project_store import (
    load_project,
    mark_stage,
    project_dir,
    write_artifact,
)
from engine.editing.decisions import hash_analysis

BRAIN_VERSION = "1.0.0"
ENGINE_TAG = "phase12-1.0"

PRINCIPLE_ORDER = ("story_continuity", "edit_safety", "content_value",
                   "visual_quality", "pacing")
PRIORITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3,
                 "informational": 4}

STYLES: dict[str, dict] = {
    "talking_head":   {"pacing": "normal", "visual_density": "medium",
                       "broll_intensity": "medium", "silence_tolerance_s": 1.2,
                       "jump_cut_tolerance": "low", "repetition_policy": "investigate",
                       "subtitle_importance": "high", "hook_importance": "high",
                       "max_cuts_per_min": 10.0},
    "podcast":        {"pacing": "relaxed", "visual_density": "low",
                       "broll_intensity": "off", "silence_tolerance_s": 2.0,
                       "jump_cut_tolerance": "high", "repetition_policy": "keep",
                       "subtitle_importance": "normal", "hook_importance": "low",
                       "max_cuts_per_min": 6.0},
    "interview":      {"pacing": "normal", "visual_density": "medium",
                       "broll_intensity": "medium", "silence_tolerance_s": 1.5,
                       "jump_cut_tolerance": "low", "repetition_policy": "investigate",
                       "subtitle_importance": "high", "hook_importance": "normal",
                       "max_cuts_per_min": 10.0},
    "educational":    {"pacing": "normal", "visual_density": "high",
                       "broll_intensity": "medium", "silence_tolerance_s": 1.5,
                       "jump_cut_tolerance": "medium", "repetition_policy": "investigate",
                       "subtitle_importance": "high", "hook_importance": "normal",
                       "max_cuts_per_min": 10.0},
    "tutorial":       {"pacing": "normal", "visual_density": "high",
                       "broll_intensity": "high", "silence_tolerance_s": 1.0,
                       "jump_cut_tolerance": "medium", "repetition_policy": "trim_candidate",
                       "subtitle_importance": "high", "hook_importance": "normal",
                       "max_cuts_per_min": 12.0},
    "commentary":     {"pacing": "brisk", "visual_density": "high",
                       "broll_intensity": "high", "silence_tolerance_s": 0.8,
                       "jump_cut_tolerance": "high", "repetition_policy": "trim_candidate",
                       "subtitle_importance": "high", "hook_importance": "high",
                       "max_cuts_per_min": 16.0},
    "social_short":   {"pacing": "brisk", "visual_density": "high",
                       "broll_intensity": "high", "silence_tolerance_s": 0.5,
                       "jump_cut_tolerance": "high", "repetition_policy": "trim_candidate",
                       "subtitle_importance": "high", "hook_importance": "high",
                       "max_cuts_per_min": 20.0},
    "documentary":    {"pacing": "relaxed", "visual_density": "medium",
                       "broll_intensity": "high", "silence_tolerance_s": 2.0,
                       "jump_cut_tolerance": "low", "repetition_policy": "keep",
                       "subtitle_importance": "normal", "hook_importance": "normal",
                       "max_cuts_per_min": 8.0},
    "cinematic":      {"pacing": "relaxed", "visual_density": "medium",
                       "broll_intensity": "medium", "silence_tolerance_s": 2.5,
                       "jump_cut_tolerance": "low", "repetition_policy": "keep",
                       "subtitle_importance": "low", "hook_importance": "normal",
                       "max_cuts_per_min": 6.0},
    "corporate":      {"pacing": "normal", "visual_density": "medium",
                       "broll_intensity": "medium", "silence_tolerance_s": 1.5,
                       "jump_cut_tolerance": "low", "repetition_policy": "investigate",
                       "subtitle_importance": "high", "hook_importance": "normal",
                       "max_cuts_per_min": 10.0},
    "general":        {"pacing": "normal", "visual_density": "medium",
                       "broll_intensity": "low", "silence_tolerance_s": 1.5,
                       "jump_cut_tolerance": "medium", "repetition_policy": "investigate",
                       "subtitle_importance": "normal", "hook_importance": "normal",
                       "max_cuts_per_min": 12.0},
}
_BROLL_STEPS = ("off", "low", "medium", "high")
_JUMP_STEPS = ("low", "medium", "high")
CTA_WORDS = ("subscribe", "link", "comment", "share", "follow", "sponsor")
_STOPWORDS = frozenset(("the a an and or of to in on for with is are was were be been "
                        "it its this that these those you your we our they their he she it "
                        "at by from as at so if out up about into over after").split())


class BrainError(RuntimeError):
    pass


def _r6(x: float) -> float:
    return round(float(x), 6)


def _overlap(a_start: float, a_end: float, b_start: float, b_end: float) -> float:
    return min(a_end, b_end) - max(a_start, b_start)


def _ev(evidence_type: str, source: str, start: float, end: float,
        metric: str, value, threshold, explanation: str) -> Evidence:
    return Evidence(evidence_type=evidence_type, source=source,
                    start=_r6(start), end=_r6(end), metric=metric,
                    value=value, threshold=threshold, explanation=explanation)


def resolve_style(name: str = "general", target_duration: float | None = None,
                  aggressive: bool = False) -> StyleProfile:
    if name not in STYLES:
        raise BrainError(f"unknown style {name!r}: expected one of {sorted(STYLES)}")
    base = dict(STYLES[name])
    if aggressive:  # documented preset shift: pace up, tolerate less dead air
        base["silence_tolerance_s"] = round(base["silence_tolerance_s"] * 0.5, 3)
        base["broll_intensity"] = _BROLL_STEPS[min(3, _BROLL_STEPS.index(base["broll_intensity"]) + 1)]
        base["jump_cut_tolerance"] = _JUMP_STEPS[min(2, _JUMP_STEPS.index(base["jump_cut_tolerance"]) + 1)]
        base["max_cuts_per_min"] = base["max_cuts_per_min"] * 1.5
    if target_duration is not None:
        try:
            target_duration = float(target_duration)
        except (TypeError, ValueError):
            raise BrainError(f"target_duration must be a number") from None
        if target_duration <= 0:
            raise BrainError("target_duration must be > 0")
    return StyleProfile(name=name, pacing=base["pacing"],
                        target_duration=target_duration,
                        visual_density=base["visual_density"],
                        broll_intensity=base["broll_intensity"],
                        silence_tolerance_s=base["silence_tolerance_s"],
                        jump_cut_tolerance=base["jump_cut_tolerance"],
                        repetition_policy=base["repetition_policy"],
                        subtitle_importance=base["subtitle_importance"],
                        hook_importance=base["hook_importance"],
                        max_cuts_per_min=base["max_cuts_per_min"])


def _words(transcript: dict) -> tuple[list[dict], set[str]]:
    language = transcript.get("language", "") or ""
    supported = filler_set(language)
    out: list[dict] = []
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
            out.append({"word": text, "norm": norm, "start": ws, "end": we,
                        "segment_id": seg.get("id"),
                        "probability": float(w.get("probability", 0.0) or 0.0),
                        "is_filler": norm in supported,
                        "terminal": text.rstrip().endswith((".", "?", "!", "…", "؟"))})
    out.sort(key=lambda x: (x["start"], x["end"]))
    return out, supported


def _scenes_bounds(scenes: dict) -> list[dict]:
    return sorted(scenes.get("scenes", []) or [], key=lambda s: (s["start"], s["end"]))


# ---------------- PASS 2: hook ----------------

def analyze_hook(transcript_words: list[dict], silences: list[dict],
                 duration: float, style: StyleProfile) -> HookAssessment:
    window = min(30.0, 0.2 * duration) if duration > 0 else 0.0
    if not transcript_words and not silences:
        return HookAssessment(start=0.0, end=_r6(window),
                              recommended_opening_strategy="investigate",
                              confidence=0.0,
                              limitation="no transcript words and no silence data")
    in_window = [w for w in transcript_words if w["start"] < window]
    questions = sum(1 for w in in_window if "?" in w["word"])
    fillers = sum(1 for w in in_window if w["is_filler"])
    sil_in = [s for s in silences if s["start"] < window]
    sil_s = round(sum(min(s["end"], window) - s["start"] for s in sil_in
                      if s["end"] > 0), 3)
    first_delay = round(min([w["start"] for w in in_window] + [window]), 3)
    signals = [
        {"signal": "question_present", "value": questions > 0, "detail": questions},
        {"signal": "word_count", "value": len(in_window), "detail": len(in_window)},
        {"signal": "filler_count", "value": fillers, "detail": fillers},
        {"signal": "silence_s", "value": sil_s, "detail": sil_s},
        {"signal": "first_word_delay_s", "value": first_delay, "detail": first_delay}]
    preamble = []
    for s in sil_in:
        if s["start"] < 1e-6 or (not in_window or s["start"] < min(w["start"] for w in in_window)):
            if s["start"] < (in_window[0]["start"] if in_window else window):
                preamble.append({"start": s["start"],
                                 "end": round(min(s["end"], window), 3),
                                 "reason": "leading_silence"})
                break
    content_start = min([w["start"] for w in in_window if not w["is_filler"]] or [window])
    if in_window and content_start > 1.0:
        preamble.append({"start": 0.0, "end": round(content_start, 3),
                         "reason": "filler_only_opening"})
    pre_s = round(sum(p["end"] - p["start"] for p in preamble), 3)
    if pre_s >= 1.0:
        strategy, conf = "trim_preamble", 0.7
    elif in_window:
        strategy, conf = "keep_as_is", 0.4
    else:
        strategy, conf = "investigate", 0.2
    return HookAssessment(start=0.0, end=_r6(window),
                          hook_strength_signals=signals,
                          removable_preamble=preamble,
                          recommended_opening_strategy=strategy,
                          confidence=conf, limitation="" if in_window else
                          "opening has no transcript words")


# ---------------- PASS 2: story + density ----------------

def story_structure(transcript_words: list[dict], scenes: list[dict],
                    duration: float) -> list[StorySegment]:
    bounds = scenes
    if not bounds:
        return [StorySegment(segment_id=0, start=0.0, end=_r6(duration),
                             classification="unknown", confidence=0.2,
                             evidence=[asdict(_ev("no_scenes", "scenes", 0, duration,
                                                  "scene_count", 0, 1,
                                                  "no scene bounds available"))],
                             scene_ids=[])]
    out: list[StorySegment] = []
    for i, sc in enumerate(bounds):
        ss, se = float(sc["start"]), float(sc["end"])
        seg_words = [w for w in transcript_words if w["start"] >= ss and w["end"] <= se]
        ev = [asdict(_ev("segment_words", "transcript", ss, se, "word_count",
                         len(seg_words), 0, f"{len(seg_words)} words in scene"))]
        text = " ".join(w["norm"] for w in seg_words)
        cta = [w for w in CTA_WORDS if w in text]
        has_q = any("?" in w["word"] for w in seg_words)
        if not seg_words:
            # Wordless segments carry no story signal: unknown, never a
            # positional label dressed as understanding.
            cls, conf = ("unknown", 0.2)
            ev.append(asdict(_ev("empty_segment", "transcript", ss, se,
                                 "word_count", 0, 1, "no transcript words here")))
        elif cta:
            cls, conf = "call_to_action", 0.7
            ev.append(asdict(_ev("cta_keywords", "transcript", ss, se,
                                 "keywords", ",".join(cta), ">=1",
                                 "call-to-action phrasing detected")))
        elif i == 0:
            cls, conf = ("hook", 0.4)
            if has_q:
                ev.append(asdict(_ev("question", "transcript", ss, se, "present",
                                     True, True, "opening question detected")))
        elif i == len(bounds) - 1:
            cls, conf = ("conclusion", 0.35)
        elif not seg_words:
            cls, conf = ("unknown", 0.2)
        elif len(seg_words) / max(se - ss, 1e-6) > 1.0:
            cls, conf = ("main_point", 0.45)
        else:
            cls, conf = ("transition", 0.35)
        out.append(StorySegment(segment_id=i, start=_r6(ss), end=_r6(se),
                                classification=cls, confidence=conf,
                                evidence=ev,
                                scene_ids=[int(sc.get("scene_id", -1))]))
    return out


def density_windows(transcript_words: list[dict], silences: list[dict],
                    scenes: list[dict], repetitions: list,
                    duration: float, width: float = 10.0) -> list[DensityWindow]:
    wins: list[DensityWindow] = []
    t = 0.0
    while t < duration - 1e-6:
        e = min(t + width, duration)
        ws = [w for w in transcript_words if w["start"] >= t and w["end"] <= e]
        norms = [w["norm"] for w in ws]
        uniq = len(set(norms)) / len(norms) if norms else 0.0
        sents = sum(1 for w in ws if w["terminal"])
        pause = round(sum(_overlap(s["start"], s["end"], t, e) for s in silences), 3)
        reps = sum(1 for r in repetitions
                   for sp in r.get("spans", []) if t <= sp["start"] < e)
        chg = sum(1 for s in scenes if t < float(s["start"]) < e)
        wps = len(ws) / (e - t) if e > t else 0.0
        wins.append(DensityWindow(start=_r6(t), end=_r6(e),
                                  words_per_sec=round(wps, 3),
                                  unique_ratio=round(uniq, 3),
                                  sentence_count=sents, pause_s=pause,
                                  repetition_hits=reps, scene_changes=chg,
                                  components={"words": len(ws)}))
        t = e
    med = statistics.median([w.words_per_sec for w in wins]) if wins else 0.0
    for w in wins:
        if med <= 0:
            w.density = "unknown"
        elif w.words_per_sec > 1.3 * med:
            w.density = "high"
        elif w.words_per_sec < 0.7 * med:
            w.density = "low"
        else:
            w.density = "normal"
    return wins


# ---------------- PASS 3: pacing ----------------

def pacing_analysis(scenes: list[dict], density: list[DensityWindow],
                    visual: dict | None, words: list[dict],
                    style: StyleProfile, duration: float) -> list[dict]:
    recs: list[dict] = []
    durs = [float(s["end"]) - float(s["start"]) for s in scenes]
    med = statistics.median(durs) if durs else 0.0
    vis_by_id = {int(s.get("scene_id", -1)): s
                 for s in (visual.get("scene_summaries", []) if visual else [])}
    for sc in scenes:
        sid, ss, se = int(sc.get("scene_id", -1)), float(sc["start"]), float(sc["end"])
        dur = se - ss
        dens = next((w.density for w in density if w.start <= ss < w.end), "unknown")
        motion = (vis_by_id.get(sid, {}) or {}).get("motion_mean", None)
        static = motion is not None and motion < 0.05
        ev = [asdict(_ev("scene_duration", "scenes", ss, se, "duration_s",
                         round(dur, 3), round(med, 3),
                         f"scene {dur:.1f}s vs median {med:.1f}s")),
              asdict(_ev("scene_density", "transcript", ss, se, "density",
                         dens, "median-relative", f"density {dens}"))]
        if motion is not None:
            ev.append(asdict(_ev("scene_motion", "visual", ss, se, "motion_mean",
                                 motion, 0.05, "static" if static else "in motion")))
        speaks = any(w["start"] < se and w["end"] > ss for w in words)
        if static and speaks:
            # Speech matters and visuals don't move: change the picture,
            # never punish the words.
            verdict, priority, conf = "add_visual_change", "medium", 0.55
        elif dur > 2.0 * med and med > 0 and dens in ("low", "unknown"):
            verdict, priority, conf = "tighten", "low", 0.5
        else:
            verdict, priority, conf = "maintain", "informational", 0.7
        recs.append({"scope": f"scene_{sid}", "start": ss, "end": se,
                     "verdict": verdict,
                     "priority": priority, "confidence": conf,
                     "evidence": ev})
    cuts = sum(1 for _ in scenes) - 1
    cpm = cuts / (duration / 60.0) if duration > 0 else 0.0
    if cpm > style.max_cuts_per_min:
        recs.append({"scope": "global", "start": 0.0, "end": duration,
                     "verdict": "open_up",
                     "priority": "medium", "confidence": 0.5,
                     "evidence": [asdict(_ev("cut_density", "scenes", 0, duration,
                                             "cuts_per_min", round(cpm, 2),
                                             style.max_cuts_per_min,
                                             "cut rate above style ceiling"))]})
    if style.target_duration is not None and duration > style.target_duration:
        recs.append({"scope": "global", "start": 0.0, "end": duration,
                     "verdict": "investigate", "priority": "medium",
                     "confidence": 0.6,
                     "evidence": [asdict(_ev("target_gap", "policy", 0, duration,
                                             "excess_s",
                                             round(duration - style.target_duration, 1), 0,
                                             "content exceeds target; no auto-fit applied"))]})
    return recs


# ---------------- PASS 5: cut planner ----------------

def _nearest_word_gap(start: float, end: float, words: list[dict]) -> float:
    gaps = [w["start"] - end for w in words if w["start"] >= end - 1e-6]
    gaps += [start - w["end"] for w in words if w["end"] <= start + 1e-6]
    gaps = [g for g in gaps if g >= -1e-6]
    return round(min(gaps), 3) if gaps else 999.0


def plan_cuts(edl: dict, intel: dict | None, visual: dict | None,
              words: list[dict], scenes: list[dict],
              style: StyleProfile) -> tuple[list[CutCandidate], list[ConflictResolution]]:
    safety = {s.get("decision_id"): s for s in (intel.get("cut_safety", [])
                                                if intel else [])}
    vis_motion: dict[tuple, float] = {}
    if visual:
        for s in visual.get("scene_summaries", []):
            vis_motion[int(s.get("scene_id", -1))] = float(s.get("motion_mean", 0.0) or 0.0)
    cuts: list[CutCandidate] = []
    conflicts: list[ConflictResolution] = []
    decisions = edl.get("decisions", [])
    for i, d in enumerate(decisions):
        if d.get("action") != "REMOVE":
            continue
        s, e, did = float(d["start"]), float(d["end"]), str(d.get("decision_id", ""))
        near = [w for w in words if w["end"] > s - 1.0 and w["start"] < e + 1.0]
        prev_w = [w for w in words if w["end"] <= s + 1e-6]
        next_w = [w for w in words if w["start"] >= e - 1e-6]
        split_sentence = bool(prev_w and next_w and not prev_w[-1]["terminal"]
                              and not prev_w[-1]["is_filler"] and not next_w[0]["is_filler"])
        contained = any(float(sc["start"]) - 1e-6 <= s and e <= float(sc["end"]) + 1e-6
                        for sc in scenes)
        sid = int(d.get("scene_id", -1))
        motion = vis_motion.get(sid, None)
        keeps = [x for x in decisions[max(0, i - 1):i + 2] if x.get("action") == "KEEP"]
        keep_lens = [float(x["end"]) - float(x["start"]) for x in keeps]
        gap = _nearest_word_gap(s, e, words)
        factors = [
            asdict(_ev("speech_proximity", "transcript", s, e, "nearest_word_gap_s",
                       gap, 0.2, "cut sits clear of words" if gap >= 0.2 else "cut near speech")),
            asdict(_ev("sentence_boundary", "transcript", s, e, "splits_sentence",
                       split_sentence, False, "splits a sentence" if split_sentence else "no sentence split")),
            asdict(_ev("scene_contained", "scenes", s, e, "contained", contained, True,
                       "inside one scene" if contained else "crosses scene boundary")),
            asdict(_ev("visual_context", "visual", s, e, "motion_mean",
                       motion if motion is not None else "unknown", 0.05,
                       "visual data absent" if motion is None else
                       ("static join" if motion < 0.05 else "visual change at join"))),
            asdict(_ev("resulting_shots", "edl", s, e, "min_keep_s",
                       round(min(keep_lens), 3) if keep_lens else 0.0, 0.5,
                       "surrounding keeps viable")),
            asdict(_ev("base_evidence", "edl", s, e, "base_reason",
                       f"{d.get('reason')}:{d.get('confidence')}", "phase8",
                       "Phase 8 rule that proposed this removal")),
            asdict(_ev("removal_size", "edl", s, e, "duration_s",
                       round(e - s, 3), style.silence_tolerance_s,
                       "removal duration vs style tolerance"))]
        st = (safety.get(did) or {}).get("status", "unknown")
        alternatives = ["keep"]
        verdict, priority, conf = "approve", "medium", 0.6
        if st == "UNSAFE":
            verdict, priority, conf = "reject", "high", 0.85
        elif split_sentence and any(not w["is_filler"] for w in near):
            verdict, priority, conf = "reject", "high", 0.7
            alternatives.append("broll_cover")
        elif st == "CAUTION":
            verdict, priority, conf = "downgrade_keep", "medium", 0.6
        elif gap < 0.2 and any(not w["is_filler"] for w in near):
            verdict, priority, conf = "downgrade_keep", "medium", 0.55
        if verdict in ("approve",) and motion is not None and motion < 0.05 \
                and style.jump_cut_tolerance == "low" and (e - s) < 2.0:
            verdict, priority = "approve_with_mitigation", "medium"
            alternatives.append("broll_cover")
        # Explicit conflict record when pro-cut and con signals collide.
        pro = [f for f in factors if f["evidence_type"] in ("base_evidence", "resulting_shots")]
        con = [f for f in factors if f["metric"] in ("sentence_boundary",)
               and f["value"] is True]
        if st in ("CAUTION", "UNSAFE"):
            con = con + [{"signal": f"safety_{st}", "principle": "edit_safety"}]
        if verdict in ("reject", "downgrade_keep") and pro:
            conflicts.append(ConflictResolution(
                topic=f"cut {did} [{s}-{e}]", pro_signals=[p["metric"] for p in pro],
                con_signals=[c.get("signal", c.get("metric", "?")) for c in con] or ["safety"],
                winner="keep",
                principle="edit_safety" if st in ("CAUTION", "UNSAFE") else "story_continuity",
                explanation=("safety/story signals outrank cut signals; "
                             "meaning is never sacrificed for cut frequency")))
        cuts.append(CutCandidate(decision_id=did, start=s, end=e, verdict=verdict,
                                 base_action="REMOVE", priority=priority,
                                 confidence=conf, factors=factors,
                                 alternatives=alternatives))
    return cuts, conflicts


# ---------------- PASS 5: jump strategy ----------------

_JUMP_MITIGATIONS = ("accept_cut", "preserve_section", "broll", "cutaway",
                     "alternate_visual", "reframe_later", "transition_later")


def jump_strategy(jump_candidates: list[dict], style: StyleProfile) -> list[dict]:
    out = []
    tol = style.jump_cut_tolerance
    for j in jump_candidates:
        gap, same = float(j.get("gap_duration", 0)), bool(j.get("same_scene"))
        if not same:
            rec, sev = ["accept_cut"], "low"
        elif gap >= 2.0 or tol == "high":
            rec, sev = ["accept_cut"], "low"
        elif tol == "low":
            rec, sev = (["broll", "cutaway", "preserve_section"]
                        if gap >= 0.5 else ["accept_cut", "reframe_later"]), \
                ("high" if gap >= 0.5 else "medium")
        else:
            rec, sev = ["broll", "accept_cut"], "medium"
        out.append({"gap_start": j.get("gap_start"), "gap_end": j.get("gap_end"),
                    "severity": sev, "recommended_mitigations": rec,
                    "available_mitigations": list(_JUMP_MITIGATIONS),
                    "priority": "medium" if sev != "low" else "informational",
                    "confidence": 0.55,
                    "evidence": j.get("evidence", [])})
    return out


# ---------------- PASS 5: B-roll ----------------

def _topic_words(words: list[dict], start: float, end: float, limit: int = 3) -> list[str]:
    freq: dict[str, int] = {}
    for w in words:
        if w["start"] >= start and w["end"] <= end and not w["is_filler"]:
            n = w["norm"]
            if len(n) > 3 and n not in _STOPWORDS and n.isalpha():
                freq[n] = freq.get(n, 0) + 1
    return sorted(freq, key=lambda k: (-freq[k], k))[:limit]


def broll_opportunities(scenes: list[dict], words: list[dict],
                        visual: dict | None, jump_candidates: list[dict],
                        median_scene: float, style: StyleProfile,
                        duration: float) -> list[BrollOpportunity]:
    if style.broll_intensity == "off":
        return []
    out: list[BrollOpportunity] = []
    vis_by_id = {int(s.get("scene_id", -1)): s
                 for s in (visual.get("scene_summaries", []) if visual else [])}
    jump_gaps = [(float(j.get("gap_start", 0)), float(j.get("gap_end", 0)))
                 for j in jump_candidates if j.get("potential_jump_cut")]
    for sc in scenes:
        sid, ss, se = int(sc.get("scene_id", -1)), float(sc["start"]), float(sc["end"])
        dur = se - ss
        summary = vis_by_id.get(sid, {}) or {}
        motion = summary.get("motion_mean", None)
        static = motion is not None and motion < 0.05
        span_words = [w for w in words if w["start"] >= ss and w["end"] <= se]
        conceals = any(not (g_end <= ss or g_start >= se) for g_start, g_end in jump_gaps)
        long_static = static and dur >= 8.0
        medium_static = static and dur >= 4.0
        very_long = median_scene > 0 and dur > 2.0 * median_scene
        if not (conceals or long_static or medium_static or very_long):
            continue
        if conceals:
            reason, rec, pri, conf = "jump_cut_concealment", True, "medium", 0.65
            vtype = "cutaway"
        elif long_static:
            reason, rec, pri, conf = "visual_stagnation", True, "medium", 0.6
            vtype = "supporting_footage"
        elif very_long:
            reason, rec, pri, conf = "long_scene", False, "low", 0.45
            vtype = "supporting_footage"
        else:
            reason, rec, pri, conf = "visual_stagnation", False, "low", 0.45
            vtype = "supporting_footage"
        if style.broll_intensity == "high" and not rec and dur >= 4.0:
            rec = True  # style asks for density; still only a recommendation
        topic = _topic_words(span_words, ss, se)
        ev = [asdict(_ev("stagnation_span", "visual" if motion is not None else "scenes",
                         ss, se, "duration_s", round(dur, 3), 4.0,
                         f"{dur:.1f}s {'static' if static else 'long'} scene")),
              asdict(_ev("speech_present", "transcript", ss, se, "word_count",
                         len(span_words), 0, "speech continues underneath"))]
        out.append(BrollOpportunity(
            start=_r6(ss), end=_r6(se), duration=_r6(dur), reason=reason,
            desired_visual_type=vtype, semantic_topic=",".join(topic),
            transcript_ref={"words": len(span_words),
                            "span": [round(ss, 3), round(se, 3)]},
            priority=pri, recommended=rec, confidence=conf, evidence=ev))
    out.sort(key=lambda o: (o.start, o.end))
    return out


# ---------------- PASS 5: visual change + audio + repetition ----------------

def visual_change_plan(scenes: list[dict], broll: list[BrollOpportunity],
                       visual: dict | None) -> list[VisualChange]:
    out: list[VisualChange] = []
    broll_by_scene: dict[tuple, list] = {}
    for b in broll:
        for sc in scenes:
            if not (b.end <= float(sc["start"]) or b.start >= float(sc["end"])):
                broll_by_scene.setdefault(int(sc.get("scene_id", -1)), []).append(b)
    for i, sc in enumerate(scenes):
        sid, ss, se = int(sc.get("scene_id", -1)), float(sc["start"]), float(sc["end"])
        if not visual:
            out.append(VisualChange(start=ss, end=se, action="unknown",
                                    reason="no visual analysis available",
                                    priority="informational", confidence=0.3,
                                    evidence=[asdict(_ev("no_visual", "visual", ss, se,
                                                         "present", False, True,
                                                         "cannot plan visual changes blind"))]))
            continue
        out.append(VisualChange(start=ss, end=se, action="keep_current_shot",
                                reason="default: no evidence demands a change",
                                priority="informational", confidence=0.6, evidence=[]))
        if i + 1 < len(scenes):
            out.append(VisualChange(start=se, end=se, action="cut_to_next_scene",
                                    reason="existing scene boundary",
                                    priority="informational", confidence=0.8,
                                    evidence=[asdict(_ev("scene_boundary", "scenes", se, se,
                                                         "boundary", True, True,
                                                         "natural cut point"))]))
        for b in broll_by_scene.get(sid, []):
            out.append(VisualChange(start=b.start, end=b.end, action="broll",
                                    reason=b.reason, priority=b.priority,
                                    confidence=b.confidence, evidence=b.evidence))
            if b.reason == "jump_cut_concealment":
                out.append(VisualChange(
                    start=b.start, end=b.end, action="reframe",
                    reason="investigate only: no reframing capability in this phase",
                    priority="low", confidence=0.3,
                    evidence=[asdict(_ev("no_capability", "policy", b.start, b.end,
                                         "reframe_available", False, True,
                                         "recorded as future option, not planned"))]))
    return out


def audio_plan(audio: dict, transcript_words: list[dict], edl: dict,
               style: StyleProfile) -> list[AudioRecommendation]:
    out: list[AudioRecommendation] = []
    for d in edl.get("decisions", []):
        if d.get("action") == "REMOVE" and d.get("reason") == "long_silence":
            out.append(AudioRecommendation(
                kind="silence_reduction", start=float(d["start"]), end=float(d["end"]),
                detail=f"reduce {float(d['end']) - float(d['start']):.2f}s dead air",
                priority="medium", confidence=0.7,
                evidence=[asdict(_ev("silence_span", "audio", float(d["start"]),
                                     float(d["end"]), "duration_s",
                                     round(float(d["end"]) - float(d["start"]), 3),
                                     style.silence_tolerance_s,
                                     "approved silence removal"))]))
    fillers = [w for w in transcript_words if w["is_filler"]]
    if fillers:
        out.append(AudioRecommendation(
            kind="filler_removal",
            detail=f"{len(fillers)} annotated filler words (removal per EDL policy)",
            priority="low", confidence=0.6,
            evidence=[asdict(_ev("filler_count", "transcript", 0,
                                 max(w["end"] for w in fillers), "count",
                                 len(fillers), 0, "annotated fillers"))]))
    loud = (audio.get("loudness", {}) or {})
    try:
        level = float(loud.get("input_i", "nan"))
    except (TypeError, ValueError):
        level = float("nan")
    if level == level:  # not NaN: measured
        ok = abs(level - (-16.0)) <= 2.0
        out.append(AudioRecommendation(
            kind="dialogue_leveling" if not ok else "levels_ok",
            detail=f"integrated loudness {level:.1f} LUFS",
            priority="medium" if not ok else "informational",
            confidence=0.6,
            evidence=[asdict(_ev("loudness", "audio", 0,
                                 float(audio.get("audio_duration", 0) or 0),
                                 "input_i_lufs", level, -16.0,
                                 "within podcast target" if ok else
                                 "outside -16±2 LUFS target"))]))
    for w in transcript_words:
        if w["terminal"]:
            nxt = [s for s in (audio.get("silence", []) or [])
                   if float(s["start"]) >= w["end"] - 1e-6
                   and float(s["start"]) - w["end"] < 1.5]
            for s in nxt[:1]:
                out.append(AudioRecommendation(
                    kind="preserve_pause", start=float(s["start"]), end=float(s["end"]),
                    detail="pause after sentence completion: preserve",
                    priority="low", confidence=0.65,
                    evidence=[asdict(_ev("sentence_pause", "transcript",
                                         float(s["start"]), float(s["end"]),
                                         "pause_s", float(s.get("duration", 0)),
                                         0, "intentional-feeling pause"))]))
                break
    out.append(AudioRecommendation(
        kind="later_phase",
        detail="music presence not measured by current analysis; ducking assessment deferred",
        priority="informational", confidence=0.3,
        evidence=[asdict(_ev("unmeasured", "audio", 0, 0, "music_detected",
                             "unknown", "n/a", "no music detector in this phase"))]))
    out.append(AudioRecommendation(
        kind="later_phase",
        detail="noise cleanup deferred to audio engine phase",
        priority="informational", confidence=0.3,
        evidence=[asdict(_ev("unmeasured", "audio", 0, 0, "noise_profile",
                             "unknown", "n/a", "no noise profiler in this phase"))]))
    return out


def editorial_repetitions(intel: dict | None, style: StyleProfile) -> list[EditorialRepetition]:
    out: list[EditorialRepetition] = []
    for r in (intel.get("repetitions", []) if intel else []):
        action = {"keep": "keep", "investigate": "investigate",
                  "trim_candidate": "candidate_for_trim"}[style.repetition_policy]
        out.append(EditorialRepetition(
            text=r.get("text", ""), spans=r.get("spans", []),
            similarity=float(r.get("similarity", 1.0)),
            confidence=float(r.get("confidence", 0.6)),
            editorial_reason=(f"style {style.name} policy={style.repetition_policy}; "
                              "removal requires conservative evidence"),
            recommended_action=action,
            evidence=r.get("evidence", [])))
    return out


# ---------------- PASS 6: conflicts ----------------

def resolve_conflict(pro: list[dict], con: list[dict],
                     order: tuple = PRINCIPLE_ORDER) -> ConflictResolution:
    """Winner = side holding the highest-ranked principle. Explicit, no ties
    broken silently: first side wins only on equal rank (documented)."""
    def best(signals):
        return min((order.index(s.get("principle", order[-1])) for s in signals),
                   default=len(order))
    pro_rank, con_rank = best(pro), best(con)
    if con_rank <= pro_rank:
        winner, principle = "keep", order[con_rank] if con_rank < len(order) else order[-1]
    else:
        winner, principle = "cut", order[pro_rank]
    return ConflictResolution(
        topic=(pro + con)[0].get("topic", "edit") if (pro + con) else "edit",
        pro_signals=pro, con_signals=con, winner=winner, principle=principle,
        explanation=(f"{principle} outranks the opposing signals "
                     f"({PRINCIPLE_ORDER}); meaning is never sacrificed for frequency"))


# ---------------- PASS 8: assembly + project ----------------

def _versions() -> dict:
    import platform
    return {"python": platform.python_version(), "engine": "0.1.0"}


def _code_hash() -> str:
    """Hash of this module's source: engine edits invalidate the cache
    automatically (a stale plan from older logic must never be served)."""
    import hashlib
    try:
        return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()[:16]
    except OSError:
        return "unknown"


def build_editor_plan(audio: dict, transcript: dict, scenes: dict, edl: dict,
                      intel: dict | None, visual: dict | None, refined: dict | None,
                      duration: float, style: StyleProfile) -> ProfessionalEditPlan:
    """Pure assembly of all passes. Raises BrainError on missing core inputs."""
    t0 = time.perf_counter()
    for name, payload, need in (("audio", audio, "silence"), ("transcript", transcript, "segments"),
                                ("scenes", scenes, "scenes"), ("edl", edl, "decisions")):
        if not isinstance(payload, dict) or need not in payload:
            raise BrainError(f"missing/invalid {name} analysis (need {need})")
    if duration <= 0:
        raise BrainError(f"invalid duration {duration}")
    words, _ = _words(transcript)
    scene_bounds = sorted(scenes.get("scenes", []),
                          key=lambda s: (s["start"], s["end"]))
    silences = [{"start": float(s["start"]), "end": float(s["end"]),
                 "duration": float(s.get("duration", float(s["end"]) - float(s["start"])))}
                for s in audio.get("silence", [])]
    hook = analyze_hook(words, silences, duration, style)
    story = story_structure(words, scene_bounds, duration)
    reps = [asdict(r) if hasattr(r, "__dataclass_fields__") else r
            for r in ((intel.get("repetitions", []) or []) if intel else [])]
    density = density_windows(words, silences, scene_bounds, reps, duration)
    pacing = pacing_analysis(scene_bounds, density, visual, words, style, duration)
    cuts, conflicts = plan_cuts(edl, intel, visual, words, scene_bounds, style)
    # Cross-check against the Phase 10 refined EDL (read-only): flag places
    # where the brain disagrees with what refinement kept. The brain never
    # mutates either EDL.
    if refined:
        ref_action = {}
        for d in refined.get("decisions", []):
            prov = (d.get("metadata", {}) or {}).get("provenance", {}) or {}
            key = prov.get("original_id") or d.get("decision_id")
            ref_action[key] = d.get("action")
        for c in cuts:
            if c.verdict in ("reject", "downgrade_keep") and \
                    ref_action.get(c.decision_id) == "REMOVE":
                conflicts.append(ConflictResolution(
                    topic=f"cut {c.decision_id}",
                    pro_signals=[{"signal": "refined_edl_keeps_removal",
                                  "principle": "content_value"}],
                    con_signals=[{"signal": f"brain_{c.verdict}",
                                  "principle": "edit_safety"}],
                    winner="keep", principle="edit_safety",
                    explanation=("brain rejects a removal the refined EDL kept; "
                                 "re-run edit or accept brain verdict before rendering")))
    jumps = jump_strategy(((intel.get("jump_cuts", []) or []) if intel else []), style)
    medians = [float(s["end"]) - float(s["start"]) for s in scene_bounds]
    median_scene = statistics.median(medians) if medians else 0.0
    broll = broll_opportunities(scene_bounds, words, visual,
                                ((intel.get("jump_cuts", []) or []) if intel else []),
                                median_scene, style, duration)
    vplan = visual_change_plan(scene_bounds, broll, visual)
    aplan = audio_plan(audio, words, edl, style)
    ereps = editorial_repetitions(intel, style)
    risks: list[QualityRisk] = []
    low_runs = _low_runs(density)
    for start, end in low_runs:
        if end - start >= 15.0:
            risks.append(QualityRisk(
                kind="attention_risk", start=start, end=end, priority="low",
                confidence=0.45,
                evidence=[asdict(_ev("low_density_stretch", "transcript", start, end,
                                     "duration_s", round(end - start, 1), 15.0,
                                     "long low-information stretch"))]))
    for b in broll:
        if b.duration >= 6.0:
            risks.append(QualityRisk(
                kind="visual_stagnation", start=b.start, end=b.end, priority="low",
                confidence=0.5, evidence=b.evidence))
    for r in ereps:
        risks.append(QualityRisk(
            kind="repetition_risk", start=r.spans[0]["start"], end=r.spans[-1]["end"],
            priority="low", confidence=0.5, evidence=r.evidence if isinstance(r.evidence, list) else []))
    ranked = sorted(
        [{"category": "cut", "ref": c.decision_id, "start": c.start,
          "priority": c.priority, "confidence": c.confidence} for c in cuts] +
        [{"category": "broll", "ref": f"{b.start}-{b.end}", "start": b.start,
          "priority": b.priority, "confidence": b.confidence} for b in broll],
        key=lambda r: (PRIORITY_RANK.get(r["priority"], 4), -r["confidence"], r["start"]))
    plan = ProfessionalEditPlan(
        source=str(edl.get("source", "")), duration=_r6(duration),
        editing_style=style, hook=hook, story_structure=story,
        density_windows=density, pacing_analysis=pacing, cut_plan=cuts,
        jump_strategy=jumps, broll_plan=broll, visual_change_plan=vplan,
        audio_plan=aplan, repetition_candidates=ereps,
        quality_risks=risks, conflicts=conflicts)
    plan.evidence_index = [
        {"category": "cut", "count": len(cuts)},
        {"category": "broll", "count": len(broll)},
        {"category": "risks", "count": len(risks)}]
    plan.processing_s = round(time.perf_counter() - t0, 3)
    return plan


def _low_runs(density: list[DensityWindow]) -> list[tuple[float, float]]:
    runs, cur = [], None
    for w in density:
        if w.density == "low":
            cur = (cur[0], w.end) if cur else (w.start, w.end)
        else:
            if cur:
                runs.append(cur)
                cur = None
    if cur:
        runs.append(cur)
    return runs


def _project_audio_only(pid: str, input_path: str) -> bool:
    """Mirror of the Phase 8 rule: media_info without video stream (or a
    probe fallback) means audio-only. Unknown -> False (fail loudly)."""
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


def run_editor_brain_for_project(project_id: str,
                                 style_name: str = "general",
                                 target_duration: float | None = None,
                                 aggressive: bool = False) -> dict:
    """Load cached analyses, plan, cache, log. No rendering, no downloads."""
    import json
    project = load_project(project_id)
    pid = project.id
    log_file = project_dir(pid) / "logs" / "run.jsonl"
    style = resolve_style(style_name, target_duration, aggressive)

    def _load(name: str, required: bool = True) -> dict | None:
        p = project_dir(pid) / "analysis" / name
        if not p.is_file():
            if required:
                raise BrainError(f"missing analysis artifact analysis/{name}")
            return None
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise BrainError(f"corrupt analysis artifact analysis/{name}: {exc}") from exc

    def _load_from(subdir: str, name: str, required: bool = True) -> dict | None:
        # Artifacts live where their phase wrote them (edit/, visual/);
        # analysis/ is kept as a legacy fallback location.
        for loc in (subdir, "analysis"):
            p = project_dir(pid) / loc / name
            if p.is_file():
                try:
                    return json.loads(p.read_text(encoding="utf-8"))
                except json.JSONDecodeError as exc:
                    raise BrainError(f"corrupt artifact {loc}/{name}: {exc}") from exc
        if required:
            raise BrainError(f"missing analysis artifact {subdir}/{name}")
        return None

    audio = _load("audio_analysis.json")
    transcript = _load("transcript.json")
    try:
        scenes = _load("scenes.json")
        synth_warning = ""
    except BrainError:
        # Audio-only sources have no visual timeline (same rule as Phase 8):
        # synthesize the degenerate single scene with a recorded warning.
        if _project_audio_only(pid, project.input_path):
            duration = float(audio.get("audio_duration") or 0)
            scenes = {"duration": duration,
                      "scenes": [{"scene_id": 0, "start": 0.0, "end": duration,
                                  "duration": duration, "start_frame": 0, "end_frame": 0}]}
            synth_warning = ("audio-only input: no scenes.json; single "
                             "[0, duration] scene assumed")
        else:
            raise BrainError("missing analysis artifact analysis/scenes.json")
    edl_path = project_dir(pid) / "edit" / "edit_decision.json"
    if not edl_path.is_file():
        raise BrainError("missing base EDL edit/edit_decision.json (run edit first)")
    try:
        edl = json.loads(edl_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise BrainError(f"corrupt base EDL: {exc}") from exc
    intel = _load_from("edit", "edit_intelligence.json", required=False)
    refined = _load_from("edit", "refined_edit_decision.json", required=False)
    visual = _load_from("visual", "visual_analysis.json", required=False)
    duration = float(edl.get("duration") or 0)
    if duration <= 0:
        raise BrainError("base EDL has no usable duration")

    from engine.editing.decisions import hash_analysis
    from engine.rendering.execution import edl_hash
    refs = {"audio": hash_analysis(audio), "transcript": hash_analysis(transcript),
            "scenes": hash_analysis(scenes), "edl": edl_hash(edl)}
    if intel:
        refs["intel"] = hash_analysis(intel)
    if visual:
        refs["visual"] = hash_analysis(visual)
    key = cache_key(project.input_path, "editor_plan",
                    {**refs, "style": asdict(style),
                     "brain_version": BRAIN_VERSION, "code_hash": _code_hash()})
    t0 = time.perf_counter()
    hit = cached(key)
    if hit is not None:
        payload = json.loads(hit.read_text(encoding="utf-8"))
        payload["cached"] = True
        write_artifact(pid, "editing", "editor_plan.json", payload)
        mark_stage(project, "editor_plan", "cached", "editing/editor_plan.json")
        log_event(log_file, "editor_plan", "plan", "cached",
                  time.perf_counter() - t0, "editing/editor_plan.json",
                  _versions(), {"style": style.name,
                                "cuts": len(payload.get("cut_plan", [])),
                                "broll": len(payload.get("broll_plan", []))})
        return {"project": pid, "cached": True, "plan": payload}

    plan = build_editor_plan(audio, transcript, scenes, edl, intel, visual,
                             refined, duration, style)
    if synth_warning:
        plan.warnings.insert(0, synth_warning)
    payload = asdict(plan)
    write_artifact(pid, "editing", "editor_plan.json", payload)
    store(key, payload)
    mark_stage(project, "editor_plan", "done", "editing/editor_plan.json")
    log_event(log_file, "editor_plan", "plan", "ok",
              time.perf_counter() - t0, "editing/editor_plan.json",
              _versions(), {"style": style.name,
                            "cuts": len(plan.cut_plan),
                            "broll": len(plan.broll_plan),
                            "risks": len(plan.quality_risks)})
    return {"project": pid, "cached": False, "plan": payload}
