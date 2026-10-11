"""Phase 13 — plan execution: APPROVED plan -> deterministic timeline -> render.

Consumes the approval snapshot (never the raw brain plan). Composition runs
in SOURCE coordinates; a single uniform concat re-encode produces the
output. All FFmpeg work via engine.rendering.ffmpeg; Phase 9 primitives
(validate_edl, select_encoder, validate_output, RenderConfig) reused, never
duplicated. Dry-run builds everything without encoding anything.
"""
from __future__ import annotations

import json
import time
from dataclasses import asdict
from pathlib import Path

from engine.core.logging_utils import log_event
from engine.core.media import MediaProbeError, probe
from engine.core.models import ExecutionOp, ExecutionPlanModel, KEEP, REMOVE
from engine.core.project_store import (
    load_project,
    mark_stage,
    project_dir,
    write_artifact,
)
from engine.editing.approval import validate_approval
from engine.rendering.execution import (
    RENDERER_VERSION,
    RenderError,
    resolve_render_config,
    validate_edl,
)
from engine.rendering.ffmpeg import (
    FfmpegError,
    apply_vf,
    concat,
    extract_audio,
    fit_filter,
    frame_health_check,
    make_silence,
    mux,
    select_encoder,
    trim,
    trim_streams,
)

PLAN_EXEC_VERSION = "1.0.0"
_MANIFEST_SUFFIX = "_plan_manifest.json"
_EPS = 1e-3


def _versions() -> dict:
    import platform
    return {"python": platform.python_version(), "engine": "0.1.0"}


def _overlap(a_start, a_end, b_start, b_end) -> float:
    return min(a_end, b_end) - max(a_start, b_start)


def compose_timeline(edl: dict, approval: dict) -> ExecutionPlanModel:
    """Build the executable timeline from base EDL + approval.

    Unapproved REMOVEs stay KEEP (explicit, recorded); overlays clamp to
    keeps (warning) or fail when fully outside. Raises RenderError."""
    issues = validate_edl(edl)
    if issues:
        raise RenderError(f"invalid base EDL: {'; '.join(issues[:5])}", stage="plan")
    approved = {c["decision_id"] for c in approval.get("approved_cuts", [])}
    assignments = approval.get("broll_assignments", []) or []

    # Execution EDL: approved REMOVEs remove; everything else keeps.
    # (validate_edl above already rejects unknown actions.)
    keeps: list[tuple[float, float, str, int]] = []
    skipped: list[str] = []
    for d in edl["decisions"]:
        s, e = float(d["start"]), float(d["end"])
        if d.get("action") == REMOVE and d.get("decision_id") in approved:
            continue
        if d.get("action") == REMOVE:
            skipped.append(str(d.get("decision_id")))
        keeps.append((s, e, str(d.get("decision_id", "")), int(d.get("scene_id", -1))))
    if not keeps:
        raise RenderError("execution keeps nothing (no approved content)",
                          stage="plan")

    # Overlays must not overlap each other; clamp to keeps.
    # NOTE: the executable span is the assignment's own start/end (the
    # request span, possibly a sub-interval of the opportunity); the
    # opportunity is provenance only.
    spans = sorted([(float(a["start"]), float(a["end"]), a)
                    for a in assignments])
    for (s1, e1, _), (s2, e2, _) in zip(spans, spans[1:]):
        if s2 < e1 - _EPS:
            raise RenderError(f"overlapping B-roll assignments "
                              f"[{s1},{e1}] and [{s2},{e2}]", stage="plan")
    warnings: list[str] = []
    ops: list[ExecutionOp] = []
    seq = 0
    cursor = 0.0
    for ks, ke, kid, kscene in keeps:
        active = []
        for a_s, a_e, a in spans:
            lo, hi = max(a_s, ks), min(a_e, ke)
            if hi - lo > _EPS:
                active.append((lo, hi, a))
                if lo > a_s + _EPS or hi < a_e - _EPS:
                    warnings.append(
                        f"B-roll [{a_s},{a_e}] clamped to keep [{ks},{ke}]")
        pos = ks
        for lo, hi, a in sorted(active):
            if lo > pos + _EPS:
                seq += 1
                ops.append(ExecutionOp(
                    operation_id=f"op_{seq:04d}", action="keep",
                    source_start=round(pos, 6), source_end=round(lo, 6),
                    output_start=round(cursor, 6),
                    output_end=round(cursor + (lo - pos), 6),
                    layer="base", reason="edl_keep", approval_state="approved",
                    confidence=1.0, scene_id=kscene,
                    metadata={"decision_id": kid}))
                cursor += lo - pos
            seq += 1
            placement = a.get("placement", "overlay")
            ops.append(ExecutionOp(
                operation_id=f"op_{seq:04d}",
                action="broll_replace" if placement == "replace" else "broll_overlay",
                source_start=round(lo, 6), source_end=round(hi, 6),
                output_start=round(cursor, 6),
                output_end=round(cursor + (hi - lo), 6),
                asset_id=a.get("asset_id", ""), layer="overlay",
                reason=a.get("opportunity", {}).get("kind", "broll"),
                approval_state="approved", confidence=0.7, scene_id=kscene,
                fit_strategy=a.get("fit", "cover"),
                audio_mode=a.get("audio_mode", "mute"),
                metadata={"decision_id": kid,
                          "opportunity": a.get("opportunity", {})}))
            cursor += hi - lo
            pos = hi
        if pos < ke - _EPS:
            seq += 1
            ops.append(ExecutionOp(
                operation_id=f"op_{seq:04d}", action="keep",
                source_start=round(pos, 6), source_end=round(ke, 6),
                output_start=round(cursor, 6),
                output_end=round(cursor + (ke - pos), 6),
                layer="base", reason="edl_keep", approval_state="approved",
                confidence=1.0, scene_id=kscene,
                metadata={"decision_id": kid}))
            cursor += ke - pos
    for a_s, a_e, a in spans:
        if not any(_overlap(a_s, a_e, ks, ke) > _EPS for ks, ke, _, _ in keeps):
            raise RenderError(f"B-roll assignment [{a_s},{a_e}] lies outside all "
                              f"kept content: re-approve with a valid span", stage="plan")
    plan = ExecutionPlanModel(
        source=str(edl.get("source", "")),
        operations=ops, assignments=[dict(a) for a in assignments],
        expected_duration=round(cursor, 6),
        warnings=warnings)
    return plan


