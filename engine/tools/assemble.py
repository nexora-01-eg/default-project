"""Render assembly driven by planner-owned motion/camera (no fit workaround).

Contract per shot: motion/camera objects {type, parameters, reason,
source}. The assembler executes exactly what the plan requests:
technical normalization (fps/scale/concat) is allowed; creative
substitution is not. Unsupported operations raise a structured
CAPABILITY_MISSING instead of silently substituting.
"""
from __future__ import annotations

from pathlib import Path

from engine.tools.adapters.base import ToolUnavailable

MOVE_TYPES = ("push", "pull", "pan", "tilt", "slide")
COVER_TYPES = ("cut", "hold", "static", "none", "medium", "wide")
CROP_TYPES = {"punch": 1.15, "close": 1.2, "detail": 1.35,
              "reframe": 1.15}

SUPPORTED_VIDEO = set(COVER_TYPES) | set(MOVE_TYPES) | set(CROP_TYPES)


class CapabilityMissing(ToolUnavailable):
    def __init__(self, subsystem: str, requested: str, reason: str):
        super().__init__(f"{subsystem}:{requested}",
                         f"CAPABILITY_MISSING: {reason}")
        self.subsystem = subsystem
        self.requested = requested


def _norm_type(obj: dict | str | None) -> str:
    if obj is None:
        return "hold"
    if isinstance(obj, str):
        return obj.strip().lower() or "hold"
    return str(obj.get("type", "hold")).strip().lower() or "hold"


CAMERA_OK = ({"static", "none", "hold"} | set(MOVE_TYPES) |
             {"close", "medium", "wide", "detail", "reframe"})
MOTION_VIDEO_OK = set(SUPPORTED_VIDEO) | {"fade", "rise", "emphasis"}


def resolve_transform(motion, camera) -> dict:
    """Decide the video transform from planner objects. Pure.

    Precedence: an explicit camera move owns the transform; otherwise
    the motion type drives it. Anything outside the supported tables
    raises structured CAPABILITY_MISSING (never substituted).
    """
    mtype = _norm_type(motion)
    ctype = _norm_type(camera)
    if ctype not in CAMERA_OK:
        from engine.tools import motion_system as _ms
        desc = _ms.describe(ctype)
        need = desc.get("missing") or {}
        raise CapabilityMissing(
            "camera", ctype,
            f"renderer does not support planner-selected camera "
            f"({need.get('reason', 'no execution path')})")
    if mtype not in MOTION_VIDEO_OK and mtype not in MOVE_TYPES:
        from engine.tools import motion_system as _ms
        desc = _ms.describe(mtype)
        need = desc.get("missing") or {}
        raise CapabilityMissing(
            "motion", mtype,
            f"renderer does not support planner-selected operation "
            f"({need.get('reason', 'no execution path')}; "
            f"alt: {need.get('alternative', 'none')})")
    if ctype in MOVE_TYPES:
        effective, source = ctype, "camera"
    else:
        effective, source = mtype, "motion"
    if effective in COVER_TYPES:
        return {"op": "cover", "source": source, "requested_motion": mtype,
                "requested_camera": ctype}
    if effective in ("push", "pull"):
        z0, z1 = (1.0, 1.12) if effective == "push" else (1.12, 1.0)
        return {"op": "zoompan", "source": source, "requested_motion": mtype,
                "requested_camera": ctype, "zoom_from": z0, "zoom_to": z1}
    if effective in ("pan", "slide"):
        return {"op": "zoompan-x", "source": source,
                "requested_motion": mtype, "requested_camera": ctype}
    if effective == "tilt":
        return {"op": "zoompan-y", "source": source,
                "requested_motion": mtype, "requested_camera": ctype}
    if effective in CROP_TYPES:
        return {"op": "crop", "source": source, "requested_motion": mtype,
                "requested_camera": ctype,
                "factor": CROP_TYPES[effective]}
    from engine.tools import motion_system as _ms
    desc = _ms.describe(effective)
    need = (desc.get("missing") or {})
    raise CapabilityMissing(
        "camera" if source == "camera" else "motion", effective,
        f"renderer does not support planner-selected operation "
        f"({need.get('reason', 'no execution path')}; "
        f"alt: {need.get('alternative', 'none')})")


def detect_mismatch(entry: dict) -> dict | None:
    """Compare executed op against both requested mappings. Pure."""
    op = entry.get("op")
    mtype = str(entry.get("requested_motion", "")).lower()
    ctype = str(entry.get("requested_camera", "")).lower()

    def _ok(t: str) -> bool:
        if op == "cover":
            return t in COVER_TYPES
        if op == "zoompan":
            return t in ("push", "pull")
        if op in ("zoompan-x",):
            return t in ("pan", "slide")
        if op == "zoompan-y":
            return t == "tilt"
        if op == "crop":
            return t in CROP_TYPES
        return False

    source = str(entry.get("effective_source", "")).lower()
    if source == "camera":
        ok = _ok(ctype)
    elif source == "motion":
        ok = _ok(mtype)
    else:
        ok = _ok(mtype) or _ok(ctype)
    if ok:
        return None
    return {"mismatch": "EXECUTION_MISMATCH", "requested_motion": mtype,
            "requested_camera": ctype, "executed": op}


