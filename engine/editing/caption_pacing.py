"""Phase 16 — caption-aware scene pacing intelligence (analysis only).

Reads verified artifacts, emits signals + conservative recommendations +
an approval artifact. NEVER renders, mutates EDLs, moves captions, fetches
media, or downloads models. KEEP is the default whenever evidence is
insufficient; story continuity outranks pacing, always.
"""
from __future__ import annotations

import statistics
import time
from dataclasses import asdict
from pathlib import Path

from engine.core import config as config_mod
from engine.core.logging_utils import log_event
from engine.core.models import (
    CaptionPacingContext,
    CaptionPacingPlan,
    PacingRecommendation,
    PacingSignal,
)
from engine.core.pipeline import cache_key, cached, store
from engine.core.project_store import (
    load_project,
    mark_stage,
    project_dir,
    write_artifact,
)

_VOLATILE_KEYS = ("cached", "processing_s", "generated_at", "realtime_factor")


def _stable(obj):
    """Strip wall-clock/cache metadata recursively for stable hashing."""
    if isinstance(obj, dict):
        return {k: _stable(v) for k, v in sorted(obj.items())
                if k not in _VOLATILE_KEYS}
    if isinstance(obj, list):
        return [_stable(v) for v in obj]
    return obj


def _stable_hash(payload: dict | None) -> str:
    import hashlib
    import json as _json
    return hashlib.sha256(_json.dumps(_stable(payload or {}), sort_keys=True,
                                      default=str).encode()).hexdigest()[:32]

PACING_VERSION = "1.0.0"
ENGINE_TAG = "phase16-1.0"

SIGNAL_TYPES = (
    "LONG_VISUAL_SECTION",
    "HIGH_CAPTION_DENSITY",
    "LOW_CAPTION_DENSITY",
    "RAPID_CAPTION_SEQUENCE",
    "LONG_SPEECH_BLOCK",
    "LONG_SILENCE",
    "STATIC_VISUAL",
    "HIGH_VISUAL_CHANGE",
    "CAPTION_PLACEMENT_CONFLICT",
    "CAPTION_CONTRAST_CAUTION",
    "SCENE_BOUNDARY_OPPORTUNITY",
    "NATURAL_PAUSE",
    "SENTENCE_BOUNDARY",
    "EDIT_SAFETY_CAUTION",
    "EDIT_SAFETY_UNSAFE",
)
ACTIONS = ("KEEP", "TRIM", "SPLIT", "ACCELERATE_VISUAL", "HOLD_LONGER",
           "CHANGE_VISUAL", "ADD_CUTAWAY_OPPORTUNITY", "REVIEW")
PRINCIPLE_ORDER = ("story_continuity", "edit_safety", "content_value",
                   "visual_quality", "pacing")
PRIORITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3,
                 "informational": 4}
ACTION_SAFETY_RANK = {"KEEP": 0, "HOLD_LONGER": 1, "REVIEW": 2,
                      "ADD_CUTAWAY_OPPORTUNITY": 3, "CHANGE_VISUAL": 3,
                      "ACCELERATE_VISUAL": 3, "SPLIT": 4, "TRIM": 5}
PACING_KEYS = ("pacing_caption_cps_fast", "pacing_caption_cps_extreme",
               "pacing_caption_gap_long", "pacing_caption_words_per_cue_high",
               "pacing_caption_density_window", "pacing_pause_s",
               "pacing_static_motion_thr", "pacing_long_scene_ratio")
TERMINAL_PUNCT = (".", "?", "!", "…", "؟", "。")


class PacingError(RuntimeError):
    pass


def _r6(x: float) -> float:
    return round(float(x), 6)


def _r3(x: float) -> float:
    return round(float(x), 3)


def _overlap(a_start: float, a_end: float, b_start: float, b_end: float) -> float:
    return min(a_end, b_end) - max(a_start, b_start)


def _ev(evidence_type: str, source: str, start: float, end: float,
        metric: str, value, threshold, explanation: str) -> dict:
    return {"evidence_type": evidence_type, "source": source,
            "start": _r6(start), "end": _r6(end), "metric": metric,
            "value": value, "threshold": threshold, "explanation": explanation}


def _versions() -> dict:
    import platform
    return {"python": platform.python_version(), "engine": "0.1.0"}


def _code_hash() -> str:
    import hashlib
    try:
        return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()[:16]
    except OSError:
        return "unknown"


def resolve_pacing_config(overrides: dict | None = None) -> dict:
    if overrides:
        unknown = sorted(set(overrides) - set(PACING_KEYS))
        if unknown:
            raise PacingError(f"unknown pacing config keys: {unknown}")
    cfg = config_mod.resolve(overrides=overrides)
    out = {k: cfg[k] for k in PACING_KEYS}
    for key in PACING_KEYS:
        try:
            out[key] = float(out[key])
        except (TypeError, ValueError):
            raise PacingError(f"{key} must be a number") from None
    if out["pacing_caption_cps_fast"] <= 0 or out["pacing_caption_cps_extreme"] <= 0:
        raise PacingError("CPS thresholds must be > 0")
    if out["pacing_caption_cps_extreme"] < out["pacing_caption_cps_fast"]:
        raise PacingError("cps_extreme must be >= cps_fast")
    if out["pacing_pause_s"] <= 0:
        raise PacingError("pacing_pause_s must be > 0")
    if out["pacing_caption_gap_long"] <= 0:
        raise PacingError("pacing_caption_gap_long must be > 0")
    if out["pacing_caption_words_per_cue_high"] < 1:
        raise PacingError("pacing_caption_words_per_cue_high must be >= 1")
    if out["pacing_caption_density_window"] <= 0:
        raise PacingError("pacing_caption_density_window must be > 0")
    if out["pacing_static_motion_thr"] < 0:
        raise PacingError("pacing_static_motion_thr must be >= 0")
    if out["pacing_long_scene_ratio"] < 1.0:
        raise PacingError("pacing_long_scene_ratio must be >= 1.0")
    return out


def _adapt_thresholds(base: dict, style_name: str) -> tuple[dict, list[dict]]:
    """Bounded documented style adaptation. Returns (thresholds, applied)."""
    adapted, notes = dict(base), []

    def _set(key: str, value: float, why: str):
        if adapted[key] != value:
            adapted[key] = value
            notes.append({"key": key, "value": value, "reason": why})

    if style_name == "social_short":
        _set("pacing_caption_cps_fast", base["pacing_caption_cps_fast"] - 3.0,
             "brisk style: denser caption tolerance")
        _set("pacing_caption_cps_extreme", base["pacing_caption_cps_extreme"] - 3.0,
             "brisk style: denser caption tolerance")
        _set("pacing_caption_gap_long", max(0.4, base["pacing_caption_gap_long"] - 0.4),
             "brisk style: shorter patience for gaps")
        _set("pacing_pause_s", round(max(0.3, base["pacing_pause_s"] - 0.2), 2),
             "brisk style: shorter pauses qualify")
        _set("pacing_caption_density_window",
             max(1.5, base["pacing_caption_density_window"] - 1.0),
             "brisk style: tighter density window")
        _set("pacing_long_scene_ratio",
             max(1.2, base["pacing_long_scene_ratio"] - 0.5),
             "brisk style: shorter scenes count as long")
    elif style_name in ("podcast", "documentary", "cinematic"):
        _set("pacing_caption_cps_fast", base["pacing_caption_cps_fast"] + 3.0,
             "relaxed style: higher density tolerance")
        _set("pacing_caption_gap_long", base["pacing_caption_gap_long"] + 0.6,
             "relaxed style: longer patience for gaps")
        _set("pacing_pause_s", round(base["pacing_pause_s"] + 0.3, 2),
             "relaxed style: only longer pauses qualify")
    return adapted, notes


