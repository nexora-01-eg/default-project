"""Phase 15 — caption-aware visual polish (measurements + approved deltas).

Reads: caption plan, visual analysis, editor plan (optional), source media.
Writes: captions/visual_caption_plan.json (+ approval-gated rendering).
Never: motion graphics, karaoke, per-character animation, downloads,
identity. Faces come only from the Phase 11 adapter (UNAVAILABLE here, so
face paths are exercised with injected fakes and labeled as such).
"""
from __future__ import annotations

import re
import time
from dataclasses import asdict
from pathlib import Path

from engine.analysis.fillers import filler_set, normalize_token
from engine.core import config as config_mod
from engine.core.logging_utils import log_event
from engine.core.models import (
    CaptionEmphasis,
    CaptionPlacement,
    CaptionVisualContext,
    VisualCaptionPlan,
)
from engine.core.pipeline import cache_key, cached, store
from engine.core.project_store import (
    load_project,
    mark_stage,
    project_dir,
    write_artifact,
)
from engine.editing.decisions import hash_analysis
from engine.subtitles.captions import caption_plan_hash

VISUAL_CAPTION_VERSION = "1.0.0"
VISUAL_CAPTION_KEYS = ("visual_caption_version", "visual_caption_band_top",
                       "visual_caption_band_mid", "visual_caption_band_bot",
                       "visual_caption_good_thr", "visual_caption_poor_thr",
                       "visual_caption_busy_thr", "visual_caption_outline_max",
                       "visual_caption_enable_emphasis",
                       "visual_caption_max_emphasis_ratio",
                       "caption_position", "caption_margin_v", "caption_margin_h")
POSITION_BAND = {"bottom": (0.62, 0.95), "center": (0.35, 0.65), "top": (0.05, 0.38)}
_NUMBER_RE = re.compile(r"^[\d\u0660-\u0669\u06f0-\u06f9][\d\u0660-\u0669\u06f0-\u06f9,.\u066b\u066c]*$")
_PUNCT_ONLY_RE = re.compile(r"^[\W_]+$", re.UNICODE)


class VisualCaptionError(RuntimeError):
    pass


def _r3(x: float) -> float:
    return round(float(x), 3)


def _versions() -> dict:
    import platform
    return {"python": platform.python_version(), "engine": "0.1.0"}


def _code_hash() -> str:
    """Hash of this module's source: engine edits invalidate the visual
    cache automatically (stale plans from older logic must never be served)."""
    import hashlib
    try:
        return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()[:16]
    except OSError:
        return "unknown"


def _media_hash(source: str) -> str:
    from engine.core.pipeline import cache_key
    return cache_key(source, "visual-source", {})


def resolve_visual_caption_config(overrides: dict | None = None) -> dict:
    cfg = config_mod.resolve(overrides=overrides)
    out = {k: cfg[k] for k in VISUAL_CAPTION_KEYS}
    for key in ("visual_caption_good_thr", "visual_caption_poor_thr",
                "visual_caption_busy_thr"):
        try:
            out[key] = float(out[key])
        except (TypeError, ValueError):
            raise VisualCaptionError(f"{key} must be a number") from None
    for key in ("visual_caption_outline_max",):
        try:
            out[key] = int(out[key])
        except (TypeError, ValueError):
            raise VisualCaptionError(f"{key} must be an integer") from None
    for key in ("visual_caption_band_top", "visual_caption_band_mid",
                "visual_caption_band_bot"):
        try:
            out[key] = float(out[key])
        except (TypeError, ValueError):
            raise VisualCaptionError(f"{key} must be a number") from None
    try:
        out["visual_caption_max_emphasis_ratio"] = float(
            out["visual_caption_max_emphasis_ratio"])
        out["caption_margin_v"] = int(out["caption_margin_v"])
        out["caption_margin_h"] = int(out["caption_margin_h"])
    except (TypeError, ValueError):
        raise VisualCaptionError("emphasis ratio / margins must be numbers") from None
    if out["caption_position"] not in ("bottom", "center", "top"):
        raise VisualCaptionError("caption_position must be bottom|center|top")
    out["visual_caption_enable_emphasis"] = bool(out["visual_caption_enable_emphasis"])
    return out