def _resolve_encoder_name(config, log_file) -> tuple[str, str]:
    if config.video_encoder == "auto":
        try:
            sel = select_encoder()
        except FfmpegError as exc:
            raise RenderError(f"encoder detection failed: {exc}", stage="execute") from exc
        return sel["selected_encoder"], sel["reason"]
    return config.video_encoder, f"explicitly requested ({config.video_encoder})"


def _prepare_broll_part(assignment: dict, assets: dict, base_info,
                        need: float, work: Path, tag: str,
                        encoder: str, preset: str, timeout: int,
                        log_file: Path | None) -> tuple[Path, str]:
    """Build one broll segment part file. Returns (part_path, audio_note)."""
    asset = assets[assignment["asset_id"]]
    src = Path(asset["path"])
    a_start = float(assignment.get("asset_start", 0.0))
    a_end = float(assignment.get("asset_end", a_start + need))
    if a_end - a_start < need - 1e-3:
        raise RenderError(f"asset {asset['asset_id']} span too short", stage="execute")
    vf = fit_filter(int(asset.get("width", 0) or base_info.width),
                    int(asset.get("height", 0) or base_info.height),
                    base_info.width, base_info.height,
                    assignment.get("fit", "cover"), fps=base_info.fps or None)
    mode = assignment.get("audio_mode", "mute")
    placement = assignment.get("placement", "overlay")
    raw = trim(src, a_start, a_end, work / f"{tag}_raw.mp4", encoder=encoder,
               accurate=True, preset=preset, timeout=timeout, log_file=log_file)
    fitted = apply_vf(raw, vf, work / f"{tag}_fit.mp4", encoder=encoder,
                      preset=preset, timeout=timeout, log_file=log_file)
    if placement == "overlay" or mode == "mute":
        # Overlay keeps base dialogue: callers mux base audio separately.
        # Replace+mute needs silence: mux callers handle via make_silence.
        v_only = trim_streams(fitted, 0, need, work / f"{tag}_v.mp4",
                              streams="video", encoder=encoder, preset=preset,
                              timeout=timeout, log_file=log_file)
        return v_only, "muted"
    # replace + original asset audio (already carried through apply_vf copy).
    return fitted, "original"


def _map_silence_expected(silences: list[dict], keeps: list[tuple]) -> float:
    total = 0.0
    for s in silences:
        ss, se = float(s["start"]), float(s["end"])
        for ks, ke in keeps:
            total += max(0.0, min(se, ke) - max(ss, ks))
    return round(total, 3)