def _words(transcript: dict | None) -> list[dict]:
    out: list[dict] = []
    for seg in (transcript.get("segments", []) or []) if transcript else []:
        for idx, w in enumerate(seg.get("words", []) or []):
            try:
                ws, we = float(w["start"]), float(w["end"])
            except (KeyError, TypeError, ValueError):
                continue
            if not we > ws:
                continue
            text = str(w.get("word", ""))
            if not text.strip():
                continue
            out.append({"word": text, "norm": text.strip().lower(),
                        "start": ws, "end": we, "segment_id": seg.get("id"),
                        "probability": float(w.get("probability", 0.0) or 0.0),
                        "terminal": text.rstrip().endswith(TERMINAL_PUNCT)})
    out.sort(key=lambda x: (x["start"], x["end"]))
    return out


def _scene_list(scenes: dict) -> list[dict]:
    return sorted((scenes.get("scenes", []) or []),
                  key=lambda s: (float(s["start"]), float(s["end"])))


# ---------------- signal extraction (pure) ----------------

def _extract_caption_signals(cues: list[dict], cfg: dict) -> list[PacingSignal]:
    sigs: list[PacingSignal] = []
    seq = 0

    def _emit(stype, s, e, sid, sev, conf, ev, metrics, refs):
        nonlocal seq
        seq += 1
        sigs.append(PacingSignal(
            signal_id=f"sig_{seq:04d}", signal_type=stype,
            start=_r6(s), end=_r6(e), scene_id=sid, severity=sev,
            confidence=round(conf, 3), evidence=ev, metrics=metrics,
            source_refs=refs))
    for c in cues:
        dur = float(c["end"]) - float(c["start"])
        if dur <= 0:
            continue
        text = str(c.get("text", ""))
        n_words = len(c.get("word_refs", []) or [])
        cps = len(text.replace("\n", "")) / dur
        if cps >= cfg["pacing_caption_cps_fast"]:
            sev = "high" if cps >= cfg["pacing_caption_cps_extreme"] else "medium"
            _emit("HIGH_CAPTION_DENSITY", c["start"], c["end"],
                  int(c.get("scene_id", -1)), sev, 0.7,
                  [_ev("caption_cps", "captions", c["start"], c["end"], "cps",
                       round(cps, 2), cfg["pacing_caption_cps_fast"],
                       f"{cps:.1f} chars/s over {dur:.1f}s")],
                  {"cps": round(cps, 2), "words": n_words},
                  [str(c.get("cue_id", ""))])
        if n_words >= cfg["pacing_caption_words_per_cue_high"]:
            _emit("HIGH_CAPTION_DENSITY", c["start"], c["end"],
                  int(c.get("scene_id", -1)), "low", 0.5,
                  [_ev("words_per_cue", "captions", c["start"], c["end"],
                       "words", n_words, cfg["pacing_caption_words_per_cue_high"],
                       "dense cue")],
                  {"words": n_words}, [str(c.get("cue_id", ""))])
    # Rapid sequences: >=3 cues with gaps < 0.3 s inside any 5 s span.
    ordered = sorted(cues, key=lambda c: (float(c["start"]), float(c["end"])))
    for i in range(len(ordered) - 2):
        a, b, c = ordered[i], ordered[i + 1], ordered[i + 2]
        if float(c["start"]) - float(a["start"]) <= 5.0 and \
           float(b["start"]) - float(a["end"]) < 0.3 and \
           float(c["start"]) - float(b["end"]) < 0.3:
            _emit("RAPID_CAPTION_SEQUENCE", a["start"], c["end"], -1, "medium", 0.6,
                  [_ev("cue_burst", "captions", a["start"], c["end"], "cues_per_5s",
                       3, 3, "three quick cues")],
                  {"cues": 3}, [str(x.get("cue_id", "")) for x in (a, b, c)])
    # Long caption-free gaps.
    span_end = max([float(c["end"]) for c in cues] or [0.0])
    cursor = 0.0
    for c in ordered:
        if float(c["start"]) - cursor >= cfg["pacing_caption_gap_long"]:
            _emit("LONG_SILENCE", cursor, float(c["start"]), -1, "low", 0.5,
                  [_ev("caption_gap", "captions", cursor, float(c["start"]),
                       "gap_s", round(float(c["start"]) - cursor, 2),
                       cfg["pacing_caption_gap_long"], "caption-free stretch")],
                  {"gap_s": round(float(c["start"]) - cursor, 2)}, [])
        cursor = max(cursor, float(c["end"]))
    _ = span_end
    return sigs


def _extract_speech_signals(words: list[dict], cfg: dict) -> tuple[list[PacingSignal], list[dict]]:
    sigs: list[PacingSignal] = []
    pauses: list[dict] = []
    seq = [0]

    def _emit(stype, s, e, sev, conf, ev, metrics):
        seq[0] += 1
        sigs.append(PacingSignal(
            signal_id=f"sig_sp_{seq[0]:04d}", signal_type=stype,
            start=_r6(s), end=_r6(e), scene_id=-1, severity=sev,
            confidence=round(conf, 3), evidence=ev, metrics=metrics,
            source_refs=[]))
    prev_end: float | None = None
    for w in words:
        if prev_end is not None and w["start"] - prev_end >= cfg["pacing_pause_s"]:
            pauses.append({"start": prev_end, "end": w["start"]})
            _emit("NATURAL_PAUSE", prev_end, w["start"], "info", 0.6,
                  [_ev("word_gap", "transcript", prev_end, w["start"], "gap_s",
                       round(w["start"] - prev_end, 2), cfg["pacing_pause_s"],
                       "inter-word pause")],
                  {"gap_s": round(w["start"] - prev_end, 2)})
        if w["terminal"]:
            _emit("SENTENCE_BOUNDARY", w["start"], w["end"], "info", 0.7,
                  [_ev("terminal_punct", "transcript", w["start"], w["end"],
                       "token", w["word"], "punctuated",
                       "sentence-like ending")],
                  {"token": w["word"]})
        prev_end = w["end"]
    # Long speech blocks: runs without qualifying pauses, duration > 8 s.
    run_start: float | None = None
    run_prev: float | None = None
    for w in words + [{"start": float("inf"), "end": float("inf")}]:
        if run_prev is not None and w["start"] - run_prev >= cfg["pacing_pause_s"]:
            base = run_start if run_start is not None else run_prev
            if run_prev - base > 8.0:
                _emit("LONG_SPEECH_BLOCK", base, run_prev, "low", 0.5,
                      [_ev("speech_run", "transcript", base, run_prev,
                           "duration_s", round(run_prev - base, 1),
                           8.0, "unbroken speech run")],
                      {"duration_s": round(run_prev - base, 1)})
            run_start = None
        if run_start is None and w["start"] != float("inf"):
            run_start = w["start"]
        run_prev = w["end"] if w["start"] != float("inf") else run_prev
    return sigs, pauses