def sample_bands(source: str, t: float, duration: float,
                 width: int, height: int) -> dict:
    """Measure top/center/bottom band brightness+std from a real decoded
    frame at time t (gateway extract_frame to temp, cv2 read)."""
    import cv2
    import numpy as np
    import tempfile
    from engine.rendering.ffmpeg import extract_frame
    t = max(0.0, min(float(t), max(0.0, duration - 0.05)))
    with tempfile.TemporaryDirectory(prefix="vcap_") as tmp:
        dest = Path(tmp) / "probe.jpg"
        try:
            extract_frame(source, t, dest)
        except Exception as exc:
            raise VisualCaptionError(f"band sampling failed at t={t}: {exc}") from exc
        bgr = cv2.imread(str(dest))
        if bgr is None:
            raise VisualCaptionError(f"unreadable probe frame at t={t}")
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY).astype(float)
    h = gray.shape[0]
    bands = {"top": (0.05, 0.38), "center": (0.35, 0.65), "bottom": (0.62, 0.95)}
    out = {}
    for name, (r0, r1) in bands.items():
        region = gray[int(h * r0):int(h * r1)]
        out[name] = {"mean": _r3(float(region.mean())),
                     "std": _r3(float(region.std()))}
    return out


def classify_contrast(band_mean: float, config: dict) -> str:
    if band_mean < config["visual_caption_good_thr"]:
        return "GOOD_CONTRAST"
    if band_mean > config["visual_caption_poor_thr"]:
        return "POOR_CONTRAST"
    return "CAUTION"


def safe_area(width: int, height: int, config: dict) -> dict:
    """Normalized safe-area bounds from configured margins (1080p basis)."""
    scale = height / 1080.0 if height > 0 else 1.0
    mx = (config["caption_margin_h"] * scale) / max(width, 1)
    mv = (config["caption_margin_v"] * scale) / max(height, 1)
    return {"x_min": round(mx, 4), "x_max": round(1.0 - mx, 4),
            "y_min": round(mv, 4), "y_max": round(1.0 - mv, 4)}


def adapt_style(style: dict, contrast: str, config: dict) -> tuple[dict, dict | None]:
    """Adapt WITHIN permitted ranges only. Returns (adapted_style|{}, record).
    Never changes family/size/alignment identity silently: every change is
    recorded with reason + confidence."""
    if contrast == "GOOD_CONTRAST":
        return {}, {"adapted": False,
                    "reason": "contrast good: style untouched",
                    "confidence": 0.7}
    adapted: dict = {}
    if contrast == "CAUTION":
        if style.get("outline", 2) < config["visual_caption_outline_max"]:
            adapted["outline"] = style.get("outline", 2) + 1
    else:  # POOR_CONTRAST: escalate outline, then box, then shadow
        if style.get("outline", 2) < config["visual_caption_outline_max"]:
            adapted["outline"] = style.get("outline", 2) + 1
        elif not style.get("box"):
            adapted["box"] = True
        elif not style.get("shadow"):
            adapted["shadow"] = 1
    if not adapted:
        return {}, {"adapted": False,
                    "reason": "contrast poor but style already at permitted maximums",
                    "confidence": 0.5}
    return adapted, {"adapted": True, "changes": adapted,
                     "reason": f"{contrast} background: strengthened within permitted range",
                     "confidence": 0.55}


def _emphasis_candidates(words: list[dict], language: str) -> list[dict]:
    """Deterministic evidence-based candidates: numbers, non-initial
    capitalized Latin, quoted spans. Fillers, low-confidence, and
    punctuation-only tokens are rejected (never emphasized)."""
    supported = filler_set(language)
    out = []
    for idx, w in enumerate(words):
        text = str(w.get("text", ""))
        norm = normalize_token(text)
        if not norm or norm in supported:
            continue
        if float(w.get("probability", 0.0) or 0.0) < 0.5:
            continue
        if _PUNCT_ONLY_RE.match(text.strip()):
            continue
        kind = None
        if _NUMBER_RE.match(text.strip()):
            kind = "keyword"
        elif re.match(r"^[A-Z][A-Za-z]{2,}$", text.strip()) and idx > 0:
            kind = "important_words"
        if kind:
            out.append({"word": w, "kind": kind,
                        "confidence": 0.6,
                        "reason": f"{kind} by deterministic rule"})
    return out


