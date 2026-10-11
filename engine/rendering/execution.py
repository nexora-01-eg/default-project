"""Phase 9 — EDL execution: SOURCE + EDL + CONFIG -> rendered master + manifest.

The renderer EXECUTES decisions; it never invents them. All FFmpeg work goes
through engine.rendering.ffmpeg (trim/concat/select_encoder/validate_output);
this module contains zero ffmpeg argv construction and zero subprocess calls.

Flow: validate EDL -> execution plan (source->output offsets) -> trim keeps
-> join -> validate (incl. A/V sync) -> manifest. Reuse path revalidates the
existing output before declaring a cache hit; corrupt outputs re-render.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from engine.core.logging_utils import log_event
from engine.core.media import MediaProbeError, probe
from engine.core.models import KEEP, REMOVE, QCCheck, RenderConfig
from engine.core.project_store import (
    load_project,
    mark_stage,
    project_dir,
    write_artifact,
)
from engine.rendering.ffmpeg import (
    ENCODER_CODEC,
    FfmpegError,
    ValidateExpect,
    concat,
    select_encoder,
    trim,
    validate_output,
)

RENDERER_VERSION = "1.0.0"
_GAP_EPS = 1e-3
_MANIFEST_SUFFIX = "_manifest.json"


class RenderError(RuntimeError):
    """Clear execution failure. `stage` is plan | execute | validate | input."""

    def __init__(self, message: str, stage: str = "execute"):
        super().__init__(message)
        self.stage = stage


@dataclass
class ExecutionSegment:
    output_start: float
    output_end: float
    source_start: float
    source_end: float
    decision_id: str = ""
    scene_id: int = -1
    reason: str = ""


@dataclass
class ExecutionPlan:
    source: str
    edl_hash: str
    expected_duration: float
    keep_segments: list[ExecutionSegment] = field(default_factory=list)
    keep_count: int = 0
    remove_count: int = 0
    strategy: str = "concat"  # direct (single keep) | concat


def resolve_render_config(overrides: dict | None = None) -> RenderConfig:
    cfg = RenderConfig()
    for key, value in (overrides or {}).items():
        if not hasattr(cfg, key):
            raise RenderError(f"unknown render config key {key!r}", stage="input")
        setattr(cfg, key, value)
    if cfg.fps_policy != "source":
        raise RenderError("Phase 9 supports fps_policy='source' only", stage="input")
    if cfg.resolution_policy != "source":
        raise RenderError("Phase 9 supports resolution_policy='source' only", stage="input")
    if cfg.container != "mp4":
        raise RenderError("Phase 9 supports container='mp4' only", stage="input")
    if cfg.duration_tol <= 0 or cfg.av_sync_tol <= 0 or cfg.timeout <= 0:
        raise RenderError("duration_tol/av_sync_tol/timeout must be > 0", stage="input")
    return cfg


def edl_hash(edl: dict) -> str:
    """Identity over decisions+policy+source+duration (NOT wall-clock/cached)."""
    canonical = {"source": edl.get("source", ""),
                 "duration": edl.get("duration", 0),
                 "decisions": edl.get("decisions", []),
                 "policy": edl.get("policy", {})}
    return hashlib.sha256(
        json.dumps(canonical, sort_keys=True, default=str).encode()).hexdigest()[:32]


def validate_edl(edl: dict, duration: float | None = None) -> list[str]:
    """Pre-render EDL check. Returns issues (empty = valid). Never repairs."""
    issues: list[str] = []
    if not isinstance(edl, dict) or not isinstance(edl.get("decisions"), list):
        return ["edl has no decisions list"]
    decisions = edl["decisions"]
    if not decisions:
        return ["edl has zero decisions"]
    total = duration if duration is not None else edl.get("duration", 0)
    try:
        total = float(total)
    except (TypeError, ValueError):
        return [f"invalid duration {total!r}"]
    if total <= 0:
        return [f"invalid duration {total}"]
    prev_end: float | None = None
    kept = removed = 0.0
    for i, d in enumerate(decisions):
        try:
            s, e = float(d["start"]), float(d["end"])
        except (KeyError, TypeError, ValueError):
            issues.append(f"decision {i}: invalid interval")
            continue
        if d.get("action") not in (KEEP, REMOVE):
            issues.append(f"decision {i}: invalid action {d.get('action')!r}")
        if not e > s:
            issues.append(f"decision {i}: end {e} not > start {s}")
        if s < -0.05:
            issues.append(f"decision {i}: negative start {s}")
        if e > total + 0.05:
            issues.append(f"decision {i}: end {e} exceeds duration {total}")
        if prev_end is not None:
            if s < prev_end - _GAP_EPS:
                issues.append(f"decision {i}: overlaps previous (gap-free violated)")
            elif s > prev_end + 0.05:
                issues.append(f"decision {i}: gap before start (starts {s}, prev ends {prev_end})")
        if i == 0 and s > 0.05:
            issues.append(f"edl does not start at 0 (starts {s})")
        prev_end = e
        if d.get("action") == KEEP:
            kept += max(0.0, e - s)
        elif d.get("action") == REMOVE:
            removed += max(0.0, e - s)
    if prev_end is not None and prev_end < total - 0.05:
        issues.append(f"edl ends at {prev_end}, duration is {total}")
    if abs((kept + removed) - total) > 0.05:
        issues.append(f"keep+remove={kept + removed:.3f} != duration {total}")
    return issues


def build_execution_plan(edl: dict, source: str = "") -> ExecutionPlan:
    """Validate then map KEEP segments to output offsets. Raises RenderError."""
    issues = validate_edl(edl)
    if issues:
        raise RenderError(f"invalid EDL, refusing to render: {'; '.join(issues[:5])}",
                          stage="plan")
    plan = ExecutionPlan(source=source or str(edl.get("source", "")),
                         edl_hash=edl_hash(edl), expected_duration=0.0)
    cursor = 0.0
    for d in edl["decisions"]:
        if d.get("action") != KEEP:
            plan.remove_count += 1
            continue
        s, e = float(d["start"]), float(d["end"])
        plan.keep_segments.append(ExecutionSegment(
            output_start=round(cursor, 6), output_end=round(cursor + (e - s), 6),
            source_start=s, source_end=e,
            decision_id=str(d.get("decision_id", "")),
            scene_id=int(d.get("scene_id", -1)),
            reason=str(d.get("reason", ""))))
        cursor += e - s
        plan.keep_count += 1
    plan.expected_duration = round(cursor, 6)
    plan.strategy = "direct" if plan.keep_count == 1 else "concat"
    if plan.keep_count == 0:
        raise RenderError("EDL keeps nothing: refusing to render empty output",
                          stage="plan")
    return plan


def _resolve_encoder(config: RenderConfig, log_file: Path | None) -> tuple[str, str]:
    if config.video_encoder == "auto":
        try:
            sel = select_encoder()
        except FfmpegError as exc:
            raise RenderError(f"encoder detection failed: {exc}", stage="execute") from exc
        return sel["selected_encoder"], sel["reason"]
    return config.video_encoder, f"explicitly requested ({config.video_encoder})"


def execute_plan(plan: ExecutionPlan, source: str, config: RenderConfig,
                 dst: str | Path, workdir: str | Path | None = None,
                 log_file: Path | None = None) -> Path:
    """Render KEEP segments to dst. Sources never modified. Raises RenderError."""
    src_p, dst_p = Path(source), Path(dst)
    try:
        info = probe(src_p)
    except MediaProbeError as exc:
        raise RenderError(str(exc), stage="input") from exc
    if not info.video_codec:
        raise RenderError(f"audio-only sources cannot be rendered to video: {src_p}",
                          stage="input")
    if info.duration <= 0:
        raise RenderError(f"unknown source duration: {src_p}", stage="input")
    encoder, enc_reason = _resolve_encoder(config, log_file)
    if log_file:
        log_event(log_file, "render", "plan", "ok", 0.0, str(dst_p), {},
                  {"segments": plan.keep_count, "encoder": encoder,
                   "reason": enc_reason, "strategy": plan.strategy,
                   "expected_s": plan.expected_duration})

    if config.overwrite is False and dst_p.is_file():
        raise RenderError(f"output exists and overwrite=False: {dst_p}", stage="input")
    work = Path(workdir) if workdir else dst_p.parent / f"_exec_{time.time_ns()}"
    work.mkdir(parents=True, exist_ok=True)
    dst_p.parent.mkdir(parents=True, exist_ok=True)
    ok = False
    try:
        parts = [trim(src_p, seg.source_start, seg.source_end,
                      work / f"keep{i:03d}.mp4", encoder=encoder,
                      accurate=config.accurate, preset=config.preset,
                      timeout=config.timeout, log_file=log_file)
                 for i, seg in enumerate(plan.keep_segments)]
        if plan.strategy == "direct":
            shutil.copyfile(parts[0], dst_p)
        else:
            concat(parts, dst_p, reencode=True, encoder=encoder,
                   preset=config.preset, timeout=config.timeout, log_file=log_file)
        ok = True
    except (FfmpegError, ValueError, MediaProbeError, OSError) as exc:
        raise RenderError(f"render failed (diagnostics retained at {work}): {exc}",
                          stage="execute") from exc
    finally:
        if ok:  # success: temp parts go; failure: workdir stays for diagnosis
            for p in work.glob("keep*.mp4"):
                p.unlink(missing_ok=True)
            try:
                work.rmdir()
            except OSError:
                pass
    return dst_p


def validate_render(output: str | Path, source_info, plan: ExecutionPlan,
                    config: RenderConfig, encoder: str) -> dict:
    """validate_output + start-time/sync extras. Returns QCReport dict."""
    expect_tol = config.duration_tol if config.accurate else max(config.duration_tol, 1.0)
    report = validate_output(output, ValidateExpect(
        duration=plan.expected_duration, duration_tol=expect_tol,
        width=source_info.width or None, height=source_info.height or None,
        fps=source_info.fps or None,
        video_codec=ENCODER_CODEC.get(encoder),
        audio_codec=config.audio_codec if source_info.audio_codec else None,
        require_audio=bool(source_info.audio_codec),
        av_sync_tol=config.av_sync_tol))
    checks = report.checks
    out_info = probe(output)
    checks.append(QCCheck(
        "video_start_time", abs(out_info.video_start_time) <= 0.1,
        f"video start={out_info.video_start_time:.3f}s"))
    if out_info.audio_streams:
        a0 = out_info.audio_streams[0]
        checks.append(QCCheck(
            "audio_start_time", abs(float(a0.get("start_time", 0))) <= 0.5,
            f"audio start={a0.get('start_time', 0)}s"))
        a_dur = float(a0.get("duration", 0) or 0)
        if a_dur > 0:
            delta = abs(out_info.duration - a_dur)
            checks.append(QCCheck(
                "av_duration_delta", delta <= config.av_sync_tol,
                f"|container-audio|={delta:.3f}s tol={config.av_sync_tol}"))
    failed = [c.name for c in checks if not c.passed]
    report.verdict = "pass" if not failed else "fail"
    if failed:
        report.suggested_fix = f"failed: {', '.join(failed)}"
    return asdict(report)


def _manifest_identity(source: str, edl_h: str, config: RenderConfig) -> dict:
    return {"source": source, "edl_hash": edl_h,
            "config": asdict(config), "renderer_version": RENDERER_VERSION}


def _find_reusable_manifest(renders_dir: Path, identity: dict,
                            expected_duration: float,
                            tol: float) -> Path | None:
    """A reuse candidate is valid only if its output exists AND re-probes OK."""
    for cand in sorted(renders_dir.glob("*" + _MANIFEST_SUFFIX)):
        try:
            data = json.loads(cand.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if data.get("status") != "completed":
            continue
        if {k: data.get(k) for k in ("source", "edl_hash", "renderer_version")} != \
           {k: identity.get(k) for k in ("source", "edl_hash", "renderer_version")}:
            continue
        if (data.get("config", {}) != identity.get("config", {})):
            continue
        out = renders_dir / data.get("output_name", "")
        if not out.is_file() or out.stat().st_size == 0:
            continue
        try:
            if abs(probe(out).duration - expected_duration) > tol:
                continue  # corrupted/changed output: never reuse
        except MediaProbeError:
            continue
        return cand
    return None


def render_edl_for_project(project_id: str, config_overrides: dict | None = None,
                           out_name: str | None = None) -> dict:
    """Full Phase 9 flow. Returns {project, cached, manifest, output}."""
    project = load_project(project_id)
    pid = project.id
    log_file = project_dir(pid) / "logs" / "run.jsonl"
    config = resolve_render_config(config_overrides)
    renders_dir = project_dir(pid) / "renders"
    renders_dir.mkdir(parents=True, exist_ok=True)

    edl_path = project_dir(pid) / "edit" / "edit_decision.json"
    if not edl_path.is_file():
        raise RenderError(f"missing EDL edit/edit_decision.json (run edit first)",
                          stage="input")
    try:
        edl = json.loads(edl_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RenderError(f"corrupt EDL: {exc}", stage="input") from exc
    try:
        info = probe(project.input_path)
    except MediaProbeError as exc:
        raise RenderError(str(exc), stage="input") from exc

    plan = build_execution_plan(edl, source=project.input_path)  # validates (plan stage)
    identity = _manifest_identity(project.input_path, plan.edl_hash, config)
    tol = config.duration_tol if config.accurate else max(config.duration_tol, 1.0)
    t0 = time.perf_counter()

    reuse = _find_reusable_manifest(renders_dir, identity, plan.expected_duration, tol)
    if reuse is not None:
        manifest = json.loads(reuse.read_text(encoding="utf-8"))
        manifest["cached"] = True
        log_event(log_file, "render", "reuse", "ok", time.perf_counter() - t0,
                  manifest.get("output", ""), _versions(),
                  {"edl_hash": plan.edl_hash, "manifest": reuse.name})
        mark_stage(project, "render", "done", f"renders/{reuse.name}")
        return {"project": pid, "cached": True,
                "manifest": manifest, "output": manifest.get("output", "")}

    encoder, enc_reason = _resolve_encoder(config, log_file)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    dst = renders_dir / (out_name or f"render_edl_{stamp}.mp4")
    work = renders_dir / f"_exec_{time.time_ns()}"
    try:
        execute_plan(plan, project.input_path, config, dst, workdir=work,
                     log_file=log_file)
    except RenderError as exc:
        mark_stage(project, "render", "failed", str(exc)[:300])
        log_event(log_file, "render", "execute", "failed",
                  time.perf_counter() - t0, str(exc)[:300], _versions(),
                  {"edl_hash": plan.edl_hash})
        raise
    try:
        out_info = probe(dst)
    except MediaProbeError as exc:
        raise RenderError(f"render produced unreadable output: {exc}", stage="validate") from exc
    qc = validate_render(dst, info, plan, config, encoder)
    proc_s = round(time.perf_counter() - t0, 3)
    manifest = {
        "kind": "edl", "status": "completed" if qc["verdict"] == "pass" else "qc_failed",
        "project": pid, "source": project.input_path,
        "edl_hash": plan.edl_hash, "config": asdict(config),
        "renderer_version": RENDERER_VERSION,
        "encoder": encoder, "encoder_reason": enc_reason,
        "output": str(dst), "output_name": dst.name,
        "source_duration": info.duration,
        "expected_duration": plan.expected_duration,
        "actual_duration": out_info.duration,
        "keep_segments": plan.keep_count, "remove_segments": plan.remove_count,
        "mapping": [asdict(s) for s in plan.keep_segments],
        "processing_s": proc_s,
        "realtime_factor": round(plan.expected_duration / proc_s, 2) if proc_s > 0 else 0.0,
        "qc": qc, "warnings": [], "cached": False,
    }
    (renders_dir / (dst.stem + _MANIFEST_SUFFIX)).write_text(
        json.dumps(manifest, indent=2), encoding="utf-8")
    mark_stage(project, "render",
               "done" if manifest["status"] == "completed" else "validation_failed",
               f"renders/{dst.stem}{_MANIFEST_SUFFIX}")
    log_event(log_file, "render", "validate", "ok" if qc["verdict"] == "pass" else "failed",
              proc_s, str(dst), _versions(),
              {"edl_hash": plan.edl_hash, "encoder": encoder,
               "expected_s": plan.expected_duration, "actual_s": out_info.duration,
               "qc": qc["verdict"]})
    if qc["verdict"] != "pass":
        raise RenderError(f"output validation failed: {qc.get('suggested_fix', '')}",
                          stage="validate")
    return {"project": pid, "cached": False, "manifest": manifest, "output": str(dst)}


def _versions() -> dict:
    import platform
    return {"python": platform.python_version(), "engine": "0.1.0"}