def _extract_visual_signals(visual: dict | None, scenes: list[dict],
                            duration: float, cfg: dict) -> tuple[list[PacingSignal], list[dict]]:
    sigs: list[PacingSignal] = []
    contexts: list[dict] = []
    seq = [0]

    def _emit(stype, s, e, sid, sev, conf, ev, metrics):
        seq[0] += 1
        sigs.append(PacingSignal(
            signal_id=f"sig_vi_{seq[0]:04d}", signal_type=stype,
            start=_r6(s), end=_r6(e), scene_id=sid, severity=sev,
            confidence=round(conf, 3), evidence=ev, metrics=metrics,
            source_refs=[]))
    if not visual:
        return sigs, [{"warning": "no visual analysis: visual signals skipped"}]
    summaries = {int(s.get("scene_id", -1)): s
                 for s in visual.get("scene_summaries", [])}
    durs = [float(s["end"]) - float(s["start"]) for s in scenes]
    median = statistics.median(durs) if durs else 0.0
    for sc in scenes:
        sid = int(sc.get("scene_id", -1))
        ss, se = float(sc["start"]), float(sc["end"])
        dur = se - ss
        summ = summaries.get(sid, {}) or {}
        motion = summ.get("motion_mean", None)
        static = motion is not None and motion < cfg["pacing_static_motion_thr"]
        contexts.append({"scene_id": sid, "motion": motion, "static": static,
                         "framing": (summ.get("framing", {}) or {}).get(
                             "classification", "unknown")})
        if static and dur >= 4.0:
            _emit("STATIC_VISUAL", ss, se, sid, "low", 0.6,
                  [_ev("static_span", "visual", ss, se, "motion_mean",
                       motion, cfg["pacing_static_motion_thr"],
                       f"{dur:.1f}s low-motion scene")],
                  {"motion": motion, "duration_s": round(dur, 2)})
        if median > 0 and dur >= cfg["pacing_long_scene_ratio"] * median:
            _emit("LONG_VISUAL_SECTION", ss, se, sid, "low", 0.5,
                  [_ev("scene_outlier", "scenes", ss, se, "duration_ratio",
                       round(dur / median, 2), cfg["pacing_long_scene_ratio"],
                       "scene much longer than median")],
                  {"ratio": round(dur / median, 2)})
    for entry in visual.get("continuity", []) or []:
        if str(entry.get("label", "")) == "large_change":
            b = float(entry.get("boundary", 0.0))
            _emit("HIGH_VISUAL_CHANGE", b, b, -1, "low", 0.55,
                  [_ev("continuity_jump", "visual", b, b, "label",
                       "large_change", "changed-or-stable",
                       "abrupt visual change")],
                  {"boundary": b})
    return sigs, contexts


def _extract_safety_edl_signals(edl: dict, intel: dict | None) -> tuple[list[PacingSignal], dict]:
    """Map EDL REMOVEs + Phase 10 CutSafety to scene-agnostic signals."""
    sigs: list[PacingSignal] = []
    safety: dict[str, str] = {}
    if intel:
        for s in intel.get("cut_safety", []) or []:
            safety[str(s.get("decision_id", ""))] = str(s.get("status", "unknown"))
    seq = [0]

    def _emit(stype, s, e, sev, conf, ev):
        seq[0] += 1
        sigs.append(PacingSignal(
            signal_id=f"sig_sa_{seq[0]:04d}", signal_type=stype,
            start=_r6(s), end=_r6(e), scene_id=-1, severity=sev,
            confidence=round(conf, 3), evidence=ev, metrics={},
            source_refs=[]))
    removes = []
    for d in edl.get("decisions", []) or []:
        if d.get("action") != "REMOVE":
            continue
        s, e = float(d["start"]), float(d["end"])
        removes.append((s, e))
        st = safety.get(str(d.get("decision_id", "")), "unknown")
        if st == "UNSAFE":
            _emit("EDIT_SAFETY_UNSAFE", s, e, "high", 0.85,
                  [_ev("cut_safety", "intelligence", s, e, "status",
                       "UNSAFE", "SAFE-or-CAUTION",
                       "existing safety veto on this removal")])
        elif st == "CAUTION":
            _emit("EDIT_SAFETY_CAUTION", s, e, "medium", 0.6,
                  [_ev("cut_safety", "intelligence", s, e, "status",
                       "CAUTION", "SAFE", "existing safety caution")])
    return sigs, {"removes": removes, "safety": safety}


def _extract_boundary_density_signals(scenes: list[dict],
                                      cues: list[dict]) -> list[PacingSignal]:
    """Scene-boundary opportunities + low-caption-density regions."""
    sigs: list[PacingSignal] = []
    seq = [0]

    def _emit(stype, s, e, sid, sev, conf, ev, metrics):
        seq[0] += 1
        sigs.append(PacingSignal(
            signal_id=f"sig_bd_{seq[0]:04d}", signal_type=stype,
            start=_r6(s), end=_r6(e), scene_id=sid, severity=sev,
            confidence=round(conf, 3), evidence=ev, metrics=metrics,
            source_refs=[]))
    for sc in scenes[1:]:
        b = float(sc["start"])
        _emit("SCENE_BOUNDARY_OPPORTUNITY", b, b, int(sc.get("scene_id", -1)),
              "info", 0.5,
              [_ev("scene_edge", "scenes", b, b, "boundary", round(b, 2),
                   "known", "candidate split point")],
              {"boundary": round(b, 2)})
    for sc in scenes:
        dens = _scene_density(sc, cues)
        if dens < 0.2:
            ss, se = float(sc["start"]), float(sc["end"])
            _emit("LOW_CAPTION_DENSITY", ss, se, int(sc.get("scene_id", -1)),
                  "low", 0.5,
                  [_ev("caption_density", "captions", ss, se, "density",
                       dens, 0.2, "caption-sparse region")],
                  {"density": dens})
    return sigs


def _extract_boundary_visual_signals(visual_plan: dict | None) -> list[PacingSignal]:
    """Map visual-caption conflicts to boundary signals (review-only)."""
    sigs: list[PacingSignal] = []
    if not visual_plan:
        return sigs
    seq = [0]
    for c in visual_plan.get("conflicts", []) or []:
        seq[0] += 1
        kind = str(c.get("kind", ""))
        stype = "CAPTION_CONTRAST_CAUTION" if "contrast" in kind \
            else "CAPTION_PLACEMENT_CONFLICT"
        sev = "medium" if "contrast" in kind else "low"
        cue = c.get("cue_id", "?")
        sigs.append(PacingSignal(
            signal_id=f"sig_vc_{seq[0]:04d}", signal_type=stype,
            start=0.0, end=0.0, scene_id=-1, severity=sev, confidence=0.55,
            evidence=[_ev("visual_conflict", "visual_captions", 0.0, 0.0,
                          "kind", kind, "none",
                          f"visual caption conflict on {cue}")],
            metrics={"kind": kind}, source_refs=[str(cue)]))
    return sigs


# ---------------- correlation -> candidates ----------------

def _scene_density(scene: dict, cues: list[dict]) -> float:
    dur = float(scene["end"]) - float(scene["start"])
    if dur <= 0:
        return 0.0
    covered = sum(_overlap(float(c["start"]), float(c["end"]),
                           float(scene["start"]), float(scene["end"]))
                  for c in cues)
    return round(covered / dur, 3)


def _topic_words(words: list[dict], start: float, end: float,
                 limit: int = 3) -> list[str]:
    freq: dict[str, int] = {}
    for w in words:
        if w["start"] >= start and w["end"] <= end and not w.get("is_filler"):
            norm = str(w.get("norm", "") or "")
            if len(norm) > 3 and norm.isalpha():
                freq[norm] = freq.get(norm, 0) + 1
    return sorted(freq, key=lambda k: (-freq[k], k))[:limit]