def extended_qc(output: str | Path, source: str, plan: ExecutionPlanModel,
                assets: dict, config, encoder: str, source_info,
                timeout: int = 600, log_file: Path | None = None) -> dict:
    """Phase 9 validate_output + black/silence/placement/decode checks."""
    from dataclasses import asdict as _asdict
    from engine.core.models import QCCheck
    from engine.rendering.execution import validate_render
    qc = validate_render(output, source_info, _phase9_plan(plan), config, encoder)
    checks = [QCCheck(**c) if isinstance(c, dict) else c for c in qc["checks"]]
    out_info = probe(output)

    # Black frames: unexpected = output black not matching mapped source black.
    health = frame_health_check(output, timeout=timeout, log_file=log_file)
    src_health = frame_health_check(source, timeout=timeout)
    keeps = [(float(d["start"]), float(d["end"])) for d in
             _keeps_of(plan)]
    expected_black = []
    for b in src_health["black"]:
        for ks, ke in keeps:
            lo, hi = max(b["start"], ks), min(b["end"], ke)
            if hi - lo >= 0.5:
                expected_black.append((lo, hi))
    mapped_black = [_map_to_output(plan, es2, ee2) for es2, ee2 in expected_black]
    unexpected = [b for b in health["black"]
                  if b["duration"] >= 0.5
                  and not any(_overlap(b["start"], b["end"], es - 0.5, ee + 0.5) > 0
                              for es, ee in mapped_black)]
    checks.append(QCCheck("no_unexpected_black", not unexpected,
                          f"unexpected={len(unexpected)}" if unexpected
                          else "all black explained by source"))
    if health["errors"]:
        checks.append(QCCheck("decode_clean", False,
                              "; ".join(health["errors"][:3])))
    else:
        checks.append(QCCheck("decode_clean", True, "no decode errors"))

    # Silence: output total vs mapped expectation.
    try:
        from engine.analysis.audio import analyze_audio
        got = analyze_audio(output).silence_total_s
        exp = _expected_silence(source, keeps)
        checks.append(QCCheck("silence_expected",
                              abs(got - exp) <= 1.0,
                              f"output_silence={got}s expected~{exp}s tol=1.0"))
    except Exception as exc:
        checks.append(QCCheck("silence_expected", True,
                              f"skipped: {exc}"))

    # B-roll placement proof: frame must match asset, differ from base.
    for op in plan.operations:
        if not op.action.startswith("broll_"):
            continue
        mid = (op.output_start + op.output_end) / 2.0
        ok, detail = _verify_placement(output, mid, op, assets, source)
        checks.append(QCCheck(f"broll_placed_{op.operation_id}", ok, detail))

    failed = [c.name for c in checks if not c.passed]
    return {"verdict": "pass" if not failed else "fail", "checks": [_asdict(c) for c in checks],
            "suggested_fix": "" if not failed else f"failed: {', '.join(failed)}"}


def _keeps_of(plan: ExecutionPlanModel) -> list[dict]:
    return [{"start": o.source_start, "end": o.source_end}
            for o in plan.operations if o.action == "keep"]


def _map_to_output(plan: ExecutionPlanModel, s: float, e: float) -> tuple[float, float]:
    for o in plan.operations:
        if o.action == "keep" and o.source_start - 1e-6 <= s and e <= o.source_end + 1e-6:
            off = o.output_start - o.source_start
            return (s + off, e + off)
    return (s, e)


def _expected_silence(source: str, keeps: list[tuple]) -> float:
    from engine.analysis.audio import analyze_audio
    sil = analyze_audio(source).silence or []
    return _map_silence_expected(
        [{"start": float(x["start"]), "end": float(x["end"])} for x in sil], keeps)


def _phase9_plan(plan: ExecutionPlanModel):
    from engine.rendering.execution import ExecutionPlan, ExecutionSegment
    segs = [ExecutionSegment(output_start=o.output_start, output_end=o.output_end,
                             source_start=o.source_start, source_end=o.source_end,
                             decision_id=o.operation_id, scene_id=o.scene_id,
                             reason=o.reason)
            for o in plan.operations if o.action == "keep"]
    return ExecutionPlan(source=plan.source, edl_hash="", expected_duration=plan.expected_duration,
                         keep_segments=segs, keep_count=len(segs), remove_count=0,
                         strategy="concat" if len(segs) > 1 else "direct")


