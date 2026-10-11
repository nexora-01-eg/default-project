"""Phase 8 — edit decision engine: ANALYSIS -> DECISIONS -> EDL.

Pure timeline math on the ORIGINAL source coordinates (never renumbered,
never rendered). No FFmpeg, no model, no network in this module.

Precedence (deterministic):
  1. INVALID / UNSAFE          -> KEEP (+ warning)
  2. MEANINGFUL SPEECH overlap -> KEEP (+ warning)
  3. FILLER removal (priority 3)
  4. LONG SILENCE removal (priority 4, minus filler spans)
  5. default                   -> KEEP

Only two removal rules exist, so conflicts resolve by subtracting placed
filler spans from silence spans. (Revisit with a general sweep if a third
removal rule ever lands.)
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict
from pathlib import Path

from engine.analysis.fillers import filler_set, normalize_token
from engine.core import config as config_mod
from engine.core.logging_utils import log_event
from engine.core.models import KEEP, REMOVE, EditDecision, EditDecisionList
from engine.core.pipeline import cache_key, cached, store
from engine.core.project_store import (
    load_project,
    mark_stage,
    project_dir,
    write_artifact,
)

POLICY_KEYS = ("edit_min_silence_s", "edit_silence_pad_before",
               "edit_silence_pad_after", "edit_remove_fillers",
               "edit_filler_pad_s", "edit_min_removal_s")

_EPS = 1e-6


class EditError(RuntimeError):
    pass


def resolve_policy(overrides: dict | None = None) -> dict:
    cfg = config_mod.resolve(overrides=overrides)
    policy = {k: cfg[k] for k in POLICY_KEYS}
    for key in ("edit_min_silence_s", "edit_silence_pad_before",
                "edit_silence_pad_after", "edit_filler_pad_s",
                "edit_min_removal_s"):
        try:
            policy[key] = float(policy[key])
        except (TypeError, ValueError):
            raise EditError(f"policy {key} must be a number (got {policy[key]!r})") from None
        if policy[key] < 0:
            raise EditError(f"policy {key} must be >= 0 (got {policy[key]})")
    if policy["edit_min_silence_s"] <= 0:
        raise EditError("policy edit_min_silence_s must be > 0")
    if policy["edit_min_removal_s"] <= 0:
        raise EditError("policy edit_min_removal_s must be > 0")
    policy["edit_remove_fillers"] = bool(policy["edit_remove_fillers"])
    return policy


def hash_analysis(payload: dict) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()[:32]


def _r6(x: float) -> float:
    return round(float(x), 6)


class _Removal:
    __slots__ = ("start", "end", "reason", "confidence", "word_refs",
                 "scene_id", "priority", "metadata")

    def __init__(self, start, end, reason, confidence, word_refs=None,
                 scene_id=-1, priority=9, metadata=None):
        self.start = _r6(start)
        self.end = _r6(end)
        self.reason = reason
        self.confidence = round(float(confidence), 3)
        self.word_refs = word_refs or []
        self.scene_id = scene_id
        self.priority = priority
        self.metadata = metadata or {}


def _overlap(a_start: float, a_end: float, b_start: float, b_end: float) -> float:
    return min(a_end, b_end) - max(a_start, b_start)


def _subtract_span(span: tuple[float, float],
                   cutters: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Subtract cutter spans from span. Deterministic, order-independent."""
    frags = [span]
    for c_start, c_end in sorted(cutters):
        out = []
        for f_start, f_end in frags:
            if c_end <= f_start + _EPS or c_start >= f_end - _EPS:
                out.append((f_start, f_end))
                continue
            if c_start > f_start + _EPS:
                out.append((f_start, c_start))
            if c_end < f_end - _EPS:
                out.append((c_end, f_end))
        frags = out
    return [( _r6(s), _r6(e)) for s, e in frags if e - s > _EPS]