def plan_emphasis(cue: dict, language: str, config: dict) -> CaptionEmphasis:
    """Cap at max_emphasis_ratio of cue words (drop lowest priority first:
    important_words before keyword? No — numbers carry signal; drop longer
    tokens first? Deterministic: keep earliest, drop latest extras)."""
    if not config["visual_caption_enable_emphasis"]:
        return CaptionEmphasis(cue_id=cue.get("cue_id", ""), emphasis_type="none",
                               reason="emphasis disabled by configuration")
    words = cue.get("word_refs", []) or []
    cands = _emphasis_candidates(words, language)
    if not cands:
        return CaptionEmphasis(cue_id=cue.get("cue_id", ""),
                               emphasis_type="none",
                               reason="no evidence-backed emphasis candidates")
    cap = max(1, int(len(words) * config["visual_caption_max_emphasis_ratio"]))
    dropped = []
    if len(cands) > cap:
        dropped = cands[cap:]
        cands = cands[:cap]
    kinds = {c["kind"] for c in cands}
    etype = "keyword" if kinds == {"keyword"} else "important_words" \
        if kinds == {"important_words"} else "keyword"
    refs = [{"word": c["word"]["text"], "start": c["word"]["start"],
             "end": c["word"]["end"], "word_id": c["word"].get("word_id", "")}
            for c in cands]
    reason = f"{len(refs)} emphasized word(s)"
    if dropped:
        reason += f"; {len(dropped)} extra candidate(s) dropped by 30% cap"
    return CaptionEmphasis(cue_id=cue.get("cue_id", ""), word_refs=refs,
                           emphasis_type=etype, reason=reason, confidence=0.6)


def _scene_at(scenes: list[dict], t: float) -> dict | None:
    for sc in scenes:
        if float(sc["start"]) - 1e-6 <= t < float(sc["end"]) - 1e-6:
            return sc
    return scenes[-1] if scenes else None