def _sentence_split_in(start: float, end: float, words: list[dict]) -> bool:
    """True if the interval would cut inside a spoken sentence."""
    prev = [w for w in words if w["end"] <= start + 1e-6]
    nxt = [w for w in words if w["start"] >= end - 1e-6]
    if not prev or not nxt:
        return False
    if prev[-1].get("is_filler") or nxt[0].get("is_filler"):
        return False
    if prev[-1].get("terminal") or nxt[0].get("terminal"):
        return False
    return (nxt[0]["start"] - prev[-1]["end"]) < 1.0


def _correlate(ctx: dict) -> tuple[list[PacingRecommendation], list[dict]]:
    """The six spec cases + safe defaults. Returns (candidates, conflicts)."""
    recs: list[PacingRecommendation] = []
    conflicts: list[dict] = []
    scenes: list[dict] = ctx["scenes"]
    cues: list[dict] = ctx["cues"]
    words: list[dict] = ctx["words"]
    static_by_scene: dict[int, bool] = ctx["static_by_scene"]
    motion_by_scene: dict[int, float | None] = ctx["motion_by_scene"]
    long_spans: list[tuple] = ctx["long_spans"]
    style: dict = ctx["style"]
    safety: dict = ctx["safety"]
    seq = [0]

    def _rec(action, s, e, sid, priority, conf, reason, ev, signals,
            caps=(), safety_status="unknown", warnings=()):
        seq[0] += 1
        recs.append(PacingRecommendation(
            recommendation_id=f"rec_{seq[0]:04d}", action=action,
            start=_r6(s), end=_r6(e), scene_id=sid, priority=priority,
            confidence=round(conf, 3), reason=reason, evidence=list(ev),
            supporting_signals=list(signals), safety_status=safety_status,
            affected_caption_ids=list(caps), affected_visual_context="",
            source_refs=[], warnings=list(warnings)))

    for sc in scenes:
        sid = int(sc.get("scene_id", -1))
        ss, se = float(sc["start"]), float(sc["end"])
        dur = se - ss
        if dur <= 0:
            continue
        dens = _scene_density(sc, cues)
        static = static_by_scene.get(sid, False)
        motion = motion_by_scene.get(sid)
        span_words = [w for w in words if w["start"] >= ss and w["end"] <= se]
        wps = len(span_words) / dur if dur > 0 else 0.0
        long_scene = any(lo <= ss and se <= hi for lo, hi, _ in long_spans)
        ev_base = [_ev("scene_span", "scenes", ss, se, "duration_s",
                       round(dur, 2), 0, f"scene {sid} spans {dur:.1f}s"),
                   _ev("caption_density", "captions", ss, se, "density",
                       dens, 0.5, f"caption coverage {dens:.2f}")]
        # Case A: long + dense + static -> CHANGE_VISUAL (+ cutaway).
        if long_scene and wps > 1.5 and static:
            ev = ev_base + [_ev("static_visual", "visual", ss, se, "motion",
                                motion, "low",
                                "static visual under dense speech")]
            _rec("CHANGE_VISUAL", ss, se, sid, "medium", 0.6,
                 "dense speech over static visuals: change the picture, keep words",
                 ev, ["LONG_VISUAL_SECTION", "STATIC_VISUAL"])
            topic = _topic_words(span_words, ss, se)
            _rec("ADD_CUTAWAY_OPPORTUNITY", ss, se, sid, "low", 0.5,
                 f"cutaway opportunity ({', '.join(topic) or 'no topic words'})",
                 ev + [_ev("topic_words", "transcript", ss, se, "topics",
                           ",".join(topic) or "none", ">=1",
                           "frequent content words")],
                 ["STATIC_VISUAL"])
        # Case B: long + sparse + static -> HOLD_LONGER (relaxed) else KEEP.
        elif long_scene and wps < 0.5 and static:
            if style.get("name") in ("podcast", "documentary", "cinematic"):
                _rec("HOLD_LONGER", ss, se, sid, "low", 0.55,
                     "sparse slow scene carries context: hold, do not cut",
                     ev_base, ["LONG_VISUAL_SECTION", "LOW_CAPTION_DENSITY"])
            else:
                _rec("KEEP", ss, se, sid, "informational", 0.6,
                     "sparse scene without visual demand: default keep",
                     ev_base, ["LOW_CAPTION_DENSITY"])
        # Case C: fast captions + stable shot -> CHANGE_VISUAL, high evidence.
        elif wps > 2.5 and motion is not None and motion < 0.05 and dur >= 4.0:
            _rec("CHANGE_VISUAL", ss, se, sid, "medium", 0.7,
                 "rapid caption sequence over a stable shot",
                 ev_base + [_ev("fast_captions", "captions", ss, se, "wps",
                                round(wps, 2), 2.5, "fast caption rate")],
                 ["RAPID_CAPTION_SEQUENCE", "STATIC_VISUAL"])
        else:
            _rec("KEEP", ss, se, sid, "informational", 0.65,
                 "no pacing evidence demands change",
                 ev_base, [])
    # Case D is emitted per visual conflict by the caller (needs cue refs).
    # Case E/F are emission points in the project runner (need EDL+safety).
    return recs, conflicts


def _apply_case_d_e(ctx: dict, recs: list[PacingRecommendation],
                    conflicts: list[dict]) -> None:
    """Case D (placement conflict + important visual -> REVIEW, never move)
    and Case E (boundary + pause + sentence + SAFE -> SPLIT)."""
    scenes: list[dict] = ctx["scenes"]
    safety_spans: list[tuple] = ctx.get("safety_spans", [])
    bounds = sorted({float(s["start"]) for s in scenes[1:]} or [])
    pauses: list[tuple] = ctx["pauses"]
    terminals: list[tuple] = ctx["terminals"]

    def _veto_at(b: float) -> str:
        """Worst safety status overlapping the boundary window."""
        worst = "SAFE"
        for s, e, st in safety_spans:
            if s - 0.5 <= b <= e + 0.5 and st in ("CAUTION", "UNSAFE"):
                if st == "UNSAFE":
                    return "UNSAFE"
                worst = "CAUTION"
        return worst

    for b in bounds:
        pause_hit = next(((ps, pe) for ps, pe in pauses if ps <= b <= pe), None)
        term_hit = any(abs(t - b) < 1.0 for _, t in terminals)
        if not (pause_hit and term_hit):
            continue
        veto = _veto_at(b)
        if veto == "UNSAFE":
            recs.append(_split_review(b, scenes))
            conflicts.append({"topic": f"split@{b:.2f}s",
                              "winner": "keep", "principle": "edit_safety",
                              "explanation": "boundary looks split-safe but "
                                             "existing safety vetoes it"})
        elif veto == "CAUTION":
            recs.append(_split_review(b, scenes))
            conflicts.append({"topic": f"split@{b:.2f}s",
                              "winner": "keep", "principle": "edit_safety",
                              "explanation": "boundary looks split-safe but "
                                             "existing safety cautions it"})
        else:
            recs.append(_split_ok(b, scenes))
    for c in ctx.get("visual_conflicts", []) or []:
        recs.append(PacingRecommendation(
            recommendation_id=f"rec_rev_{len(recs) + 1:04d}", action="REVIEW",
            start=_r6(c.get("start", 0.0)), end=_r6(c.get("end", 0.0)),
            scene_id=int(c.get("scene_id", -1)), priority="low", confidence=0.5,
            reason=f"visual caption conflict ({c.get('kind', '?')}): review, never move",
            evidence=[_ev("visual_conflict", "visual_captions",
                          c.get("start", 0.0), c.get("end", 0.0), "kind",
                          c.get("kind", "?"), "none", "reported conflict")],
            supporting_signals=["CAPTION_PLACEMENT_CONFLICT"],
            safety_status="unknown", affected_caption_ids=[],
            affected_visual_context="", source_refs=[], warnings=[]))