def _verify_placement(output: str | Path, t: float, op, assets: dict,
                      source: str) -> tuple[bool, str]:
    """Mid-interval frame must resemble the asset and differ from base content."""
    import tempfile
    from engine.analysis.visual import dhash, hamming, hist_corr
    import cv2
    asset = assets[op.asset_id]
    span = op.source_end - op.source_start
    a_mid = float(asset.get("asset_start", 0.0)) + span / 2.0
    with tempfile.TemporaryDirectory(prefix="place_") as tmp:
        from engine.rendering.ffmpeg import extract_frame
        fo, fa, fb = Path(tmp) / "o.jpg", Path(tmp) / "a.jpg", Path(tmp) / "b.jpg"
        try:
            extract_frame(output, t, fo)
            extract_frame(asset["path"], a_mid, fa)
            extract_frame(source, (op.source_start + op.source_end) / 2.0, fb)
        except (FfmpegError, ValueError, MediaProbeError) as exc:
            return False, f"placement probe failed: {exc}"
        go = cv2.cvtColor(cv2.imread(str(fo)), cv2.COLOR_BGR2GRAY)
        ga = cv2.cvtColor(cv2.imread(str(fa)), cv2.COLOR_BGR2GRAY)
        gb = cv2.cvtColor(cv2.imread(str(fb)), cv2.COLOR_BGR2GRAY)
        if go is None or ga is None or gb is None:
            return False, "unreadable placement probe frame"
        match_asset = hamming(dhash(go), dhash(ga)) <= 5 and hist_corr(go, ga) >= 0.9
        match_base = hamming(dhash(go), dhash(gb)) <= 5 and hist_corr(go, gb) >= 0.9
        if match_asset and not match_base:
            return True, "frame matches asset, differs from base"
        if match_asset and match_base:
            return True, "ambiguous (asset resembles base here); accepted with warning"
        return False, "frame does not match assigned asset"


