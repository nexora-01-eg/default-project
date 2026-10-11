"""Central orchestrator: INPUT → … → FINAL (Phase 3: inspect + analyze_audio).

Later phases register `plan`, `execute`, `render`, `qc` stages
without changing this runner.
"""
from __future__ import annotations

import sys
import time
from dataclasses import asdict
from pathlib import Path

from engine.analysis.audio import AudioAnalysisError, analyze_audio
from . import config as config_mod
from .logging_utils import log_event
from .media import MediaProbeError, probe
from .models import MediaInfo
from .pipeline import cache_key, cached, registered, store
from .project_store import create_project, mark_stage, project_dir, write_artifact

ENGINE_VERSION = "0.1.0"


def _versions() -> dict:
    import platform
    return {"python": platform.python_version(), "engine": ENGINE_VERSION}


def _media_from_dict(payload: dict) -> MediaInfo:
    fields = MediaInfo.__dataclass_fields__
    return MediaInfo(**{k: payload[k] for k in fields if k in payload})


def _run_audio_stage(project, log_file, input_path: str, media_payload: dict,
                     cfg: dict) -> tuple[dict, bool]:
    """Run (or load from cache) the analyze_audio stage. Returns (payload, was_cached)."""
    audio_cfg = {"silence_db": cfg["silence_db"], "min_silence_s": cfg["min_silence_s"]}
    key = cache_key(input_path, "analyze_audio", audio_cfg)
    t0 = time.perf_counter()
    hit = cached(key)
    if hit is not None:
        import json
        payload = json.loads(hit.read_text(encoding="utf-8"))
        write_artifact(project.id, "analysis", "audio_analysis.json", payload)
        mark_stage(project, "analyze_audio", "cached", "analysis/audio_analysis.json")
        log_event(log_file, "analyze_audio", "audio_stats", "cached",
                  time.perf_counter() - t0, "analysis/audio_analysis.json", _versions())
        return payload, True
    try:
        result = analyze_audio(input_path, media=_media_from_dict(media_payload),
                               silence_db=float(audio_cfg["silence_db"]),
                               min_silence_s=float(audio_cfg["min_silence_s"]))
    except AudioAnalysisError as exc:
        mark_stage(project, "analyze_audio", "failed", str(exc))
        log_event(log_file, "analyze_audio", "audio_stats", "failed",
                  time.perf_counter() - t0, str(exc), _versions())
        raise
    payload = asdict(result)
    write_artifact(project.id, "analysis", "audio_analysis.json", payload)
    store(key, payload)
    mark_stage(project, "analyze_audio", "done", "analysis/audio_analysis.json")
    log_event(log_file, "analyze_audio", "audio_stats", "ok",
              time.perf_counter() - t0, "analysis/audio_analysis.json", _versions())
    return payload, False


def run_inspect(input_path: str, template: str = "youtube", preset: str = "youtube_1080p",
                overrides: dict | None = None) -> dict:
    cfg = config_mod.resolve(template, preset, overrides)
    project = create_project(input_path, template=cfg["template"], preset=cfg["preset"])
    pid = project.id
    log_file = project_dir(pid) / "logs" / "run.jsonl"
    t0 = time.perf_counter()

    # Cache lookup first (expensive analysis must never repeat).
    key = cache_key(input_path, "inspect", cfg)
    hit = cached(key)
    inspect_cached = hit is not None
    if hit is not None:
        import json
        payload = json.loads(hit.read_text(encoding="utf-8"))
        write_artifact(pid, "analysis", "media_info.json", payload)
        mark_stage(project, "inspect", "cached", "analysis/media_info.json")
        log_event(log_file, "inspect", "probe", "cached",
                  time.perf_counter() - t0, "analysis/media_info.json", _versions())
    else:
        try:
            info = probe(input_path)
        except MediaProbeError as exc:
            mark_stage(project, "inspect", "failed", str(exc))
            log_event(log_file, "inspect", "probe", "failed",
                      time.perf_counter() - t0, str(exc), _versions())
            raise

        payload = asdict(info)
        write_artifact(pid, "analysis", "media_info.json", payload)
        store(key, payload)
        mark_stage(project, "inspect", "done", "analysis/media_info.json")
        log_event(log_file, "inspect", "probe", "ok",
                  time.perf_counter() - t0, "analysis/media_info.json", _versions())

    audio_payload, audio_cached = _run_audio_stage(project, log_file, input_path, payload, cfg)
    return {"project": pid, "cached": inspect_cached and audio_cached,
            "media": payload, "audio": audio_payload}


def run_edit(*args, **kwargs) -> dict:
    raise NotImplementedError(
        "Legacy entry point (kept for compatibility). Phase 8 decisions live in "
        "engine.editing.decisions.build_edl_for_project; use `video-engine edit <project>`."
    )