def _split_ok(b: float, scenes: list[dict]) -> PacingRecommendation:
    sc = next((s for s in scenes if float(s["start"]) <= b < float(s["end"])),
              scenes[0] if scenes else {"scene_id": -1})
    return PacingRecommendation(
        recommendation_id="rec_split", action="SPLIT",
        start=_r6(max(0.0, b - 0.5)), end=_r6(b + 0.5),
        scene_id=int(sc.get("scene_id", -1)), priority="medium", confidence=0.6,
        reason="scene boundary + natural pause + sentence boundary, safety allows",
        evidence=[_ev("split_point", "scenes+transcript", b, b, "boundary",
                      round(b, 2), "aligned",
                      "pause, sentence end and scene edge coincide")],
        supporting_signals=["SCENE_BOUNDARY_OPPORTUNITY", "NATURAL_PAUSE",
                            "SENTENCE_BOUNDARY"],
        safety_status="SAFE", affected_caption_ids=[],
        affected_visual_context="", source_refs=[], warnings=[])


def _split_review(b: float, scenes: list[dict]) -> PacingRecommendation:
    rec = _split_ok(b, scenes)
    rec.action, rec.priority, rec.confidence = "REVIEW", "low", 0.5
    rec.reason = "boundary looks split-safe but safety vetoes it: review only"
    return rec


def _trim_candidates(ctx: dict, recs: list[PacingRecommendation],
                     conflicts: list[dict]) -> None:
    """Case F: TRIM only what the EDL already removes, with valid cue mapping
    and non-UNSAFE safety. Anything else -> REVIEW/KEEP, never invented cuts."""
    edl_removes: list[tuple] = ctx["edl_removes"]
    cues: list[dict] = ctx["cues"]
    safety: dict = ctx["safety"]
    for rs, re_ in edl_removes:
        overlapping = [c for c in cues
                       if _overlap(float(c["start"]), float(c["end"]), rs, re_) > 1e-3]
        words_inside = [w for c in overlapping for w in c.get("word_refs", [])
                        if rs - 1e-3 <= float(w["start"])
                        and float(w["end"]) <= re_ + 1e-3]
        st = safety.get(f"{round(rs, 3)}", "unknown")
        if st == "UNSAFE":
            recs.append(PacingRecommendation(
                recommendation_id=f"rec_trim_{len(recs) + 1:04d}", action="REVIEW",
                start=_r6(rs), end=_r6(re_), scene_id=-1, priority="high",
                confidence=0.7,
                reason="EDL removal vetoed by existing UNSAFE safety: review, do not cut",
                evidence=[_ev("safety_veto", "intelligence", rs, re_, "status",
                             "UNSAFE", "SAFE-or-CAUTION", "safety veto")],
                supporting_signals=["EDIT_SAFETY_UNSAFE"],
                safety_status="UNSAFE",
                affected_caption_ids=[c.get("cue_id", "") for c in overlapping],
                affected_visual_context="", source_refs=[],
                warnings=["never cut on UNSAFE"]))
            conflicts.append({"topic": f"trim [{rs}-{re_}]",
                              "winner": "keep", "principle": "edit_safety",
                              "explanation": "EDL proposed removal but safety vetoes it"})
        elif _sentence_split_in(rs, re_, ctx["words"]):
            recs.append(PacingRecommendation(
                recommendation_id=f"rec_trim_{len(recs) + 1:04d}", action="REVIEW",
                start=_r6(rs), end=_r6(re_), scene_id=-1, priority="medium",
                confidence=0.55,
                reason="EDL removal would split a sentence: downgraded to review",
                evidence=[_ev("sentence_split", "transcript", rs, re_, "split",
                             True, False, "cut inside spoken sentence")],
                supporting_signals=["EDIT_SAFETY_CAUTION"],
                safety_status="CAUTION",
                affected_caption_ids=[c.get("cue_id", "") for c in overlapping],
                affected_visual_context="", source_refs=[], warnings=[]))
        elif any(float(c["start"]) < rs - 1e-3 or float(c["end"]) > re_ + 1e-3
                 for c in overlapping):
            recs.append(PacingRecommendation(
                recommendation_id=f"rec_trim_{len(recs) + 1:04d}", action="REVIEW",
                start=_r6(rs), end=_r6(re_), scene_id=-1, priority="medium",
                confidence=0.55,
                reason="EDL removal cuts through a cue boundary: invalid cue "
                       "mapping, downgraded to review",
                evidence=[_ev("partial_cue", "captions", rs, re_, "covered",
                             False, True, "cue extends past removal span")],
                supporting_signals=["EDIT_SAFETY_CAUTION"],
                safety_status="CAUTION",
                affected_caption_ids=[c.get("cue_id", "") for c in overlapping],
                affected_visual_context="", source_refs=[], warnings=[]))
        else:
            recs.append(PacingRecommendation(
                recommendation_id=f"rec_trim_{len(recs) + 1:04d}", action="TRIM",
                start=_r6(rs), end=_r6(re_), scene_id=-1, priority="high",
                confidence=0.7,
                reason="EDL already removes this span; cues stay valid; safety allows",
                evidence=[_ev("edl_remove", "edl", rs, re_, "covered",
                             True, True, "existing EDL decision covers span"),
                          _ev("dropped_words", "captions", rs, re_, "count",
                             len(words_inside), "any",
                             f"{len(words_inside)} cue words inside removal")],
                supporting_signals=["LONG_SILENCE"],
                safety_status=st if st != "unknown" else "SAFE",
                affected_caption_ids=[c.get("cue_id", "") for c in overlapping],
                affected_visual_context="", source_refs=[], warnings=[]))


# ---------------- ranking ----------------

_BASE_PRIORITY = {"TRIM": "high", "SPLIT": "medium", "CHANGE_VISUAL": "medium",
                  "ADD_CUTAWAY_OPPORTUNITY": "low", "REVIEW": "low",
                  "HOLD_LONGER": "informational", "KEEP": "informational",
                  "ACCELERATE_VISUAL": "low"}
_SAFETY_STATUS_RANK = {"SAFE": 0, "CAUTION": 1, "unknown": 2, "UNSAFE": 3}


def _rec_rank(rec: PacingRecommendation) -> tuple:
    return (ACTION_SAFETY_RANK.get(rec.action, 9),
            _SAFETY_STATUS_RANK.get(rec.safety_status, 2))


def _rank_key(rec: PacingRecommendation) -> tuple:
    return (PRIORITY_RANK.get(rec.priority, 4), -rec.confidence, rec.start)