def build_edl(audio: dict, transcript: dict | None, scenes: dict | None,
              duration: float, policy: dict) -> EditDecisionList:
    """Build the EDL from analysis dicts. Raises EditError (never invents)."""
    warnings: list[str] = []
    if not isinstance(audio, dict) or not isinstance(audio.get("silence"), list):
        raise EditError("missing/invalid audio analysis (need silence[])")
    if not isinstance(transcript, dict) or "segments" not in transcript:
        raise EditError("missing/invalid transcript analysis")
    if not isinstance(scenes, dict) or not scenes.get("scenes"):
        raise EditError("missing/invalid scene analysis (need scenes[])")
    try:
        duration = float(duration)
    except (TypeError, ValueError):
        raise EditError(f"invalid duration {duration!r}") from None
    if duration <= 0:
        raise EditError(f"invalid duration {duration}")

    scene_list = sorted(scenes["scenes"], key=lambda s: (s["start"], s["end"]))
    language = transcript.get("language", "") or ""
    fillers_supported = filler_set(language)

    # Meaningful speech = transcript words that are NOT fillers.
    speech_spans: list[tuple[float, float]] = []
    word_prob: dict[tuple, float] = {}
    for seg in transcript.get("segments", []):
        for w in seg.get("words", []) or []:
            try:
                ws, we = float(w["start"]), float(w["end"])
            except (KeyError, TypeError, ValueError):
                warnings.append(f"invalid word timestamps in segment {seg.get('id')}: kept")
                continue
            if not we > ws:
                warnings.append(f"invalid word span [{ws},{we}]: kept")
                continue
            norm = normalize_token(str(w.get("word", "")))
            if not norm:
                continue
            if norm in fillers_supported:
                word_prob[(seg.get("id"), norm, round(ws, 3))] = float(w.get("probability", 0.8) or 0.8)
            else:
                speech_spans.append((ws, we))

    filler_removals: list[_Removal] = []
    if policy["edit_remove_fillers"]:
        pad = policy["edit_filler_pad_s"]
        for f in transcript.get("fillers", []) or []:
            try:
                fs, fe = float(f["start"]), float(f["end"])
            except (KeyError, TypeError, ValueError):
                warnings.append(f"invalid filler timestamps {f}: kept")
                continue
            if not fe > fs:
                warnings.append(f"invalid filler span [{fs},{fe}]: kept")
                continue
            start, end = _r6(max(0.0, fs - pad)), _r6(min(duration, fe + pad))
            if not end > start:
                warnings.append(f"filler span vanished after padding [{fs},{fe}]: kept")
                continue
            if any(_overlap(start, end, ss, se) > _EPS for ss, se in speech_spans):
                warnings.append(
                    f"filler {f.get('word')!r} [{fs},{fe}] overlaps speech: kept")
                continue
            prob = word_prob.get((f.get("segment_id"),
                                  normalize_token(str(f.get("word", ""))),
                                  round(fs, 3)), 0.8)
            filler_removals.append(_Removal(
                start, end, "filler_word", prob,
                word_refs=[{"word": f.get("word"), "start": fs, "end": fe,
                            "segment_id": f.get("segment_id")}],
                priority=3, metadata={"filler": f.get("word")}))

    silence_removals: list[_Removal] = []
    min_sil = policy["edit_min_silence_s"]
    min_rem = policy["edit_min_removal_s"]
    filler_cutters = [(r.start, r.end) for r in filler_removals]
    for s in audio.get("silence", []) or []:
        try:
            ss, se = float(s["start"]), float(s["end"])
        except (KeyError, TypeError, ValueError):
            warnings.append(f"invalid silence span {s}: kept")
            continue
        if not se > ss:
            warnings.append(f"invalid silence span [{ss},{se}]: kept")
            continue
        if (se - ss) < min_sil - _EPS:
            continue  # tiny natural pause: keep (no warning; by design)
        interior = (_r6(ss + policy["edit_silence_pad_before"]),
                    _r6(se - policy["edit_silence_pad_after"]))
        if interior[1] - interior[0] < min_rem - _EPS:
            continue  # padding consumed it: keep
        conf = min(0.99, 0.70 + 0.10 * ((se - ss) - min_sil))
        for frag_start, frag_end in _subtract_span(interior, filler_cutters):
            if frag_end - frag_start < min_rem - _EPS:
                continue
            silence_removals.append(_Removal(
                frag_start, frag_end, "long_silence", conf, priority=4,
                metadata={"silence_start": ss, "silence_end": se}))

    # Scene-aware split (traceability; never cut across boundaries silently).
    split: list[_Removal] = []
    for r in filler_removals + silence_removals:
        for sc in scene_list:
            try:
                cs, ce = float(sc["start"]), float(sc["end"])
            except (KeyError, TypeError, ValueError):
                continue
            lo, hi = max(r.start, cs), min(r.end, ce)
            if hi - lo >= min_rem - _EPS:
                split.append(_Removal(lo, hi, r.reason, r.confidence,
                                      word_refs=r.word_refs, scene_id=int(sc.get("scene_id", -1)),
                                      priority=r.priority, metadata=r.metadata))
    split.sort(key=lambda r: (r.start, r.priority))

    # Merge adjacent identical (action implied REMOVE; reason+scene must match
    # so scene traceability is never blurred).
    merged: list[_Removal] = []
    for r in split:
        if (merged and merged[-1].reason == r.reason
                and merged[-1].scene_id == r.scene_id
                and r.start <= merged[-1].end + _EPS):
            merged[-1].end = _r6(max(merged[-1].end, r.end))
            merged[-1].confidence = round(min(merged[-1].confidence, r.confidence), 3)
            merged[-1].word_refs = merged[-1].word_refs + r.word_refs
        else:
            merged.append(r)

    # Walk the source timeline: gaps stay KEEP.
    decisions: list[EditDecision] = []
    cursor = 0.0
    seq = 0

    def _emit(start: float, end: float, action: str, reason: str,
              confidence: float, scene_id: int, word_refs: list, metadata: dict):
        nonlocal seq
        if end - start <= _EPS:
            return
        seq += 1
        decisions.append(EditDecision(
            decision_id=f"edl_{seq:04d}", start=_r6(start), end=_r6(end),
            action=action, reason=reason, confidence=round(float(confidence), 3),
            scene_id=scene_id, word_refs=word_refs, metadata=metadata))

    def _scene_at(t: float) -> int:
        for sc in scene_list:
            try:
                if float(sc["start"]) - _EPS <= t < float(sc["end"]) - _EPS:
                    return int(sc.get("scene_id", -1))
            except (KeyError, TypeError, ValueError):
                continue
        return int(scene_list[-1].get("scene_id", -1)) if scene_list else -1

    for r in merged:
        if r.start > cursor + _EPS:
            _emit(cursor, r.start, KEEP, "default", 1.0, _scene_at(cursor), [], {})
        _emit(r.start, r.end, REMOVE, r.reason, r.confidence, r.scene_id,
              r.word_refs, r.metadata)
        cursor = max(cursor, r.end)
    if cursor < duration - _EPS:
        _emit(cursor, duration, KEEP, "default", 1.0, _scene_at(cursor), [], {})

    kept = round(sum(d.end - d.start for d in decisions if d.action == KEEP), 6)
    removed = round(sum(d.end - d.start for d in decisions if d.action == REMOVE), 6)
    edl = EditDecisionList(
        source=str(audio.get("path", "")),
        duration=_r6(duration),
        decisions=decisions,
        decision_count=len(decisions),
        kept_duration=kept,
        removed_duration=removed,
        removal_ratio=round(removed / duration, 6) if duration > 0 else 0.0,
        policy={k: policy[k] for k in POLICY_KEYS},
        warnings=warnings)
    return edl