def _zoompan_vf(mode: str, z0: float = 1.0, z1: float = 1.12,
                w: int = 1080, h: int = 1920) -> str:
    n = 900  # normalized ramp; actual length follows input frames
    if mode == "zoompan":
        return (f"scale=2160:3840,zoompan=z='{z0}+({z1}-{z0})*on/{n}':"
                f"d=1:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
                f"s={w}x{h}:fps=30")
    if mode == "zoompan-x":
        return (f"scale=2160:3840,zoompan=z='1.12':d=1:"
                f"x='(iw-iw/zoom)*on/{n}':y='ih/2-(ih/zoom/2)':"
                f"s={w}x{h}:fps=30")
    return (f"scale=2160:3840,zoompan=z='1.12':d=1:"
            f"x='iw/2-(iw/zoom/2)':y='(ih-ih/zoom)*on/{n}':"
            f"s={w}x{h}:fps=30")


def render_shot(seg: dict, ars_dir: str | Path, workdir: str | Path, *,
                w: int = 1080, h: int = 1920, fps: int = 30,
                encoder: str = "h264_qsv") -> dict:
    """Render one planned segment to a part file + manifest entry."""
    from engine.core.media import probe
    from engine.rendering.ffmpeg import (apply_vf, color_clip, fit_filter,
                                         trim)
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    label = seg.get("shot_id", seg.get("label", "seg"))
    spec = resolve_transform(seg.get("motion"), seg.get("camera"))
    op = spec["op"]
    if seg.get("kind") == "card" or not seg.get("file"):
        dur = float(seg.get("len") or seg.get("dur") or 2.0)
        part = workdir / f"{label}.mp4"
        color_clip(seg.get("color", "0x0B102E"), w, h, dur, part, fps=fps)
        entry = {"shot": label, "requested_motion": spec["requested_motion"],
                 "requested_camera": spec["requested_camera"],
                 "effective_source": spec["source"], "op": "card",
                 "params": {"dur": dur}, "result": str(part)}
    else:
        src = Path(ars_dir) / seg["file"]
        s, e = seg["span"]
        info = probe(src)
        tmp = workdir / f"{label}_raw.mp4"
        trim(src, s, e, tmp, encoder=encoder)
        if op == "cover":
            vf = fit_filter(info.width, info.height, w, h, "cover", fps=fps)
        elif op.startswith("zoompan"):
            z0 = spec.get("zoom_from", 1.0)
            z1 = spec.get("zoom_to", 1.12)
            vf = _zoompan_vf(op, z0, z1, w, h)
        elif op == "crop":
            f = spec["factor"]
            cw, ch = round(w / f), round(h / f)
            vf = (fit_filter(info.width, info.height, w, h, "cover",
                             fps=fps) +
                  f",crop={cw}:{ch},scale={w}:{h}")
        else:  # pragma: no cover - resolve_transform guards this
            raise CapabilityMissing("motion", op, "unhandled op")
        part = workdir / f"{label}.mp4"
        apply_vf(tmp, vf, part, encoder=encoder)
        tmp.unlink(missing_ok=True)
        entry = {"shot": label, "requested_motion": spec["requested_motion"],
                 "requested_camera": spec["requested_camera"],
                 "effective_source": spec["source"], "op": op,
                 "params": {"span": [s, e],
                            **{k: v for k, v in spec.items()
                               if k.startswith("zoom") or k == "factor"}},
                 "result": str(part)}
    mismatch = detect_mismatch(entry)
    if mismatch:
        entry["mismatch"] = mismatch
    return {"part": part, "manifest": entry}


def build_audio(narr_parts: list, music: dict, sting: dict | None,
                total: float, workdir: str | Path,
                sample_rate: int = 44100) -> dict:
    """Deterministic narration + ducked bed (+sting) mix. Gateway ops only."""
    from engine.rendering.ffmpeg import (concat, extract_audio, fade_audio,
                                         gain_audio, make_silence, mix_audio)
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    track = []
    for p in narr_parts:
        if p["kind"] == "silence":
            track.append(make_silence(p["dur"], workdir / p["name"],
                                      sample_rate=sample_rate, channels=2))
        else:
            track.append(extract_audio(
                p["src"], workdir / p["name"], sample_rate=sample_rate,
                channels=2, start=p.get("start"), duration=p.get("dur")))
    narr = concat(track, workdir / "narr.wav", reencode=False)
    mus = extract_audio(music["src"], workdir / "mus.wav", start=2.0,
                        duration=total, sample_rate=sample_rate, channels=2)
    faded = workdir / "musf.m4a"
    fade_audio(mus, faded, fade_in=2.0, fade_out=3.0)
    slices = []
    for k, st in enumerate(music["states"]):
        sl = workdir / f"au{k:02d}.m4a"
        extract_audio(faded, sl, start=st["start"],
                      duration=round(st["end"] - st["start"], 3))
        if st["gain_db"]:
            gl = workdir / f"aug{k:02d}.m4a"
            gain_audio(sl, gl, gain_db=st["gain_db"])
            sl.unlink(missing_ok=True)
            sl = gl
        slices.append(sl)
    bed = workdir / "bed.m4a"
    concat(slices, bed, reencode=False)
    bedw = extract_audio(bed, workdir / "bed.wav", sample_rate=sample_rate,
                         channels=2)
    inputs = [narr, bedw]
    if sting:
        s0 = extract_audio(sting["src"], workdir / "st0.m4a", start=0.0,
                           duration=sting.get("dur", 1.2))
        sq = workdir / "stq.m4a"
        gain_audio(s0, sq, gain_db=sting.get("gain_db", -12.0))
        inputs.append(sq)
    mixed = mix_audio(inputs, workdir / "mixed.m4a")
    safe = gain_audio(mixed, workdir / "safe.m4a", gain_db=-1.5)
    return {"narr": str(narr), "bed": str(bed), "mixed": str(safe)}