def rank_recommendations(recs: list[PacingRecommendation]
                         ) -> tuple[list[PacingRecommendation], list[dict]]:
    """Sort by (priority, -confidence, start); resolve overlaps by keeping
    the safest action, merging compatible ones, rejecting conflicts.

    Informational scene defaults yield to any specific (non-informational)
    action on overlap; complementary CHANGE_VISUAL + ADD_CUTAWAY_OPPORTUNITY
    pairs coexist (Case A emits both by design)."""
    ordered = sorted(recs, key=_rank_key)
    kept: list[PacingRecommendation] = []
    rejected: list[dict] = []
    for rec in ordered:
        clash = next((k for k in kept
                      if _overlap(k.start, k.end, rec.start, rec.end) > 1e-6), None)
        if clash is None:
            kept.append(rec)
            continue
        if rec.priority == "informational" and clash.priority != "informational":
            rejected.append({"recommendation_id": rec.recommendation_id,
                             "action": rec.action,
                             "reason": f"scene default yields to specific "
                                       f"{clash.action} {clash.recommendation_id}"})
            continue
        if clash.priority == "informational" and rec.priority != "informational":
            kept.remove(clash)
            kept.append(rec)
            rejected.append({"recommendation_id": clash.recommendation_id,
                             "action": clash.action,
                             "reason": f"scene default yields to specific "
                                       f"{rec.action} {rec.recommendation_id}"})
            continue
        pair = {rec.action, clash.action}
        if pair <= {"CHANGE_VISUAL", "ADD_CUTAWAY_OPPORTUNITY"} and len(pair) == 2:
            kept.append(rec)  # complementary by design: coexist, no rejection
            continue
        rank_new, rank_old = _rec_rank(rec), _rec_rank(clash)
        if rank_new == rank_old and rec.action == clash.action \
                and rec.reason == clash.reason:
            clash.start = _r6(min(clash.start, rec.start))
            clash.end = _r6(max(clash.end, rec.end))
            clash.evidence = clash.evidence + rec.evidence
            clash.supporting_signals = sorted(set(clash.supporting_signals)
                                              | set(rec.supporting_signals))
            continue
        if rank_new == rank_old:
            rejected.append({"recommendation_id": rec.recommendation_id,
                             "action": rec.action,
                             "reason": f"duplicates overlapping {clash.action} "
                                       f"{clash.recommendation_id}; rejected"})
            continue
        loser, winner = (rec, clash) if rank_new > rank_old else (clash, rec)
        if winner is clash:
            rejected.append({"recommendation_id": loser.recommendation_id,
                             "action": loser.action,
                             "reason": f"overlaps safer {winner.action} "
                                       f"{winner.recommendation_id}; rejected"})
        else:
            kept.remove(clash)
            kept.append(rec)
            rejected.append({"recommendation_id": clash.recommendation_id,
                             "action": clash.action,
                             "reason": f"overlaps safer {rec.action} "
                                       f"{rec.recommendation_id}; rejected"})
    kept.sort(key=_rank_key)
    for i, rec in enumerate(kept):
        rec.recommendation_id = f"rec_{i + 1:04d}"
    return kept, rejected


# ---------------- assembly ----------------

def _safety_spans(intel: dict | None) -> list[tuple]:
    out = []
    if intel:
        for s in intel.get("cut_safety", []) or []:
            try:
                out.append((float(s["start"]), float(s["end"]),
                            str(s.get("status", "unknown"))))
            except (KeyError, TypeError, ValueError):
                continue
    return out


def build_pacing_plan(audio: dict | None, transcript: dict | None,
                      scenes: dict, edl: dict, cues: list[dict],
                      intel: dict | None, visual: dict | None,
                      visual_plan: dict | None, brain: dict | None,
                      duration: float, style_name: str,
                      config: dict) -> CaptionPacingPlan:
    """Assemble the full plan from validated parts (pure; no I/O)."""
    from engine.editing.brain import resolve_style
    if not isinstance(scenes, dict) or not scenes.get("scenes"):
        raise PacingError("missing/invalid scene analysis (need scenes[])")
    for sc in scenes.get("scenes", []):
        try:
            ss, se = float(sc["start"]), float(sc["end"])
        except (KeyError, TypeError, ValueError):
            raise PacingError("scene with invalid coordinates") from None
        if not se > ss or ss < 0:
            raise PacingError(f"invalid scene interval [{ss}, {se}]")
    if not isinstance(edl, dict) or not edl.get("decisions"):
        raise PacingError("missing/invalid base EDL (need decisions[])")
    for d in edl.get("decisions", []):
        try:
            ds, de = float(d["start"]), float(d["end"])
        except (KeyError, TypeError, ValueError):
            raise PacingError("EDL decision with invalid coordinates") from None
        if not de > ds or ds < 0:
            raise PacingError(f"invalid EDL interval [{ds}, {de}]")
        if d.get("action") not in ("KEEP", "REMOVE"):
            raise PacingError(f"unsupported EDL action {d.get('action')!r}")
    if duration <= 0:
        raise PacingError(f"invalid duration {duration}")
    try:
        style = resolve_style(style_name)
    except Exception as exc:
        raise PacingError(f"unknown style {style_name!r}") from exc
    thresholds, adaptations = _adapt_thresholds(config, style.name)
    warnings: list[str] = []
    if transcript is None:
        warnings.append("no transcript: sentence/pause/density signals degraded "
                        "(cue word_refs used where present)")
    if audio is None:
        warnings.append("no audio analysis: silence signals skipped")
    if visual is None:
        warnings.append("no visual analysis: visual signals skipped")
    if intel is None:
        warnings.append("no editor intelligence: safety lookups limited to EDL evidence")
    if brain is None:
        warnings.append("no editor plan: brain candidate context unavailable")

    words = _words(transcript)
    scene_bounds = _scene_list(scenes)
    silences = [{"start": float(s["start"]), "end": float(s["end"]),
                 "duration": float(s.get("duration", float(s["end"]) - float(s["start"])))}
                for s in (audio.get("silence", []) or [])] if audio else []
    static_by_scene: dict[int, bool] = {}
    motion_by_scene: dict[int, float | None] = {}
    long_spans: list[tuple] = []
    if visual:
        summaries = {int(s.get("scene_id", -1)): s
                     for s in visual.get("scene_summaries", [])}
        durs = [float(s["end"]) - float(s["start"]) for s in scene_bounds]
        median = statistics.median(durs) if durs else 0.0
        for sc in scene_bounds:
            sid = int(sc.get("scene_id", -1))
            summ = summaries.get(sid, {}) or {}
            motion = summ.get("motion_mean", None)
            motion = float(motion) if motion is not None else None
            motion_by_scene[sid] = motion
            static = motion is not None and motion < thresholds["pacing_static_motion_thr"]
            static_by_scene[sid] = static
            dur = float(sc["end"]) - float(sc["start"])
            if median > 0 and dur >= thresholds["pacing_long_scene_ratio"] * median:
                long_spans.append((float(sc["start"]), float(sc["end"]), sid))
    for d in edl.get("decisions", []) or []:
        if d.get("action") == "REMOVE":
            rs, re_ = float(d["start"]), float(d["end"])
            if re_ - rs >= 4.0:
                long_spans.append((rs, re_, -1))
    safety_map: dict[str, str] = {}
    safety_spans: list[tuple] = []
    if intel:
        for s in intel.get("cut_safety", []) or []:
            try:
                safety_map[str(s.get("decision_id", ""))] = str(s.get("status", "unknown"))
                safety_spans.append((float(s["start"]), float(s["end"]),
                                     str(s.get("status", "unknown"))))
            except (KeyError, TypeError, ValueError):
                continue
    pauses = [(w2["start"] - w1["end"], w1["end"], w2["start"])
              for w1, w2 in zip(words, words[1:])
              if w2["start"] - w1["end"] >= thresholds["pacing_pause_s"]]
    pauses = [(ps, pe) for _, ps, pe in pauses]
    terminals = [(i, w["end"]) for i, w in enumerate(words) if w["terminal"]]
    visual_conflicts = (visual_plan.get("conflicts", []) or []) if visual_plan else []

    ctx = {"scenes": scene_bounds, "cues": cues, "words": words,
           "silences": silences, "static_by_scene": static_by_scene,
           "motion_by_scene": motion_by_scene, "long_spans": long_spans,
           "edl_removes": [(float(d["start"]), float(d["end"]))
                           for d in edl.get("decisions", []) or []
                           if d.get("action") == "REMOVE"],
           "style": {"name": style.name},
           "safety": safety_map, "safety_spans": safety_spans,
           "pauses": pauses, "terminals": terminals,
           "visual_conflicts": visual_conflicts}
    signals: list[PacingSignal] = []
    signals += _extract_caption_signals(cues, thresholds)
    speech_sigs, _ = _extract_speech_signals(words, thresholds)
    signals += speech_sigs
    vis_sigs, _ = _extract_visual_signals(visual, scene_bounds, duration, thresholds)
    signals += vis_sigs
    edl_sigs, _ = _extract_safety_edl_signals(edl, intel)
    signals += edl_sigs
    signals += _extract_boundary_visual_signals(visual_plan)
    signals += _extract_boundary_density_signals(scene_bounds, cues)
    signals.sort(key=lambda s: (s.start, s.end, s.signal_id))

    recs, conflicts = _correlate(ctx)
    _apply_case_d_e(ctx, recs, conflicts)
    _trim_candidates(ctx, recs, conflicts)
    ranked, rejected = rank_recommendations(recs)

    safety_counts: dict[str, int] = {}
    for r in ranked:
        safety_counts[r.safety_status] = safety_counts.get(r.safety_status, 0) + 1
    by_action: dict[str, int] = {}
    for r in ranked:
        by_action[r.action] = by_action.get(r.action, 0) + 1
    return CaptionPacingPlan(
        project_id="", source_hash="",
        edit_plan_hash="", caption_plan_hash="", visual_caption_plan_hash="",
        style=style.name,
        context_summary=_context_summary(
            scene_bounds, cues, words, static_by_scene, motion_by_scene, visual_plan),
        signals=signals, recommendations=ranked, conflicts=conflicts,
        rejected=rejected,
        safety_summary={"counts": safety_counts,
                        "hierarchy": list(PRINCIPLE_ORDER)},
        statistics={"signals": len(signals), "recommendations": len(ranked),
                    "rejected": len(rejected), "conflicts": len(conflicts),
                    "by_action": by_action,
                    "threshold_adaptations": adaptations},
        warnings=warnings)


