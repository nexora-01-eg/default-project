"""Phase 7 — scene/shot detection (PySceneDetect primary, ffmpeg fallback).

Conventions (same as speech/audio stages):
  - FFmpeg only via engine.rendering.ffmpeg (never direct subprocess).
  - Timeline source of truth is OUR probe (fps/duration), not the detector's.
  - Zero cuts is valid data: normalized to a single [0, duration] scene.
  - Timestamps kept at full float precision (never rounded).
  - Auto-fallback pyscenedetect -> ffmpeg is attempted once and RECORDED
    (fallback_from + log); never silent.
"""
from __future__ import annotations

import re
import time
from dataclasses import asdict
from pathlib import Path

from engine.core.logging_utils import log_event
from engine.core.media import MediaProbeError, probe
from engine.core.models import Scene, SceneDetectionResult
from engine.core.pipeline import cache_key, cached, store
from engine.core.project_store import (
    create_project,
    load_project,
    mark_stage,
    project_dir,
    write_artifact,
)
from engine.rendering.ffmpeg import FfmpegError, run_ffmpeg

METHODS = ("content", "threshold", "ffmpeg")
DEFAULT_THRESHOLDS = {"content": 27.0, "threshold": 12.0, "ffmpeg": 0.4}
_SHOWINFO_PTS = re.compile(r"pts_time:([0-9]+(?:\.[0-9]+)?)")


class SceneError(RuntimeError):
    pass


def detector_version() -> str:
    try:
        import scenedetect
        return str(getattr(scenedetect, "__version__", "unknown"))
    except Exception:
        return "missing"


def resolve_threshold(method: str, threshold: float | None) -> float:
    if method not in METHODS:
        raise SceneError(f"unsupported method {method!r}: expected one of {list(METHODS)}")
    if threshold is None:
        return DEFAULT_THRESHOLDS[method]
    try:
        value = float(threshold)
    except (TypeError, ValueError):
        raise SceneError(f"threshold must be a number (got {threshold!r})") from None
    if not value >= 0:
        raise SceneError(f"threshold must be >= 0 (got {value})")
    return value


def validate_scenes(scenes: list[Scene], duration: float, fps: float) -> list[str]:
    """Timeline sanity. Returns issue strings (empty = clean)."""
    issues: list[str] = []
    if not scenes:
        return ["no scenes"]
    eps = 1e-6
    frame_tol = (1.0 / fps if fps > 0 else 0.05) + 0.05
    if scenes[0].start > frame_tol:
        issues.append(f"first scene starts at {scenes[0].start}, expected near 0")
    for i, s in enumerate(scenes):
        if s.start < 0:
            issues.append(f"scene {s.scene_id}: negative start {s.start}")
        if not s.end > s.start:
            issues.append(f"scene {s.scene_id}: end {s.end} not > start {s.start}")
        if s.end > duration + 0.05:
            issues.append(f"scene {s.scene_id}: end {s.end} exceeds duration {duration}")
        if i > 0:
            prev = scenes[i - 1]
            if s.start < prev.start - eps:
                issues.append(f"scene {s.scene_id}: out of order")
            if s.start < prev.end - eps:
                issues.append(f"scene {s.scene_id}: overlaps previous")
    return issues


def _min_frames(min_scene_len_s: float, fps: float) -> int:
    if min_scene_len_s < 0:
        raise SceneError(f"min_scene_len_s must be >= 0 (got {min_scene_len_s})")
    return max(1, round(float(min_scene_len_s) * fps))