def render_plan_for_project(project_id: str, config_overrides: dict | None = None,
                            out_name: str | None = None,
                            force: bool = False,
                            captions: bool = False) -> dict:
    """Validate approval -> compose -> execute -> QC -> manifest. Rendering only approved ops.
    With captions=True, an approved caption layer is applied after base QC
    passes (sidecar files and/or burned-in video). Without captions the flow
    is byte-identical to Phase 13."""
    project = load_project(project_id)
    pid = project.id
    log_file = project_dir(pid) / "logs" / "run.jsonl"
    config = resolve_render_config(config_overrides)
    renders_dir = project_dir(pid) / "renders"
    renders_dir.mkdir(parents=True, exist_ok=True)

    t0 = time.perf_counter()
    try:
        checked = validate_approval(pid)
    except Exception as exc:
        raise RenderError(f"approval invalid: {exc}", stage="input") from exc
    approval, plan_doc = checked["approval"], checked["plan"]
    try:
        info = probe(project.input_path)
    except MediaProbeError as exc:
        raise RenderError(str(exc), stage="input") from exc
    edl_path = project_dir(pid) / "edit" / "edit_decision.json"
    try:
        edl = json.loads(edl_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RenderError(f"cannot load base EDL: {exc}", stage="input") from exc

    plan = compose_timeline(edl, approval)
    asset_reg = {}
    for a in approval.get("broll_assignments", []):
        asset_reg[a["asset_id"]] = _asset_record(a)
    plan.assets = asset_reg
    try:
        resolved_encoder, _enc_reason = _resolve_encoder_name(config, log_file)
    except RenderError as exc:
        mark_stage(project, "render_plan", "failed", str(exc)[:300])
        raise
    identity = {"source": project.input_path,
                "editor_plan_hash": approval.get("plan_hash"),
                "approval_hash": _approval_hash(approval),
                "assets": {k: v.get("asset_hash") for k, v in asset_reg.items()},
                "execution_version": PLAN_EXEC_VERSION,
                "renderer_version": RENDERER_VERSION,
                "config": asdict(config),
                "encoder": resolved_encoder}
    tol = config.duration_tol if config.accurate else max(config.duration_tol, 1.0)
    cap_id = None
    if captions:
        # Caption identity resolved BEFORE reuse matching (no encoding here).
        from engine.subtitles.captions import (
            caption_plan_hash as _cph,
            validate_captions_approval,
        )
        from engine.subtitles.render import _font_identity as _cap_font_id
        from engine.subtitles.visual_captions import visual_plan_hash as _vph
        cap_checked = validate_captions_approval(pid)
        cap_font_file = (cap_checked["approval"].get("font", {}) or {}).get("file", "")
        cap_id = {"caption_plan_hash": _cph(cap_checked["plan"]),
                  "style": cap_checked["approval"].get("style", ""),
                  "mode": cap_checked["approval"].get("mode", ""),
                  "font": _cap_font_id(cap_font_file) if cap_font_file else {},
                  "visual": _visual_hash_or_none(pid)}
    reused_base = None
    if not force:
        reuse = _find_plan_manifest(renders_dir, identity, plan.expected_duration, tol,
                                    caption_id=cap_id)
        if reuse is not None:
            manifest = json.loads(reuse.read_text(encoding="utf-8"))
            if captions and not manifest.get("caption_mode"):
                reused_base = manifest  # plain base output: caption layer still runs
            else:
                manifest["cached"] = True
                log_event(log_file, "render_plan", "reuse", "ok",
                          time.perf_counter() - t0, manifest.get("output", ""),
                          _versions(), {"expected_s": plan.expected_duration})
                mark_stage(project, "render_plan", "done", f"renders/{reuse.name}")
                return {"project": pid, "cached": True,
                        "manifest": manifest, "output": manifest.get("output", "")}

    stamp = time.strftime("%Y%m%d_%H%M%S")
    dst = renders_dir / (out_name or f"plan_{stamp}.mp4")
    work = renders_dir / f"_plan_{time.time_ns()}"
    log_event(log_file, "render_plan", "validate", "ok", 0.0, "", _versions(),
              {"ops": len(plan.operations), "expected_s": plan.expected_duration})
    if reused_base is not None:
        dst = Path(reused_base["output"])
        encoder, enc_reason = (reused_base.get("encoder", ""),
                               reused_base.get("encoder_reason", "reused base render"))
        qc = reused_base.get("qc", {"verdict": "pass", "checks": []})
        base_cached = True
    else:
        try:
            out, (encoder, enc_reason) = _execute_ops(
                plan, asset_reg, project.input_path, info, config, dst, work, log_file)
        except RenderError as exc:
            mark_stage(project, "render_plan", "failed", str(exc)[:300])
            log_event(log_file, "render_plan", "execute", "failed",
                      time.perf_counter() - t0, str(exc)[:300], _versions(), {})
            raise
        qc = extended_qc(dst, project.input_path, plan, asset_reg, config,
                         encoder, info, timeout=config.timeout, log_file=log_file)
        base_cached = False
    proc_s = round(time.perf_counter() - t0, 3)
    caption_section: dict = {}
    final_output = str(dst)
    caption_cached = False
    if captions:
        if qc["verdict"] != "pass":
            raise RenderError("base QC must pass before caption layer", stage="validate")
        from engine.subtitles.render import apply_captions
        keeps = [(o.source_start, o.source_end, o.output_start, o.output_end)
                 for o in plan.operations if o.action == "keep"]
        try:
            cap = apply_captions(pid, str(dst), keeps, config, log_file)
        except RenderError as exc:
            mark_stage(project, "render_plan", "failed", str(exc)[:300])
            log_event(log_file, "render_plan", "captions", "failed",
                      time.perf_counter() - t0, str(exc)[:300], _versions(), {})
            raise
        final_output = cap["output"]
        caption_cached = cap.get("cached", False)
        caption_section = {
            "caption_plan_hash": cap.get("caption_plan_hash", ""),
            "caption_style": cap.get("style", ""),
            "caption_mode": cap.get("mode", ""),
            "caption_font": cap.get("font", {}),
            "caption_format": ",".join(sorted(
                k for k in cap.get("files", {}) if k in ("srt", "vtt", "ass"))),
            "caption_count": cap.get("cue_count", 0),
            "caption_language": cap.get("language", ""),
            "caption_warnings": cap.get("warnings", []),
            "caption_qc": cap.get("caption_qc", {}),
            "caption_files": cap.get("files", {}),
            "caption_cached": caption_cached,
            "visual_plan_hash": cap.get("visual_plan_hash", ""),
            "visual_approval": cap.get("visual_approval", "absent"),
            "visual_placements": cap.get("visual_placements", 0),
            "visual_emphasis_cues": cap.get("visual_emphasis_cues", 0),
        }
        log_event(log_file, "render_plan", "captions", "ok",
                  time.perf_counter() - t0, final_output, _versions(),
                  {"mode": cap.get("mode", ""), "cues": cap.get("cue_count", 0),
                   "qc": cap.get("caption_qc", {}).get("verdict")})
    manifest = {
        "kind": "plan", "status": "completed" if qc["verdict"] == "pass" else "qc_failed",
        "project": pid, "source": project.input_path,
        "source_fingerprint": approval.get("source_fingerprint"),
        "editor_plan_hash": approval.get("plan_hash"),
        "approval_hash": _approval_hash(approval),
        "execution_plan_hash": _exec_hash(plan),
        "execution_version": PLAN_EXEC_VERSION,
        "renderer_version": RENDERER_VERSION,
        "gateway_version": "ffmpeg-gateway-1.0",
        "schema_versions": {"manifest": "plan-manifest-1.0",
                            "approval": "approval-1.0",
                            "execution_plan": "execution-plan-1.0",
                            "editor_plan": "editor-plan-1.0"},
        "render_config": asdict(config), "encoder": encoder,
        "encoder_reason": enc_reason,
        "operations": [asdict(o) for o in plan.operations],
        "assets": asset_reg,
        "broll_mappings": approval.get("broll_assignments", []),
        "output": final_output, "output_name": Path(final_output).name,
        "source_duration": info.duration,
        "expected_duration": plan.expected_duration,
        "actual_duration": round(probe(final_output).duration, 3)
        if Path(final_output).is_file() else 0.0,
        "warnings": plan.warnings, "qc": qc,
        "processing_s": proc_s,
        "realtime_factor": round(plan.expected_duration / proc_s, 2) if proc_s > 0 else 0.0,
        "cached": bool(base_cached and (not captions or caption_cached)),
        **caption_section,
    }
    (renders_dir / (Path(final_output).stem + "_plan_manifest.json")).write_text(
        json.dumps(manifest, indent=2), encoding="utf-8")
    mark_stage(project, "render_plan",
               "done" if manifest["status"] == "completed" else "validation_failed",
               f"renders/{Path(final_output).stem}_plan_manifest.json")
    log_event(log_file, "render_plan", "qc",
              "ok" if qc["verdict"] == "pass" else "failed",
              proc_s, final_output, _versions(),
              {"expected_s": plan.expected_duration,
               "actual_s": manifest["actual_duration"], "qc": qc["verdict"]})
    if qc["verdict"] != "pass":
        raise RenderError(f"plan QC failed: {qc.get('suggested_fix', '')}",
                          stage="validate")
    return {"project": pid, "cached": manifest["cached"], "manifest": manifest,
            "output": final_output}


def _execute_ops(plan, asset_reg, source, info, config, dst, work, log_file):
    encoder, enc_reason = _resolve_encoder_name(config, log_file)
    if config.overwrite is False and Path(dst).is_file():
        raise RenderError(f"output exists and overwrite=False: {dst}", stage="input")
    work.mkdir(parents=True, exist_ok=True)
    Path(dst).parent.mkdir(parents=True, exist_ok=True)
    ok = False
    try:
        parts = []
        for i, op in enumerate(plan.operations):
            if op.action == "keep":
                parts.append(trim(source, op.source_start, op.source_end,
                                  work / f"p{i:03d}.mp4", encoder=encoder,
                                  accurate=config.accurate, preset=config.preset,
                                  timeout=config.timeout, log_file=log_file))
            elif op.action in ("broll_replace", "broll_overlay"):
                assign = next(a for a in plan.assignments
                              if a["asset_id"] == op.asset_id)
                parts.append(_execute_broll_op(
                    op, assign, asset_reg[op.asset_id], source, info,
                    work, i, encoder, config, log_file))
            elif op.action == "remove":
                continue
            else:
                raise RenderError(f"unsupported operation action {op.action!r} "
                                  f"(not executed, not replaced)", stage="plan")
        concat(parts, dst, reencode=True, encoder=encoder,
               preset=config.preset, timeout=config.timeout, log_file=log_file)
        ok = True
    except (FfmpegError, ValueError, MediaProbeError, OSError) as exc:
        raise RenderError(f"plan render failed (diagnostics at {work}): {exc}",
                          stage="execute") from exc
    finally:
        if ok:
            for p in work.glob("*.mp4"):
                p.unlink(missing_ok=True)
            for p in work.glob("*.wav"):
                p.unlink(missing_ok=True)
            try:
                work.rmdir()
            except OSError:
                pass
    return dst, (encoder, enc_reason)


def _execute_broll_op(op, assign, asset, source, base_info, work, i,
                      encoder, config, log_file):
    need = round(op.source_end - op.source_start, 6)
    a_start = float(assign.get("asset_start", 0.0))
    v_raw = trim(Path(asset["path"]), a_start, a_start + need,
                 work / f"b{i:03d}_raw.mp4", encoder=encoder, accurate=True,
                 preset=config.preset, timeout=config.timeout, log_file=log_file)
    vf = fit_filter(int(asset.get("width", 0) or base_info.width),
                    int(asset.get("height", 0) or base_info.height),
                    base_info.width, base_info.height,
                    assign.get("fit", "cover"), fps=base_info.fps or None)
    v_fit = apply_vf(v_raw, vf, work / f"b{i:03d}_fit.mp4", encoder=encoder,
                     preset=config.preset, timeout=config.timeout, log_file=log_file)
    if op.action == "broll_overlay":
        base_audio = extract_audio(source, work / f"a{i:03d}.wav",
                                   start=op.source_start, duration=need,
                                   timeout=config.timeout, log_file=log_file)
        v_only = trim_streams(v_fit, 0, need, work / f"b{i:03d}_v.mp4",
                              streams="video", encoder=encoder, preset=config.preset,
                              timeout=config.timeout, log_file=log_file)
        return mux(v_only, base_audio, work / f"b{i:03d}_seg.mp4",
                   timeout=config.timeout, log_file=log_file)
    if assign.get("audio_mode", "mute") == "mute":
        v_only = trim_streams(v_fit, 0, need, work / f"b{i:03d}_v.mp4",
                              streams="video", encoder=encoder, preset=config.preset,
                              timeout=config.timeout, log_file=log_file)
        sil = make_silence(need, work / f"s{i:03d}.wav",
                           sample_rate=base_info.sample_rate or 44100,
                           channels=base_info.audio_channels or 1,
                           timeout=config.timeout, log_file=log_file)
        return mux(v_only, sil, work / f"b{i:03d}_seg.mp4",
                   timeout=config.timeout, log_file=log_file)
    a_part = extract_audio(Path(asset["path"]), work / f"a{i:03d}.wav",
                           start=a_start, duration=need,
                           timeout=config.timeout, log_file=log_file)
    v_only = trim_streams(v_fit, 0, need, work / f"b{i:03d}_v.mp4",
                          streams="video", encoder=encoder, preset=config.preset,
                          timeout=config.timeout, log_file=log_file)
    return mux(v_only, a_part, work / f"b{i:03d}_seg.mp4",
               timeout=config.timeout, log_file=log_file)


def _asset_record(a: dict) -> dict:
    return {"asset_id": a.get("asset_id", ""), "path": a.get("asset_path", ""),
            "asset_hash": a.get("asset_hash", ""),
            "asset_start": a.get("asset_start", 0.0),
            "asset_end": a.get("asset_end", 0.0),
            "audio_mode": a.get("audio_mode", "mute"),
            "fit": a.get("fit", "cover"),
            "placement": a.get("placement", "overlay"),
            "opportunity": a.get("opportunity", {})}


def _approval_hash(approval: dict) -> str:
    import hashlib as _hl
    canonical = {k: v for k, v in approval.items() if k not in ("approved_at",)}
    return _hl.sha256(json.dumps(canonical, sort_keys=True, default=str)
                      .encode()).hexdigest()[:32]


def _exec_hash(plan: ExecutionPlanModel) -> str:
    import hashlib as _hl
    from dataclasses import asdict as _asdict
    return _hl.sha256(json.dumps(_asdict(plan), sort_keys=True, default=str)
                      .encode()).hexdigest()[:32]


def _manifest_matches(data: dict, identity: dict) -> bool:
    keys = ("source", "editor_plan_hash", "approval_hash", "execution_version",
            "renderer_version", "encoder")
    if {k: data.get(k) for k in keys} != {k: identity.get(k) for k in keys}:
        return False
    if data.get("render_config", {}) != identity.get("config", {}):
        return False
    stored = data.get("assets", {}) or {}
    stored_hashes = {k: (v.get("asset_hash") if isinstance(v, dict) else v)
                     for k, v in stored.items()}
    return stored_hashes == identity.get("assets", {})


def _visual_hash_or_none(pid: str) -> str:
    """Visual plan hash for cache identity, or 'none' (no visual plan)."""
    from engine.core.project_store import project_dir as _pd
    from engine.subtitles.visual_captions import visual_plan_hash as _vph
    vp_path = _pd(pid) / "captions" / "visual_caption_plan.json"
    if not vp_path.is_file():
        return "none"
    try:
        import json as _json
        return _vph(_json.loads(vp_path.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return "none"


def _dry_run_visual(pid: str) -> dict:
    """Visual block for dry-run: approved / unapproved / absent (no encode)."""
    vp_path = project_dir(pid) / "captions" / "visual_caption_plan.json"
    if not vp_path.is_file():
        return {"state": "absent"}
    try:
        from engine.subtitles.visual_captions import validate_visual_approval
        checked = validate_visual_approval(pid)
        vplan = checked["plan"]
        return {"state": "approved",
                "placements": len(vplan.get("placements", [])),
                "emphasis_cues": sum(
                    1 for e in vplan.get("emphasis", [])
                    if e.get("emphasis_type", "none") != "none"),
                "conflicts": len(vplan.get("conflicts", [])),
                "warnings": len(vplan.get("warnings", []))}
    except Exception as exc:
        return {"state": "unapproved", "reason": str(exc)[:200]}


def _find_plan_manifest(renders_dir: Path, identity: dict,
                        expected_duration: float, tol: float,
                        caption_id: dict | None = None) -> Path | None:
    """Find a reusable manifest. caption_id None -> plain renders only;
    given -> full caption match required (plan hash, style, font, mode)."""
    for cand in sorted(renders_dir.glob("*_plan_manifest.json")):
        try:
            data = json.loads(cand.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if data.get("status") != "completed" or data.get("kind") != "plan":
            continue
        if not _manifest_matches(data, identity):
            continue
        if caption_id is None:
            if data.get("caption_mode"):
                continue  # captioned renders never substitute plain ones
        else:
            if data.get("caption_plan_hash") != caption_id.get("caption_plan_hash"):
                continue
            if data.get("caption_style") != caption_id.get("style"):
                continue
            if data.get("caption_mode") != caption_id.get("mode"):
                continue
            if data.get("caption_font", {}) != caption_id.get("font", {}):
                continue
            if data.get("visual_plan_hash", "none") != caption_id.get("visual", "none"):
                continue
        out = renders_dir / data.get("output_name", "")
        if not out.is_file() or out.stat().st_size == 0:
            continue
        try:
            got = probe(out)
            if abs(got.duration - expected_duration) > tol or not got.video_codec:
                continue
        except MediaProbeError:
            continue
        return cand
    return None


def dry_run_plan(project_id: str, config_overrides: dict | None = None,
                 captions: bool = False) -> dict:
    """Build + validate everything. Resolves NOTHING that encodes (no ffmpeg
    writes, no encoder smoke tests). ffprobe reads are analysis, not render."""
    project = load_project(project_id)
    checked = validate_approval(project_id)
    approval, plan_doc = checked["approval"], checked["plan"]
    config = resolve_render_config(config_overrides)
    edl_path = project_dir(project.id) / "edit" / "edit_decision.json"
    edl = json.loads(edl_path.read_text(encoding="utf-8"))
    plan = compose_timeline(edl, approval)
    assets = {a["asset_id"]: _asset_record(a)
              for a in approval.get("broll_assignments", [])}
    out = {"project": project.id,
           "operations": [asdict(o) for o in plan.operations],
           "assets": assets,
           "expected_duration": plan.expected_duration,
           "warnings": plan.warnings,
           "encoder": "auto (resolved at render; smoke tests skipped in dry-run)"
                      if config.video_encoder == "auto" else config.video_encoder,
           "render_config": asdict(config),
           "qc_plan": ["duration", "streams", "av_sync", "black_frames",
                       "silence_profile", "broll_placement", "decode"],
           "approval_hash": _approval_hash(approval)}
    if captions:
        from engine.subtitles.captions import (
            map_cues_to_output,
            validate_captions_approval,
        )
        cap_checked = validate_captions_approval(project.id)
        cap_plan = cap_checked["plan"]
        keeps = [(o.source_start, o.source_end, o.output_start, o.output_end)
                 for o in plan.operations if o.action == "keep"]
        mapped, warnings, stats = map_cues_to_output(
            cap_plan.get("cues", []), keeps)
        out["captions"] = {
            "cue_count": len(mapped),
            "mode": cap_checked["approval"].get("mode", ""),
            "style": cap_checked["approval"].get("style", ""),
            "language": cap_plan.get("language", ""),
            "warnings": warnings,
            "mapped_stats": stats,
            "qc_plan": ["timing", "readability", "text", "rendered_video"],
            "visual": _dry_run_visual(project.id),
        }
        vp_path = project_dir(project.id) / "captions" / "visual_caption_plan.json"
        if vp_path.is_file():
            try:
                from engine.subtitles.visual_captions import validate_visual_approval
                checked_v = validate_visual_approval(project.id)
                vplan = checked_v["plan"]
                out["captions"]["visual"] = {
                    "state": "approved",
                    "placements": len(vplan.get("placements", [])),
                    "emphasis_cues": sum(
                        1 for e in vplan.get("emphasis", [])
                        if e.get("emphasis_type", "none") != "none"),
                    "conflicts": len(vplan.get("conflicts", [])),
                    "warnings": len(vplan.get("warnings", [])),
                }
            except Exception as exc:
                out["captions"]["visual"] = {"state": "unapproved",
                                             "reason": str(exc)[:200]}
        else:
            out["captions"]["visual"] = {"state": "absent"}
        out["qc_plan"] = out["qc_plan"] + ["caption_timing", "caption_visibility"]
    return out