def _context_summary(scenes, cues, words, static_by_scene, motion_by_scene,
                     visual_plan) -> list[CaptionPacingContext]:
    out: list[CaptionPacingContext] = []
    for sc in scenes:
        sid = int(sc.get("scene_id", -1))
        ss, se = float(sc["start"]), float(sc["end"])
        dur = se - ss
        in_scene = [c for c in cues
                    if _overlap(float(c["start"]), float(c["end"]), ss, se) > 1e-6]
        wds = [w for w in words if w["start"] >= ss and w["end"] <= se]
        cap_dur = sum(_overlap(float(c["start"]), float(c["end"]), ss, se)
                      for c in in_scene)
        speech_dur = sum(w["end"] - w["start"] for w in wds)
        gaps = []
        for a, b in zip(in_scene, in_scene[1:]):
            g = float(b["start"]) - float(a["end"])
            if g > 1e-6:
                gaps.append(round(g, 3))
        out.append(CaptionPacingContext(
            scene_id=sid, scene_start=_r6(ss), scene_end=_r6(se),
            scene_duration=_r6(dur),
            caption_cue_ids=[str(c.get("cue_id", "")) for c in in_scene],
            caption_duration=_r6(cap_dur),
            words_per_cue=round(len(wds) / max(len(in_scene), 1), 2),
            cps=round(sum(len(str(c.get("text", "")).replace("\n", ""))
                          for c in in_scene) / max(cap_dur, 1e-6), 2),
            wpm=round(len(wds) / max(speech_dur, 1e-6) * 60.0, 1) if speech_dur else 0.0,
            caption_density=round(cap_dur / dur, 3) if dur > 0 else 0.0,
            pause_gaps=gaps,
            visual_stagnation=round(1.0 if static_by_scene.get(sid) else 0.0, 3),
            visual_change="unknown",
            edit_safety="unknown",
            editor_candidate="",
            caption_placement="unknown", caption_contrast="unknown",
            visual_conflicts=sum(1 for c in (visual_plan.get("conflicts", [])
                                             if visual_plan else [])),
            confidence=0.5, warnings=[]))
    return out


# ---------------- project runner + approval ----------------

def _load_json(path: Path, what: str, required: bool = True) -> dict | None:
    import json
    if not path.is_file():
        if required:
            raise PacingError(f"missing {what} ({path.name})")
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PacingError(f"corrupt {what}: {exc}") from exc