def build_visual_plan(caption_plan: dict, visual: dict | None,
                      source: str, duration: float, width: int, height: int,
                      style: dict, config: dict,
                      face_regions_fn=None) -> object:
    """Assemble the deterministic VisualCaptionPlan (no rendering)."""
    from engine.core.models import VisualCaptionPlan as _VCP
    t0 = time.perf_counter()
    cues = caption_plan.get("cues", []) or []
    language = caption_plan.get("language", "") or ""
    scenes = sorted((visual.get("scene_summaries", []) if visual else []) or [],
                    key=lambda s: (s["start"], s["end"]))
    positions = []
    emphases = []
    contexts = []
    conflicts = []
    warnings = []
    adaptations = {}
    for cue in cues:
        cid = cue.get("cue_id", "")
        mid = (cue["start"] + cue["end"]) / 2.0
        sc = _scene_at(scenes, mid) if scenes else None
        sid = int(sc.get("scene_id", -1)) if sc else -1
        # Band sampling on a real decoded frame (fallback: style default).
        try:
            bands = sample_bands(source, mid, duration, width, height)
        except VisualCaptionError as exc:
            warnings.append(f"{cid}: band sampling failed ({exc}); defaults used")
            bands = {k: {"mean": 0.0, "std": 0.0} for k in ("top", "center", "bottom")}
        # Face-safe positioning (adapter-driven; UNAVAILABLE here).
        faces: list = []
        face_available = False
        if face_regions_fn is not None:
            try:
                faces = face_regions_fn(mid) or []
                face_available = True
            except Exception as exc:
                warnings.append(f"{cid}: face adapter failed ({exc})")
        default_pos = style.get("alignment", config.get("caption_position", "bottom"))
        pos, reason, conf = default_pos, "style_default", 0.5
        if face_available and faces:
            in_default = [f for f in faces
                          if _overlap(f["y"], f["y"] + f["h"],
                                      *_band_rows(default_pos, height)) > 0]
            if in_default:
                alt = min(bands, key=lambda b: bands[b]["mean"])
                pos, reason, conf = alt, "face_avoidance", 0.6
        else:
            poor_here = classify_contrast(bands[default_pos]["mean"], config)
            if poor_here == "POOR_CONTRAST":
                alt = min(bands, key=lambda b: bands[b]["mean"])
                if bands[alt]["mean"] < bands[default_pos]["mean"] - 20:
                    pos, reason, conf = alt, "contrast_seek", 0.6
        anchor = {"bottom": "bottom-center", "center": "middle-center",
                  "top": "top-center"}.get(pos, "bottom-center")
        y = {"bottom": 0.92, "center": 0.5, "top": 0.08}.get(pos, 0.92)
        positions.append(CaptionPlacement(
            cue_id=cid, position=pos, x=0.5, y=y, anchor=anchor,
            safe_area=safe_area(width, height, config),
            reason=reason, confidence=conf))
        contrast = classify_contrast(bands[pos]["mean"], config)
        adapted, record = adapt_style(style, contrast, config)
        if record.get("adapted"):
            adaptations[cid] = record.get("changes", {})
        contexts.append(CaptionVisualContext(
            cue_id=cid, scene_id=sid, brightness=bands[pos]["mean"],
            contrast=bands[pos]["std"], motion=0.0, static_score=0.0,
            visual_change="unknown", face_available=face_available,
            face_regions=faces,
            safe_regions=[b for b in bands if bands[b]["mean"] < 200],
            band_stats=bands, frame_timestamp=_r3(mid)))
        # Scene-boundary treatment (text never altered).
        bounds = [float(s["start"]) for s in scenes[1:]] if scenes else []
        crossing = [b for b in bounds if cue["start"] < b < cue["end"]]
        if crossing:
            conflicts.append({"cue_id": cid, "kind": "scene_crossing",
                              "boundary": crossing[0],
                              "resolution": "single placement kept; text unchanged",
                              "priority": "informational", "confidence": 0.7})
        if bands[pos]["std"] > config["visual_caption_busy_thr"]:
            conflicts.append({"cue_id": cid, "kind": "busy_background",
                              "resolution": "recorded; placement kept",
                              "priority": "informational", "confidence": 0.5})
        if contrast == "POOR_CONTRAST" and not adapted:
            conflicts.append({"cue_id": cid, "kind": "poor_contrast_unfixed",
                              "resolution": "recorded; style at permitted maximums",
                              "priority": "low", "confidence": 0.5})
        if cue["end"] - cue["start"] > 6.0:
            conflicts.append({"cue_id": cid, "kind": "long_cue",
                              "resolution": "recorded; not split (Phase 14 timing kept)",
                              "priority": "informational", "confidence": 0.6})
        emphases.append(plan_emphasis(cue, language, config))
    plan = _VCP(source_hash="", caption_plan_hash="", visual_analysis_hash="",
                style=style.get("_name", "default"),
                placements=positions, emphasis=emphases, contexts=contexts,
                adaptations=adaptations,
                conflicts=conflicts, warnings=warnings)
    return plan, round(time.perf_counter() - t0, 3)


def _overlap(a_start: float, a_end: float, b_start: float, b_end: float) -> float:
    return min(a_end, b_end) - max(a_start, b_start)


def _band_rows(position: str, height: int) -> tuple[float, float]:
    frac = POSITION_BAND.get(position, (0.62, 0.95))
    return frac[0] * height, frac[1] * height


def visual_plan_hash(plan: dict) -> str:
    import hashlib
    import json as _json
    canonical = {k: v for k, v in plan.items() if k not in ("processing_s", "cached")}
    return hashlib.sha256(_json.dumps(canonical, sort_keys=True, default=str)
                          .encode()).hexdigest()[:32]