def detect_pyscenedetect(src: Path, fps: float, duration: float, method: str,
                         threshold: float, min_scene_len_s: float) -> tuple[list[Scene], str, str]:
    """Returns (scenes, detector_version, note). Raises SceneError on failure."""
    try:
        from scenedetect import SceneManager, open_video
        from scenedetect.detectors import ContentDetector, ThresholdDetector
    except Exception as exc:
        raise SceneError(f"pyscenedetect unavailable: {exc}") from exc
    frames = _min_frames(min_scene_len_s, fps)
    if method == "content":
        detector = ContentDetector(threshold=threshold, min_scene_len=frames)
    else:
        detector = ThresholdDetector(threshold=threshold, min_scene_len=frames)
    try:
        video = open_video(str(src))
    except Exception as exc:
        raise SceneError(f"pyscenedetect cannot open {src}: {exc}") from exc
    try:
        manager = SceneManager()
        manager.add_detector(detector)
        manager.detect_scenes(video, show_progress=False)
        raw = manager.get_scene_list()
    except Exception as exc:
        raise SceneError(f"pyscenedetect detection failed on {src}: {exc}") from exc
    finally:
        try:
            video.close()
        except Exception:
            pass
    note = ""
    if not raw:
        note = "no cuts detected"
        scenes = [Scene(scene_id=0, start=0.0, end=duration,
                        start_frame=0, end_frame=round(duration * fps))]
    else:
        scenes = [Scene(scene_id=i, start=float(s.seconds), end=float(e.seconds),
                        start_frame=int(s.frame_num), end_frame=int(e.frame_num))
                  for i, (s, e) in enumerate(raw)]
        scenes[-1].end = min(scenes[-1].end, duration)  # clamp trailing overrun
        scenes[-1].duration = scenes[-1].end - scenes[-1].start
    return scenes, detector_version(), note


def detect_ffmpeg(src: Path, fps: float, duration: float, threshold: float,
                  min_scene_len_s: float, timeout: int,
                  log_file: Path | None) -> tuple[list[Scene], str]:
    """Scene cuts via select/showinfo through the FFmpeg gateway."""
    try:
        result = run_ffmpeg(
            ["-i", str(src), "-an",
             "-vf", f"select='gt(scene,{threshold})',showinfo",
             "-f", "null", "-"],
            timeout=timeout, log_file=log_file, op="scene_detect_ffmpeg")
    except FfmpegError as exc:
        raise SceneError(f"ffmpeg scene detection failed: {exc}") from exc
    cuts = [0.0]
    for line in (result.stderr or "").splitlines():
        if "showinfo" not in line:
            continue
        m = _SHOWINFO_PTS.search(line)
        if m:
            cuts.append(round(float(m.group(1)), 6))
    bounds = sorted(set(cuts))
    merged = [bounds[0]]
    for b in bounds[1:]:
        if b - merged[-1] >= min_scene_len_s:
            merged.append(b)
    if merged[-1] < duration:
        merged.append(duration)
    scenes = [Scene(scene_id=i, start=merged[i], end=merged[i + 1],
                    start_frame=round(merged[i] * fps),
                    end_frame=round(merged[i + 1] * fps))
              for i in range(len(merged) - 1)]
    return scenes, "ffmpeg-fallback"


def detect_scenes(path: str | Path, *, method: str = "content",
                  threshold: float | None = None, min_scene_len_s: float = 0.6,
                  timeout: int = 900, log_file: Path | None = None) -> SceneDetectionResult:
    """Detect scenes on the source timeline. Raises SceneError (never fakes)."""
    src = Path(path)
    if not src.is_file():
        raise SceneError(f"input not found: {src}")
    if method not in METHODS:
        raise SceneError(f"unsupported method {method!r}: expected one of {list(METHODS)}")
    resolved = resolve_threshold(method, threshold)
    try:
        info = probe(src)
    except MediaProbeError as exc:
        raise SceneError(str(exc)) from exc
    if info.fps <= 0 or info.duration <= 0:
        raise SceneError(f"cannot detect scenes: unknown fps/duration for {src}")
    fps, duration = info.fps, info.duration
    frame_count = round(duration * fps)

    t0 = time.perf_counter()
    fallback_from, note, det_name, det_ver = "", "", "pyscenedetect", detector_version()
    try:
        if method == "ffmpeg":
            scenes, det_ver = detect_ffmpeg(src, fps, duration, resolved,
                                            min_scene_len_s, timeout, log_file)
            det_name = "ffmpeg"
        else:
            scenes, det_ver, note = detect_pyscenedetect(
                src, fps, duration, method, resolved, min_scene_len_s)
    except SceneError as exc:
        if method == "ffmpeg":
            raise
        fallback_from = method  # one recorded automatic attempt, never silent
        scenes, det_ver = detect_ffmpeg(src, fps, duration,
                                        DEFAULT_THRESHOLDS["ffmpeg"],
                                        min_scene_len_s, timeout, log_file)
        det_name = "ffmpeg"
        note = f"primary {method} failed ({exc}); ffmpeg fallback used"
    proc_s = round(time.perf_counter() - t0, 3)
    result = SceneDetectionResult(
        source=str(src), duration=duration, fps=fps, frame_count=frame_count,
        method=det_name if method == "ffmpeg" or fallback_from else method,
        requested_method=method, threshold=resolved, min_scene_len_s=min_scene_len_s,
        detector=det_name, detector_version=det_ver, fallback_from=fallback_from,
        note=note, scenes=scenes, scene_count=len(scenes),
        processing_s=proc_s,
        realtime_factor=round(duration / proc_s, 2) if proc_s > 0 else 0.0,
        config={"method": method, "threshold": resolved,
                "min_scene_len_s": min_scene_len_s})
    result.timeline_issues = validate_scenes(scenes, duration, fps)
    return result