def run_caption_pacing_for_project(project_id: str, style_name: str = "general",
                                   config_overrides: dict | None = None,
                                   force: bool = False,
                                   dry_run: bool = False) -> dict:
    """Build the pacing plan from cached artifacts. Dry-run builds without
    writing artifacts, stages, or cache entries (pure computation)."""
    import json
    project = load_project(project_id)
    pid = project.id
    log_file = project_dir(pid) / "logs" / "run.jsonl"
    config = resolve_pacing_config(config_overrides)
    from engine.rendering.execution import edl_hash

    cap_plan = _load_json(project_dir(pid) / "captions" / "caption_plan.json",
                          "caption plan (run captions first)")
    scenes = _load_json(project_dir(pid) / "analysis" / "scenes.json",
                        "scene analysis (run scenes first)")
    edl = _load_json(project_dir(pid) / "edit" / "edit_decision.json",
                     "base EDL (run edit first)")
    audio = _load_json(project_dir(pid) / "analysis" / "audio_analysis.json",
                       "audio analysis", required=False)
    transcript = _load_json(project_dir(pid) / "analysis" / "transcript.json",
                            "transcript", required=False)
    visual_p = project_dir(pid) / "visual" / "visual_analysis.json"
    visual = _load_json(visual_p, "visual analysis", required=False)
    vis_plan_p = project_dir(pid) / "captions" / "visual_caption_plan.json"
    visual_plan = _load_json(vis_plan_p, "visual caption plan", required=False)
    intel_p = project_dir(pid) / "edit" / "edit_intelligence.json"
    intel = _load_json(intel_p, "editor intelligence", required=False)
    brain_p = project_dir(pid) / "editing" / "editor_plan.json"
    brain = _load_json(brain_p, "editor plan", required=False)
    duration = float(edl.get("duration") or 0)
    if duration <= 0:
        raise PacingError("base EDL has no usable duration")

    refs = {"audio": _stable_hash(audio) if audio else "none",
            "transcript": _stable_hash(transcript) if transcript else "none",
            "scenes": _stable_hash(scenes),
            "edl": edl_hash(edl),
            "caption": _stable_hash(cap_plan),
            "visual": _stable_hash(visual) if visual else "none",
            "visual_plan": _stable_hash(visual_plan) if visual_plan else "none",
            "intel": _stable_hash(intel) if intel else "none",
            "brain": _stable_hash(brain) if brain else "none"}
    key = cache_key(project.input_path, "caption_pacing",
                    {**refs, "style": style_name,
                     "config": {k: config[k] for k in PACING_KEYS},
                     "version": PACING_VERSION, "code_hash": _code_hash()})
    t0 = time.perf_counter()
    if not force and not dry_run:
        hit = cached(key)
        if hit is not None:
            payload = json.loads(hit.read_text(encoding="utf-8"))
            write_artifact(pid, "editing", "caption_pacing_plan.json", payload)
            mark_stage(project, "caption_pacing", "cached",
                       "editing/caption_pacing_plan.json")
            log_event(log_file, "caption_pacing", "plan", "cached",
                      time.perf_counter() - t0, "editing/caption_pacing_plan.json",
                      _versions(),
                      {"signals": len(payload.get("signals", [])),
                       "recommendations": len(payload.get("recommendations", []))})
            return {"project": pid, "cached": True, "plan": payload}

    plan = build_pacing_plan(audio, transcript, scenes, edl,
                             cap_plan.get("cues", []), intel, visual,
                             visual_plan, brain, duration, style_name, config)
    plan.project_id = pid
    plan.source_hash = _media_hash(project.input_path)
    plan.edit_plan_hash = _stable_hash(brain) if brain else "none"
    plan.caption_plan_hash = _stable_hash(cap_plan)
    plan.visual_caption_plan_hash = _stable_hash(visual_plan) \
        if visual_plan else "none"
    from dataclasses import asdict
    payload = asdict(plan)
    if dry_run:
        return {"project": pid, "cached": False, "plan": payload, "dry_run": True}
    write_artifact(pid, "editing", "caption_pacing_plan.json", payload)
    store(key, payload)
    mark_stage(project, "caption_pacing", "done", "editing/caption_pacing_plan.json")
    log_event(log_file, "caption_pacing", "plan", "ok",
              time.perf_counter() - t0, "editing/caption_pacing_plan.json",
              _versions(),
              {"signals": len(payload.get("signals", [])),
               "recommendations": len(payload.get("recommendations", []))})
    return {"project": pid, "cached": False, "plan": payload}


def _media_hash(source: str) -> str:
    from engine.core.pipeline import cache_key as _ck
    return _ck(source, "pacing-source", {})


def approve_caption_pacing(project_id: str, approver: str = "operator") -> dict:
    """Explicit approval binding all 8 inputs. Never mutates other artifacts."""
    import json
    from datetime import datetime, timezone
    project = load_project(project_id)
    pid = project.id
    log_file = project_dir(pid) / "logs" / "run.jsonl"
    plan = _load_json(project_dir(pid) / "editing" / "caption_pacing_plan.json",
                      "pacing plan (run caption-pacing first)")

    def _rehash(name: str, subdir: str, required: bool) -> str:
        payload = _load_json(project_dir(pid) / subdir / name, name,
                             required=required)
        return _stable_hash(payload) if payload is not None else "none"

    current = {
        "source": _media_hash(project.input_path),
        "edit_plan": _rehash("editor_plan.json", "editing", False),
        "caption_plan": _stable_hash(_load_json(
            project_dir(pid) / "captions" / "caption_plan.json", "caption plan")),
        "visual_plan": _rehash("visual_caption_plan.json", "captions", False),
        "style": plan.get("style", "general"),
        "config": plan.get("statistics", {}).get("threshold_adaptations", []),
    }
    # The plan embeds everything needed to re-derive its own identity except
    # live source/artifact state, which is recomputed above.
    expected = {
        "source_hash": plan.get("source_hash", ""),
        "edit_plan_hash": plan.get("edit_plan_hash", ""),
        "caption_plan_hash": plan.get("caption_plan_hash", ""),
        "visual_caption_plan_hash": plan.get("visual_caption_plan_hash", ""),
        "style": plan.get("style", ""),
    }
    drift = []
    if current["source"] != expected["source_hash"]:
        drift.append("source")
    if current["edit_plan"] != expected["edit_plan_hash"] and \
            not (current["edit_plan"] == "none" and expected["edit_plan_hash"] == "none"):
        drift.append("edit_plan")
    if current["caption_plan"] != expected["caption_plan_hash"]:
        drift.append("caption_plan")
    if current["visual_plan"] != expected["visual_caption_plan_hash"]:
        drift.append("visual_caption_plan")
    if drift:
        raise PacingError(f"drift since pacing plan: {', '.join(drift)} — re-plan")
    approval = {"schema_version": "caption-pacing-approval-1.0",
                "source_hash": current["source"],
                "edit_plan_hash": current["edit_plan"],
                "caption_plan_hash": current["caption_plan"],
                "visual_caption_plan_hash": current["visual_plan"],
                "pacing_plan_hash": _plan_hash(plan),
                "style": plan.get("style", ""),
                "config_identity": current,
                "code_version": PACING_VERSION,
                "approved_at": datetime.now(timezone.utc).isoformat(),
                "approver": approver}
    write_artifact(pid, "editing", "approved_caption_pacing_plan.json", approval)
    mark_stage(project, "caption_pacing_approval", "done",
               "editing/approved_caption_pacing_plan.json")
    log_event(log_file, "caption_pacing", "approve", "ok", 0.0,
              "editing/approved_caption_pacing_plan.json", _versions(),
              {"recommendations": len(plan.get("recommendations", []))})
    return {"project": pid, "approval": approval}


def validate_caption_pacing_approval(project_id: str) -> dict:
    """Revalidate all bindings. Returns {approval, plan} or raises."""
    import json
    project = load_project(project_id)
    pid = project.id
    ap_path = project_dir(pid) / "editing" / "approved_caption_pacing_plan.json"
    if not ap_path.is_file():
        raise PacingError("missing pacing approval (run approve-caption-pacing first)")
    try:
        approval = json.loads(ap_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PacingError(f"corrupt pacing approval: {exc}") from exc
    if approval.get("schema_version") != "caption-pacing-approval-1.0":
        raise PacingError("unsupported pacing approval schema")
    plan_path = project_dir(pid) / "editing" / "caption_pacing_plan.json"
    try:
        plan = json.loads(plan_path.read_text(encoding="utf-8")) \
            if plan_path.is_file() else None
    except json.JSONDecodeError as exc:
        raise PacingError(f"corrupt pacing plan: {exc}") from exc
    if plan is None or _plan_hash(plan) != approval.get("pacing_plan_hash"):
        raise PacingError("pacing plan changed since approval: re-approve")
    cap_path = project_dir(pid) / "captions" / "caption_plan.json"
    try:
        cap_now = _stable_hash(json.loads(cap_path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError) as exc:
        raise PacingError(f"caption plan unreadable: {exc}") from exc
    if cap_now != approval.get("caption_plan_hash"):
        raise PacingError("caption plan changed since approval: re-approve")
    if _media_hash(project.input_path) != approval.get("source_hash"):
        raise PacingError("source changed since approval: re-approve")
    return {"approval": approval, "plan": plan}


def _plan_hash(plan: dict) -> str:
    import hashlib
    import json as _json
    canonical = {k: v for k, v in plan.items() if k != "cached"}
    return hashlib.sha256(_json.dumps(canonical, sort_keys=True, default=str)
                          .encode()).hexdigest()[:32]