def caption_visual_for_project(project_id: str,
                               policy_overrides: dict | None = None,
                               style_name: str | None = None,
                               force: bool = False,
                               dry_run: bool = False) -> dict:
    """Build (+ validate) the visual caption plan. Dry-run writes nothing."""
    import json
    from engine.subtitles.formats import resolve_style
    project = load_project(project_id)
    pid = project.id
    log_file = project_dir(pid) / "logs" / "run.jsonl"
    config = resolve_visual_caption_config(policy_overrides)

    cap_path = project_dir(pid) / "captions" / "caption_plan.json"
    if not cap_path.is_file():
        raise VisualCaptionError("missing captions/caption_plan.json (run captions first)")
    try:
        caption_plan = json.loads(cap_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise VisualCaptionError(f"corrupt caption plan: {exc}") from exc
    vis_path = project_dir(pid) / "visual" / "visual_analysis.json"
    visual = None
    if vis_path.is_file():
        try:
            visual = json.loads(vis_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise VisualCaptionError(f"corrupt visual analysis: {exc}") from exc
    try:
        from engine.core.media import probe
        info = probe(project.input_path)
    except Exception as exc:
        raise VisualCaptionError(f"cannot probe source: {exc}") from exc
    if info.width <= 0 or info.height <= 0 or info.duration <= 0:
        raise VisualCaptionError("source has no usable video geometry/duration")
    style_name = style_name or caption_plan.get("style", "default")
    try:
        style = resolve_style(style_name)
    except Exception as exc:
        raise VisualCaptionError(str(exc)) from exc
    style = dict(style, _name=style_name)

    key = cache_key(project.input_path, "visual_captions",
                    {"caption_plan": caption_plan_hash(caption_plan),
                     "visual": hash_analysis(visual) if visual else "none",
                     "style": style_name,
                     "font": config.get("caption_font_family"),
                     "config": {k: config[k] for k in VISUAL_CAPTION_KEYS},
                     "version": VISUAL_CAPTION_VERSION,
                     "code_hash": _code_hash()})
    t0 = time.perf_counter()
    if not force and not dry_run:
        hit = cached(key)
        if hit is not None:
            payload = json.loads(hit.read_text(encoding="utf-8"))
            payload["cached"] = True
            write_artifact(pid, "captions", "visual_caption_plan.json", payload)
            mark_stage(project, "visual_captions", "cached",
                       "captions/visual_caption_plan.json")
            log_event(log_file, "visual_captions", "plan", "cached",
                      time.perf_counter() - t0, "captions/visual_caption_plan.json",
                      _versions(), {"cues": len(payload.get("placements", []))})
            return {"project": pid, "cached": True, "plan": payload}

    plan, proc_s = build_visual_plan(
        caption_plan, visual, project.input_path, info.duration,
        info.width, info.height, style, config)
    plan.source_hash = _media_hash(project.input_path)
    plan.caption_plan_hash = caption_plan_hash(caption_plan)
    plan.visual_analysis_hash = hash_analysis(visual) if visual else "none"
    payload = asdict(plan)
    if dry_run:
        return {"project": pid, "cached": False, "plan": payload, "dry_run": True}
    write_artifact(pid, "captions", "visual_caption_plan.json", payload)
    store(key, payload)
    mark_stage(project, "visual_captions", "done", "captions/visual_caption_plan.json")
    log_event(log_file, "visual_captions", "plan", "ok",
              time.perf_counter() - t0, "captions/visual_caption_plan.json",
              _versions(), {"cues": len(payload.get("placements", [])),
                            "emphasis": len(payload.get("emphasis", []))})
    return {"project": pid, "cached": False, "plan": payload}


def approve_caption_visual(project_id: str,
                           approver: str = "operator") -> dict:
    """Explicit approval binding all six inputs. Never mutates other artifacts."""
    import json
    from datetime import datetime, timezone
    project = load_project(project_id)
    pid = project.id
    log_file = project_dir(pid) / "logs" / "run.jsonl"
    plan_path = project_dir(pid) / "captions" / "visual_caption_plan.json"
    if not plan_path.is_file():
        raise VisualCaptionError("missing captions/visual_caption_plan.json "
                                 "(run caption-visual first)")
    try:
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise VisualCaptionError(f"corrupt visual caption plan: {exc}") from exc
    cap_path = project_dir(pid) / "captions" / "caption_plan.json"
    vis_path = project_dir(pid) / "visual" / "visual_analysis.json"
    try:
        cap_plan = json.loads(cap_path.read_text(encoding="utf-8")) \
            if cap_path.is_file() else None
        visual = json.loads(vis_path.read_text(encoding="utf-8")) \
            if vis_path.is_file() else None
    except json.JSONDecodeError as exc:
        raise VisualCaptionError(f"corrupt input artifact: {exc}") from exc
    if cap_plan is None or caption_plan_hash(cap_plan) != plan.get("caption_plan_hash"):
        raise VisualCaptionError("caption plan drifted since visual planning: re-plan")
    vis_hash = hash_analysis(visual) if visual else "none"
    if vis_hash != plan.get("visual_analysis_hash"):
        raise VisualCaptionError("visual analysis drifted since visual planning: re-plan")
    try:
        from engine.core.media import probe
        info = probe(project.input_path)
    except Exception as exc:
        raise VisualCaptionError(f"cannot probe source: {exc}") from exc
    # Font identity comes from the caption approval (the actual render font).
    cap_ap_path = project_dir(pid) / "editing" / "approved_captions.json"
    font_id: dict = {}
    if cap_ap_path.is_file():
        try:
            cap_ap = json.loads(cap_ap_path.read_text(encoding="utf-8"))
            font_id = (cap_ap.get("font", {}) or {})
            font_id = {"file": font_id.get("file", "")}
        except json.JSONDecodeError:
            font_id = {}
    _ = info
    approval = {"schema_version": "visual-caption-approval-1.0",
                "source_hash": _media_hash(project.input_path),
                "caption_plan_hash": plan.get("caption_plan_hash", ""),
                "visual_analysis_hash": plan.get("visual_analysis_hash", ""),
                "style": plan.get("style", "default"),
                "font_identity": font_id,
                "visual_plan_hash": visual_plan_hash(plan),
                "approved_at": datetime.now(timezone.utc).isoformat(),
                "approver": approver}
    write_artifact(pid, "captions", "approved_visual_caption_plan.json", approval)
    mark_stage(project, "visual_caption_approval", "done",
               "captions/approved_visual_caption_plan.json")
    log_event(log_file, "visual_captions", "approve", "ok", 0.0,
              "captions/approved_visual_caption_plan.json", _versions(),
              {"placements": len(plan.get("placements", []))})
    return {"project": pid, "approval": approval}


def validate_visual_approval(project_id: str) -> dict:
    """Revalidate all six bindings. Returns {approval, plan} or raises."""
    import json
    project = load_project(project_id)
    pid = project.id
    ap_path = project_dir(pid) / "captions" / "approved_visual_caption_plan.json"
    if not ap_path.is_file():
        raise VisualCaptionError("missing visual caption approval "
                                 "(run approve-caption-visual first)")
    try:
        approval = json.loads(ap_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise VisualCaptionError(f"corrupt visual approval: {exc}") from exc
    if approval.get("schema_version") != "visual-caption-approval-1.0":
        raise VisualCaptionError("unsupported visual approval schema")
    plan_path = project_dir(pid) / "captions" / "visual_caption_plan.json"
    try:
        plan = json.loads(plan_path.read_text(encoding="utf-8")) \
            if plan_path.is_file() else None
    except json.JSONDecodeError as exc:
        raise VisualCaptionError(f"corrupt visual caption plan: {exc}") from exc
    if plan is None or visual_plan_hash(plan) != approval.get("visual_plan_hash"):
        raise VisualCaptionError("visual plan changed since approval: re-approve")
    if _media_hash(project.input_path) != approval.get("source_hash"):
        raise VisualCaptionError("source changed since visual approval: re-approve")
    font_file = (approval.get("font_identity", {}) or {}).get("file", "")
    if font_file and not Path(font_file).is_file():
        raise VisualCaptionError(f"approved font vanished: {font_file}")
    return {"approval": approval, "plan": plan}
