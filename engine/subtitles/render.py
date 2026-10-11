"""Phase 14 — caption execution: mapped cues -> sidecars / burned-in video.

Consumes the caption approval (never the raw brain-style plan). Sidecar
mode writes derived files beside the base render; burned-in mode adds one
documented post-render ASS pass through the gateway. Base manifests stay
byte-identical when captions are off.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from engine.core.logging_utils import log_event
from engine.core.media import probe
from engine.rendering.execution import RenderError
from engine.rendering.ffmpeg import burn_subtitles, extract_frame
from engine.subtitles.captions import (
    CaptionError,
    map_cues_to_output,
    validate_captions_approval,
    validate_cues,
)
from engine.subtitles.formats import resolve_style, write_ass, write_srt, write_vtt

CAPTION_SCALE_VERSION = "caption-exec-1.0"


def _versions() -> dict:
    import platform
    return {"python": platform.python_version(), "engine": "0.1.0"}


def _font_identity(font_file: str) -> dict:
    p = Path(font_file)
    try:
        st = p.stat()
        return {"file": str(p), "size": st.st_size, "mtime_ns": st.st_mtime_ns}
    except OSError as exc:
        raise RenderError(f"caption font unreadable: {exc}", stage="input") from exc


def caption_sidecars(mapped: list[dict], renders_dir: Path, stem: str,
                     language: str = "") -> dict:
    """Write derived sidecar files. Pure file I/O (no ffmpeg)."""
    renders_dir.mkdir(parents=True, exist_ok=True)
    srt_path = renders_dir / f"{stem}.srt"
    vtt_path = renders_dir / f"{stem}.vtt"
    srt_path.write_text(write_srt(mapped), encoding="utf-8")
    vtt_path.write_text(write_vtt(mapped, language), encoding="utf-8")
    return {"srt": str(srt_path), "vtt": str(vtt_path)}


def verify_sidecars(files: dict, mapped: list[dict]) -> dict:
    """Roundtrip QC: re-parse sidecars and compare against mapped cues."""
    from engine.subtitles.formats import srt_time, vtt_time
    checks: list[dict] = []

    def _check(name: str, ok: bool, detail: str):
        checks.append({"name": name, "passed": ok, "detail": detail})

    for key in ("srt", "vtt"):
        p = Path(files[key])
        _check(f"sidecar_{key}_exists", p.is_file() and p.stat().st_size > 0,
               f"{p.stat().st_size} bytes" if p.is_file() else "missing")
    try:
        srt_text = Path(files["srt"]).read_text(encoding="utf-8")
        blocks = [b for b in srt_text.strip().split("\n\n") if b.strip()]
        _check("sidecar_srt_count", len(blocks) == len(mapped),
               f"srt={len(blocks)} mapped={len(mapped)}")
        if blocks and mapped:
            first, last = blocks[0].splitlines(), blocks[-1].splitlines()
            _check("sidecar_srt_bounds",
                   first[1].startswith(srt_time(mapped[0]["start"])[:8])
                   and last[1].startswith(srt_time(mapped[-1]["start"])[:8]),
                   "first/last cue times roundtrip")
    except OSError as exc:
        _check("sidecar_srt_parse", False, str(exc))
    failed = [c["name"] for c in checks if not c["passed"]]
    return {"verdict": "pass" if not failed else "fail", "checks": checks,
            "suggested_fix": "" if not failed else f"failed: {', '.join(failed)}"}


def visible_caption_check(captioned: str | Path, base: str | Path,
                          mapped: list[dict], limit: int = 3,
                          position: str = "bottom") -> dict:
    """Sample cue midpoints on captioned vs base video: subtitle pixels must
    differ in the caption band. Metric is the top-5% mean abs-diff inside
    the band (text edges dominate; re-encode noise is ~0.2, text is ~25+).
    Proves visible burn-in (not file existence)."""
    import cv2
    import numpy as np
    import tempfile
    band = {"bottom": (0.75, 1.0), "center": (0.375, 0.625),
            "top": (0.0, 0.25)}.get(position, (0.75, 1.0))
    checks: list[dict] = []

    def _check(name: str, ok: bool, detail: str):
        checks.append({"name": name, "passed": ok, "detail": detail})

    picks = [c for c in mapped if c["text"].strip()][:limit]
    if not picks:
        return {"verdict": "pass", "checks": [],
                "suggested_fix": "", "note": "no cues to sample"}
    diffs = []
    with tempfile.TemporaryDirectory(prefix="capq_") as tmp:
        for i, cue in enumerate(picks):
            mid = (cue["start"] + cue["end"]) / 2.0
            fo, fb = Path(tmp) / f"o{i}.jpg", Path(tmp) / f"b{i}.jpg"
            try:
                extract_frame(captioned, mid, fo)
                extract_frame(base, mid, fb)
            except Exception as exc:
                _check(f"caption_visible_{i}", False, f"probe failed: {exc}")
                continue
            io = cv2.imread(str(fo))
            ib = cv2.imread(str(fb))
            if io is None or ib is None or io.shape != ib.shape:
                _check(f"caption_visible_{i}", False, "unreadable probe frame")
                continue
            r0, r1 = int(io.shape[0] * band[0]), int(io.shape[0] * band[1])
            d = np.abs(io[r0:r1].astype(float) - ib[r0:r1].astype(float)).mean(axis=2)
            flat = np.sort(d.reshape(-1))
            top5 = float(flat[int(len(flat) * 0.95):].mean())
            diffs.append(top5)
            _check(f"caption_visible_{i}", top5 > 12.0,
                   f"band top-5% mean-abs-diff={top5:.1f} (thr 12.0; noise ~0.2)")
    failed = [c["name"] for c in checks if not c["passed"]]
    return {"verdict": "pass" if not failed else "fail", "checks": checks,
            "suggested_fix": "" if not failed else f"failed: {', '.join(failed)}",
            "mean_diff": round(sum(diffs) / len(diffs), 2) if diffs else 0.0}


def apply_captions(pid: str, base_output: str, keeps: list[tuple],
                   config, log_file: Path | None = None) -> dict:
    """Full caption layer for one render. Returns caption manifest section."""
    from engine.core.project_store import project_dir
    from engine.subtitles.captions import caption_plan_hash
    renders_dir = project_dir(pid) / "renders"
    checked = validate_captions_approval(pid)
    approval, plan = checked["approval"], checked["plan"]
    mode = approval.get("mode", "sidecar")
    style_name = approval.get("style", "default")
    style = resolve_style(style_name)
    font = approval.get("font", {}) or {}

    mapped, warnings, stats = map_cues_to_output(plan.get("cues", []), keeps)
    issues = _validate_mapped(mapped)
    if issues:
        raise RenderError(f"mapped caption cues invalid: {issues[:3]}", stage="validate")

    # Visual polish: used only when a visual plan AND its approval are both
    # present and valid. Anything else renders standard captions + a warning
    # (never silently applies unapproved visual changes).
    visual_state = _resolve_visual_state(pid, mapped, style_name, font)
    if visual_state["warnings"]:
        warnings.extend(visual_state["warnings"])

    base = Path(base_output)
    stem = base.stem + "_captioned" if mode == "burned_in" else base.stem
    cap_key_path = renders_dir / f"{Path(base_output).stem}_captions.json"
    font_id = _font_identity(font.get("file", ""))
    cap_identity = {"caption_plan_hash": caption_plan_hash(plan),
                    "style": style_name, "font": font_id, "mode": mode,
                    "mapped_cues": len(mapped),
                    "visual": visual_state["identity"]}
    if cap_key_path.is_file():
        try:
            prev = json.loads(cap_key_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            prev = None
        if prev and prev.get("identity") == cap_identity:
            if prev.get("output") and Path(prev["output"]).is_file():
                prev["cached"] = True
                return prev

    t0 = time.perf_counter()
    files: dict = {}
    caption_qc: dict = {"verdict": "pass", "checks": [], "suggested_fix": ""}
    output = str(base)
    if mode == "sidecar":
        files = caption_sidecars(mapped, renders_dir, base.stem,
                                 plan.get("language", ""))
        caption_qc = verify_sidecars(files, mapped)
    else:
        from engine.subtitles.formats import write_ass_visual
        from engine.subtitles.visual_captions import visual_plan_hash
        if visual_state["active"]:
            ass_text = write_ass_visual(
                mapped, style, font.get("family", "Arial"), *(_frame_size(base)),
                placements=visual_state["placements"],
                emphasis=visual_state["emphasis"],
                adaptations=visual_state["adaptations"])
        else:
            ass_text = write_ass(mapped, style, font.get("family", "Arial"),
                                 *(_frame_size(base)))
        ass_path = renders_dir / f"{stem}.ass"
        ass_path.write_text(ass_text, encoding="utf-8")
        files["ass"] = str(ass_path)
        dst = renders_dir / f"{stem}.mp4"
        burn_subtitles(base, ass_path, dst,
                       encoder=config.video_encoder, preset=config.preset,
                       fontsdir="C:/Windows/Fonts",
                       timeout=config.timeout, log_file=log_file)
        output = str(dst)
        files["video"] = output
        caption_qc = visible_caption_check(dst, base, mapped,
                                           position=style.get("alignment", "bottom"))
        # Audio must be untouched by the burn (stream copy by design).
        base_info, out_info = probe(base), probe(dst)
        same_audio = (base_info.audio_codec == out_info.audio_codec
                      and abs(base_info.duration - out_info.duration) <= 0.3)
        caption_qc["checks"].append(
            {"name": "caption_audio_preserved", "passed": same_audio,
             "detail": f"{base_info.audio_codec}->{out_info.audio_codec}"})
        if not same_audio:
            caption_qc["verdict"] = "fail"
            caption_qc["suggested_fix"] = "burn altered audio"

    result = {"mode": mode, "style": style_name, "font": font_id,
              "language": plan.get("language", ""),
              "caption_plan_hash": cap_identity["caption_plan_hash"],
              "cue_count": len(mapped), "mapped_stats": stats,
              "warnings": warnings + plan.get("warnings", []),
              "files": files, "output": output,
              "caption_qc": caption_qc, "identity": cap_identity,
              "visual_plan_hash": visual_state.get("plan_hash", ""),
              "visual_approval": visual_state.get("approval_state", "absent"),
              "visual_placements": len(visual_state.get("placements", {})),
              "visual_emphasis_cues": len(visual_state.get("emphasis", {})),
              "processing_s": round(time.perf_counter() - t0, 3),
              "cached": False}
    # Visual QC checks ride along (fail only on invalid geometry/corruption).
    if visual_state["active"]:
        for check in _visual_qc_checks(mapped, visual_state):
            caption_qc["checks"].append(check)
            if not check["passed"]:
                caption_qc["verdict"] = "fail"
                caption_qc["suggested_fix"] = (
                    caption_qc.get("suggested_fix", "") + f" {check['name']};").strip()
    cap_key_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    if caption_qc["verdict"] != "pass":
        raise RenderError(f"caption QC failed: {caption_qc.get('suggested_fix', '')}",
                          stage="validate")
    return result


def _frame_size(path: str | Path) -> tuple[int, int]:
    info = probe(path)
    if info.width <= 0 or info.height <= 0:
        raise RenderError(f"unknown frame size for {path}", stage="validate")
    return info.width, info.height


def _resolve_visual_state(pid: str, mapped: list[dict],
                          style_name: str, font: dict) -> dict:
    """Decide whether visual polish applies. Returns placements/emphasis/
    adaptations maps + cache identity + warnings. Standard captions render
    whenever visual approval is absent or invalid (recorded, never silent)."""
    from engine.core.project_store import project_dir as _pd
    from engine.subtitles.visual_captions import (
        validate_visual_approval,
        visual_plan_hash,
    )
    none_state = lambda warnings: {
        "active": False, "placements": {}, "emphasis": {},
        "adaptations": {}, "identity": "none", "warnings": warnings,
        "plan_hash": "", "approval_state": "absent"}
    plan_path = _pd(pid) / "captions" / "visual_caption_plan.json"
    if not plan_path.is_file():
        return none_state([])
    try:
        checked = validate_visual_approval(pid)
    except Exception as exc:
        return none_state([f"visual plan unapproved ({exc}); standard captions rendered"])
    plan = checked["plan"]
    placements, emphasis, adaptations = {}, {}, {}
    for p in plan.get("placements", []) or []:
        placements[p.get("cue_id", "")] = p.get("position", "bottom")
    for e in plan.get("emphasis", []) or []:
        if e.get("emphasis_type", "none") == "none":
            continue
        seen: dict[str, int] = {}
        spans = []
        for r in e.get("word_refs", []) or []:
            key = str(r.get("word", ""))
            spans.append({"text": key, "occurrence": seen.get(key, 0),
                          "kind": e["emphasis_type"]})
            seen[key] = seen.get(key, 0) + 1
        emphasis[e.get("cue_id", "")] = spans
    for cid, patch in (plan.get("adaptations", {}) or {}).items():
        if isinstance(patch, dict) and patch:
            adaptations[cid] = patch
    return {"active": True, "placements": placements, "emphasis": emphasis,
            "adaptations": adaptations,
            "identity": visual_plan_hash(plan),
            "warnings": plan.get("warnings", [])[:5],
            "plan_hash": visual_plan_hash(plan),
            "approval_state": "valid"}


def _visual_qc_checks(mapped: list[dict], visual_state: dict) -> list[dict]:
    """Placement/emphasis/RTL integrity. Invalid geometry or corruption
    fails; contrast advisories never fail (recorded in the plan)."""
    checks = []
    if not visual_state["active"]:
        return checks
    for c in mapped:
        base_id = str(c.get("cue_id", "")).split("+")[0]
        pos = visual_state["placements"].get(c.get("cue_id", ""), None)
        if pos is None:
            pos = visual_state["placements"].get(base_id, "bottom")
        ok_pos = pos in ("top", "center", "bottom")
        checks.append({"name": f"visual_placement_{c.get('cue_id')}",
                       "passed": ok_pos,
                       "detail": f"position={pos}"})
        # Emphasis spans resolve to cue words by (text, occurrence); every
        # span must sit inside cue bounds (timing from transcript refs).
        by_text: dict[str, list[dict]] = {}
        for w in c.get("word_refs", []) or []:
            by_text.setdefault(str(w.get("text", "")), []).append(w)
        used: dict[str, int] = {}
        spans = visual_state["emphasis"].get(
            c.get("cue_id", ""), visual_state["emphasis"].get(base_id, []))
        bad_timing = 0
        for s in spans:
            lst = by_text.get(s.get("text", ""), [])
            n = used.get(s.get("text", ""), 0)
            used[s.get("text", "")] = n + 1
            if n >= len(lst):
                bad_timing += 1
                continue
            w = lst[n]
            if not (c["start"] - 1e-3 <= w["start"] and w["end"] <= c["end"] + 1e-3):
                bad_timing += 1
        checks.append({"name": f"visual_emphasis_{c.get('cue_id')}",
                       "passed": bad_timing == 0,
                       "detail": f"{len(spans)} span(s), {bad_timing} outside cue"})
    # Arabic integrity: stripped ASS-source words survive in order.
    rtl_cues = [c for c in mapped if any(
        "\u0600" <= ch <= "\u06ff" for ch in c.get("text", ""))]
    for c in rtl_cues:
        words = [w.get("text", "") for w in c.get("word_refs", [])]
        intact = all(w in c.get("text", "") for w in words if w.strip())
        checks.append({"name": f"visual_rtl_{c.get('cue_id')}",
                       "passed": bool(intact),
                       "detail": "logical-order words intact" if intact
                       else "word/text mismatch"})
    return checks
    info = probe(path)
    if info.width <= 0 or info.height <= 0:
        raise RenderError(f"unknown frame size for {path}", stage="validate")
    return info.width, info.height


def _validate_mapped(mapped: list[dict]) -> list[str]:
    issues: list[str] = []
    for i, c in enumerate(mapped):
        if not c["end"] > c["start"]:
            issues.append(f"{c.get('cue_id', i)}: end not > start")
        if not c["text"].strip():
            issues.append(f"{c.get('cue_id', i)}: empty text")
        try:
            c["text"].encode("utf-8", "strict")
        except UnicodeError:
            issues.append(f"{c.get('cue_id', i)}: invalid unicode")
        if i > 0 and c["start"] < mapped[i - 1]["end"] - 1e-3:
            issues.append(f"{c.get('cue_id', i)}: overlaps previous cue")
    return issues