def _versions() -> dict:
    import platform
    return {"python": platform.python_version(), "engine": "0.1.0"}


def detect_scenes_project(input_path: str, *, project_id: str | None = None,
                          template: str = "youtube", preset: str = "youtube_1080p",
                          method: str = "content", threshold: float | None = None,
                          min_scene_len_s: float = 0.6,
                          timeout: int = 900) -> dict:
    """Project-scoped detection with caching. Returns {project, cached, result}."""
    if method not in METHODS:
        raise SceneError(f"unsupported method {method!r}: expected one of {list(METHODS)}")
    resolved = resolve_threshold(method, threshold)
    if method == "ffmpeg":
        from engine.rendering.ffmpeg import ffmpeg_version
        det_ver_key = ffmpeg_version()
    else:
        det_ver_key = detector_version()
    scfg = {"method": method, "detector": "pyscenedetect" if method != "ffmpeg" else "ffmpeg",
            "detector_version": det_ver_key, "threshold": resolved,
            "min_scene_len_s": min_scene_len_s}
    project = load_project(project_id) if project_id else create_project(
        input_path, template=template, preset=preset)
    pid = project.id
    log_file = project_dir(pid) / "logs" / "run.jsonl"

    key = cache_key(project.input_path, "scenes", scfg)
    t0 = time.perf_counter()
    hit = cached(key)
    if hit is not None:
        import json
        payload = json.loads(hit.read_text(encoding="utf-8"))
        payload["cached"] = True
        write_artifact(pid, "analysis", "scenes.json", payload)
        mark_stage(project, "scenes", "cached", "analysis/scenes.json")
        log_event(log_file, "scenes", "detect", "cached", time.perf_counter() - t0,
                  "analysis/scenes.json", _versions(),
                  {"method": method, "scenes": payload.get("scene_count", 0)})
        return {"project": pid, "cached": True, "result": payload}

    try:
        result = detect_scenes(project.input_path, method=method, threshold=resolved,
                               min_scene_len_s=min_scene_len_s, timeout=timeout,
                               log_file=log_file)
    except SceneError as exc:
        mark_stage(project, "scenes", "failed", str(exc)[:300])
        log_event(log_file, "scenes", "detect", "failed", time.perf_counter() - t0,
                  str(exc)[:300], _versions(), {"method": method})
        raise
    payload = asdict(result)
    write_artifact(pid, "analysis", "scenes.json", payload)
    store(key, payload)
    mark_stage(project, "scenes", "done", "analysis/scenes.json")
    log_event(log_file, "scenes", "detect", "ok", time.perf_counter() - t0,
              "analysis/scenes.json", _versions(),
              {"method": result.method, "threshold": resolved,
               "detector_version": result.detector_version,
               "scenes": result.scene_count,
               "processing_s": result.processing_s,
               "fallback_from": result.fallback_from})
    return {"project": pid, "cached": False, "result": payload}