def _versions() -> dict:
    import platform
    return {"python": platform.python_version(), "engine": "0.1.0"}


def _project_has_video(pid: str, input_path: str) -> bool:
    """True if the source has a video stream (media_info artifact or probe)."""
    import json
    media = project_dir(pid) / "analysis" / "media_info.json"
    if media.is_file():
        try:
            if json.loads(media.read_text(encoding="utf-8")).get("video_codec"):
                return True
        except (json.JSONDecodeError, AttributeError):
            pass
    try:
        from engine.core.media import probe
        return bool(probe(input_path).video_codec)
    except Exception:
        return True  # unknown -> strict path (fail loudly, don't assume audio-only)


def build_edl_for_project(project_id: str,
                          policy_overrides: dict | None = None) -> dict:
    """Load analysis artifacts, build EDL, cache, log. Returns {project, cached, edl}."""
    import json
    project = load_project(project_id)
    pid = project.id
    log_file = project_dir(pid) / "logs" / "run.jsonl"
    policy = resolve_policy(policy_overrides)

    def _load(name: str) -> dict:
        p = project_dir(pid) / "analysis" / name
        if not p.is_file():
            raise EditError(f"missing analysis artifact analysis/{name} "
                            f"(run analyze/transcribe/scenes first)")
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise EditError(f"corrupt analysis artifact analysis/{name}: {exc}") from exc

    audio = _load("audio_analysis.json")
    transcript = _load("transcript.json")
    try:
        scenes = _load("scenes.json")
        synth_note = ""
    except EditError:
        # Audio-only sources have no visual timeline: the degenerate single
        # scene is the truthful normalization (cf. Phase 7 zero-cut rule),
        # recorded as a warning. Video sources without scenes fail loudly.
        if _project_has_video(pid, project.input_path):
            raise EditError("missing analysis artifact analysis/scenes.json "
                            "(run scenes first)")
        duration = float(audio.get("audio_duration") or 0)
        if duration <= 0:
            raise EditError("cannot determine media duration from analysis artifacts")
        scenes = {"duration": duration,
                  "scenes": [{"scene_id": 0, "start": 0.0, "end": duration,
                              "duration": duration, "start_frame": 0, "end_frame": 0}]}
        synth_note = ("audio-only input: no scenes.json; single [0, duration] "
                      "scene assumed")
    duration = float(scenes.get("duration") or audio.get("audio_duration") or 0)
    if duration <= 0:
        media = project_dir(pid) / "analysis" / "media_info.json"
        if media.is_file():
            try:
                duration = float(json.loads(media.read_text(encoding="utf-8")).get("duration", 0))
            except (json.JSONDecodeError, TypeError, ValueError):
                duration = 0
    if duration <= 0:
        raise EditError("cannot determine media duration from analysis artifacts")

    refs = {"audio": hash_analysis(audio), "transcript": hash_analysis(transcript),
            "scenes": hash_analysis(scenes)}
    key = cache_key(project.input_path, "edit_decision", {**policy, **refs})
    t0 = time.perf_counter()
    hit = cached(key)
    if hit is not None:
        payload = json.loads(hit.read_text(encoding="utf-8"))
        payload["cached"] = True
        write_artifact(pid, "edit", "edit_decision.json", payload)
        mark_stage(project, "edit", "cached", "edit/edit_decision.json")
        log_event(log_file, "edit", "decide", "cached", time.perf_counter() - t0,
                  "edit/edit_decision.json", _versions(),
                  {"decisions": payload.get("decision_count", 0),
                   "removed_s": payload.get("removed_duration", 0)})
        return {"project": pid, "cached": True, "edl": payload}

    try:
        edl = build_edl(audio, transcript, scenes, duration, policy)
    except EditError as exc:
        mark_stage(project, "edit", "failed", str(exc)[:300])
        log_event(log_file, "edit", "decide", "failed", time.perf_counter() - t0,
                  str(exc)[:300], _versions(), {})
        raise
    if synth_note:
        edl.warnings.insert(0, synth_note)
    edl.analysis_refs = refs
    payload = asdict(edl)
    write_artifact(pid, "edit", "edit_decision.json", payload)
    store(key, payload)
    mark_stage(project, "edit", "done", "edit/edit_decision.json")
    log_event(log_file, "edit", "decide", "ok", time.perf_counter() - t0,
              "edit/edit_decision.json", _versions(),
              {"decisions": edl.decision_count, "removed_s": edl.removed_duration,
               "removal_ratio": edl.removal_ratio, "warnings": len(edl.warnings)})
    return {"project": pid, "cached": False, "edl": payload}
