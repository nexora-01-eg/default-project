"""Phase 5/6 — local Whisper STT engine (faster-whisper, local-first).

Pipeline: probe -> (Phase 3) audio/silence profile -> explicit model check
-> load (verified device) -> transcribe -> structured Transcript.

Rules enforced here:
  - FFmpeg only via engine.rendering.ffmpeg (never direct subprocess).
  - No silent downloads: model must be cached unless allow_download=True.
  - No-audio / fully-silent inputs return empty transcripts WITHOUT loading
    any model (no download attempted, fast path first).
  - Original timeline preserved: "full" spans mode transcribes whole audio;
    "non_silent" mode transcribes spans separately and shifts timestamps back.
  - _MODEL_CLS is a documented test seam (unit tests inject a fake model).
"""
from __future__ import annotations

import time
from dataclasses import asdict
from pathlib import Path

from engine.analysis.audio import AudioAnalysisError, analyze_audio
from engine.analysis.fillers import annotate_fillers
from engine.core.media import MediaProbeError, probe
from engine.core.models import Transcript, TranscriptWord, WhisperSegment
from engine.core.pipeline import cache_key, cached, store
from engine.core.project_store import (
    create_project,
    load_project,
    mark_stage,
    project_dir,
    write_artifact,
)
from engine.core.logging_utils import log_event
from engine.rendering.ffmpeg import FfmpegError, extract_audio

_MODEL_CLS = None  # test seam: tests set speech._MODEL_CLS = FakeWhisperModel


class SpeechError(RuntimeError):
    pass


SUPPORTED_MODELS = ["tiny", "base", "small", "medium", "large-v3"]

# Source: Hugging Face Hub (Systran/faster-whisper-*), pulled on demand by
# faster-whisper itself. Weights derive from OpenAI Whisper (MIT); converted
# CTranslate2 checkpoints — see each HF repo for current terms. Sizes approx.
WHISPER_MODELS: dict[str, dict] = {
    "tiny":     {"repo": "Systran/faster-whisper-tiny",     "size_mb": 75},
    "base":     {"repo": "Systran/faster-whisper-base",     "size_mb": 145},
    "small":    {"repo": "Systran/faster-whisper-small",    "size_mb": 466},
    "medium":   {"repo": "Systran/faster-whisper-medium",   "size_mb": 1500},
    "large-v3": {"repo": "Systran/faster-whisper-large-v3", "size_mb": 3080},
}

CPU_COMPUTE_TYPES = ("int8", "int8_float32", "float16", "float32")
CUDA_COMPUTE_TYPES = ("float16", "float32", "int8_float16", "int8")
_TIMESTAMP_TOL = 0.5


def _r3(x: float) -> float:
    return round(float(x), 3)


def cuda_device_count() -> int:
    try:
        import ctranslate2
        return int(ctranslate2.get_cuda_device_count())
    except Exception:
        return 0


def cuda_usable() -> bool:
    """True only if CUDA is present AND capable (never assume from count alone).

    CTranslate2 needs efficient low-precision compute (SM 6.0+); this box's
    940MX (CC 5.0) reports a device but rejects every CUDA compute type.
    Verified via nvidia-smi compute_cap; unverifiable -> False.
    """
    if cuda_device_count() == 0:
        return False
    try:
        import shutil
        import subprocess
        if shutil.which("nvidia-smi") is None:
            return False
        out = subprocess.run(["nvidia-smi", "--query-gpu=compute_cap",
                              "--format=csv,noheader"],
                             capture_output=True, text=True, timeout=30)
        if out.returncode != 0:
            return False
        for line in (out.stdout or "").splitlines():
            parts = line.strip().split(".")
            if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
                if (int(parts[0]), int(parts[1])) >= (6, 0):
                    return True
        return False
    except Exception:
        return False


def resolve_device(device: str = "auto") -> str:
    if device == "auto":
        return "cuda" if cuda_usable() else "cpu"
    if device not in ("cpu", "cuda"):
        raise SpeechError(f"unsupported device {device!r}: expected auto|cpu|cuda")
    return device


def resolve_compute(compute_type: str, device: str) -> str:
    if compute_type == "auto":
        return "float16" if device == "cuda" else "int8"
    allowed = CUDA_COMPUTE_TYPES if device == "cuda" else CPU_COMPUTE_TYPES
    if compute_type not in allowed:
        raise SpeechError(
            f"unsupported compute_type {compute_type!r} for device {device!r}: "
            f"expected one of {list(allowed)}")
    return compute_type


def validate_model_name(model: str) -> str:
    if model not in SUPPORTED_MODELS:
        raise SpeechError(
            f"unsupported model {model!r}: expected one of {SUPPORTED_MODELS}")
    return model


def ensure_model_local(model: str, allow_download: bool = False,
                       download_root: str | Path | None = None) -> str:
    """Return local model path. Never downloads unless allow_download=True."""
    validate_model_name(model)
    from faster_whisper.utils import download_model
    kwargs = {"local_files_only": True}
    if download_root is not None:
        kwargs["cache_dir"] = str(download_root)
    try:
        return download_model(model, **kwargs)
    except Exception:
        pass  # not cached -> explicit decision below
    if not allow_download:
        size = WHISPER_MODELS[model]["size_mb"]
        raise SpeechError(
            f"model {model!r} (~{size} MB) is not cached locally and downloads are "
            f"not enabled. Run `video-engine download-model {model}` or re-run with "
            f"--allow-download.")
    try:
        dl_kwargs = {}
        if download_root is not None:
            dl_kwargs["cache_dir"] = str(download_root)
        return download_model(model, **dl_kwargs)
    except Exception as exc:
        raise SpeechError(f"model download failed for {model!r}: {exc}") from exc


def download_model_explicit(model: str,
                            download_root: str | Path | None = None) -> dict:
    """Explicit one-shot download with verification (used by `download-model`)."""
    validate_model_name(model)
    from faster_whisper.utils import download_model
    kwargs = {}
    if download_root is not None:
        kwargs["cache_dir"] = str(download_root)
    try:
        path = download_model(model, **kwargs)
    except Exception as exc:
        raise SpeechError(f"model download failed for {model!r}: {exc}") from exc
    model_bin = Path(path) / "model.bin"
    if not model_bin.is_file():
        raise SpeechError(f"download incomplete for {model!r}: model.bin missing at {path}")
    return {"model": model, "repo": WHISPER_MODELS[model]["repo"],
            "size_mb": WHISPER_MODELS[model]["size_mb"], "path": path,
            "verified": True}


def _load_model(model: str, device: str, compute: str,
                download_root: str | Path | None = None):
    """Load with graceful cuda->cpu fallback (fallback is returned, never silent)."""
    from faster_whisper import WhisperModel
    cls = _MODEL_CLS or WhisperModel
    kwargs = {}
    if download_root is not None:
        kwargs["download_root"] = str(download_root)
    try:
        return cls(model, device=device, compute_type=compute, **kwargs), ""
    except Exception as exc:
        if device == "cuda":
            note = f"cuda load failed ({exc}); falling back to cpu/int8"
            try:
                return cls(model, device="cpu", compute_type="int8", **kwargs), note
            except Exception as exc2:
                raise SpeechError(f"whisper load failed on cuda and cpu fallback: {exc2}") from exc2
        raise SpeechError(f"whisper load failed (device={device}, compute={compute}): {exc}") from exc


def validate_transcript_dict(d: dict, tol: float = _TIMESTAMP_TOL) -> list[str]:
    """Check timestamp sanity. Returns issue strings (empty = clean)."""
    issues: list[str] = []
    for seg in d.get("segments", []):
        sid = seg.get("id")
        s, e = seg.get("start", 0), seg.get("end", 0)
        if s < 0:
            issues.append(f"segment {sid}: start {s} < 0")
        if not e > s:
            issues.append(f"segment {sid}: end {e} not > start {s}")
        for w in seg.get("words", []):
            ws, we = w.get("start", 0), w.get("end", 0)
            if not we > ws:
                issues.append(f"segment {sid} word {w.get('word')!r}: end {we} not > start {ws}")
            if ws < s - tol or we > e + tol:
                issues.append(f"segment {sid} word {w.get('word')!r}: "
                              f"[{ws},{we}] outside segment [{s},{e}] tol={tol}")
    dur = d.get("duration", 0)
    ends = [s.get("end", 0) for s in d.get("segments", [])]
    if ends and max(ends) > dur + 1.0:
        issues.append(f"transcript overshoots duration: max_end {max(ends)} > {dur}")
    return issues


def _empty_transcript(path: str, duration: float, reason: str, engine_info: dict,
                      config_used: dict, spans: list[dict]) -> Transcript:
    coverage = (sum(s["duration"] for s in spans) / duration) if duration > 0 else 0.0
    return Transcript(path=path, duration=_r3(duration), skipped_reason=reason,
                      engine=engine_info, non_silent_spans=spans,
                      non_silent_coverage=round(coverage, 4), config_used=config_used,
                      performance={"media_duration_s": _r3(duration),
                                   "processing_s": 0.0, "realtime_factor": 0.0})


def transcribe_file(path: str | Path, *, model: str = "small",
                    language: str | None = None, device: str = "auto",
                    compute_type: str = "auto", word_timestamps: bool = True,
                    spans: str = "full", allow_download: bool = False,
                    silence_db: float = -35.0, min_silence_s: float = 0.5,
                    download_root: str | Path | None = None,
                    audio_profile: dict | None = None,
                    timeout: int = 900,
                    log_file: Path | None = None) -> Transcript:
    """Transcribe one file. Raises SpeechError on any failure (never fakes output)."""
    src = Path(path)
    if not src.is_file():
        raise SpeechError(f"input not found: {src}")
    validate_model_name(model)
    if spans not in ("full", "non_silent"):
        raise SpeechError(f"unsupported spans mode {spans!r}: expected full|non_silent")
    dev = resolve_device(device)
    comp = resolve_compute(compute_type, dev)
    config_used = {"model": model, "language": language or "auto", "device": dev,
                   "compute_type": comp, "word_timestamps": word_timestamps,
                   "spans": spans, "silence_db": silence_db,
                   "min_silence_s": min_silence_s}
    engine_info = {"model": model, "device": dev, "compute_type": comp,
                   "model_not_loaded": False, "fallback": ""}
    try:
        info = probe(src)
    except MediaProbeError as exc:
        raise SpeechError(str(exc)) from exc
    media_dur = _r3(info.duration)
    if not info.audio_codec:
        return _empty_transcript(str(src), media_dur, "no_audio", engine_info,
                                 config_used, [])

    if audio_profile is None:
        try:
            audio_profile = asdict(analyze_audio(
                src, media=info, silence_db=silence_db, min_silence_s=min_silence_s,
                timeout=timeout))
        except AudioAnalysisError as exc:
            raise SpeechError(str(exc)) from exc
    ns_spans = audio_profile.get("non_silent", [])
    if not ns_spans:
        engine_info["model_not_loaded"] = True
        return _empty_transcript(str(src), media_dur, "fully_silent", engine_info,
                                 config_used, [])

    model_path = ensure_model_local(model, allow_download, download_root)
    t0 = time.perf_counter()
    whisper, fallback_note = _load_model(model_path if _MODEL_CLS is None else model,
                                         dev, comp, download_root)
    engine_info["fallback"] = fallback_note
    workdir = src.parent / f"_stt_{time.time_ns()}"
    workdir.mkdir(parents=True, exist_ok=True)
    try:
        jobs = [({"start": 0.0, "end": None, "offset": 0.0}, None)] if spans == "full" else [
            ({"start": s["start"], "end": s["end"], "offset": s["start"]}, s) for s in ns_spans]
        segments: list[WhisperSegment] = []
        lang, lang_prob, detected_dur = "", 0.0, 0.0
        seg_id = 0
        for job, _span in jobs:
            wav = extract_audio(src, workdir / f"prep_{seg_id}.wav", sample_rate=16000,
                                channels=1,
                                start=None if job["start"] == 0.0 and job["end"] is None else job["start"],
                                duration=None if job["end"] is None else _r3(job["end"] - job["start"]),
                                timeout=timeout, log_file=log_file)
            fw_segments, fw_info = whisper.transcribe(
                str(wav), language=language, word_timestamps=word_timestamps)
            lang, lang_prob = fw_info.language, float(fw_info.language_probability or 0.0)
            detected_dur = float(fw_info.duration or detected_dur)
            for fs in fw_segments:
                words = [TranscriptWord(word=w.word, start=_r3(w.start + job["offset"]),
                                        end=_r3(w.end + job["offset"]),
                                        probability=round(float(w.probability or 0.0), 4))
                         for w in (fs.words or [])]
                segments.append(WhisperSegment(
                    id=seg_id, text=str(fs.text or "").strip(),
                    start=_r3(fs.start + job["offset"]), end=_r3(fs.end + job["offset"]),
                    words=words))
                seg_id += 1
    except (FfmpegError, ValueError) as exc:
        raise SpeechError(f"speech pipeline failed: {exc}") from exc
    except Exception as exc:
        raise SpeechError(f"whisper inference failed: {exc}") from exc
    finally:
        for p in workdir.glob("prep_*.wav"):
            p.unlink(missing_ok=True)
        workdir.rmdir()
    proc_s = round(time.perf_counter() - t0, 3)
    language_mode = "forced" if language else "auto"
    seg_dicts = [asdict(s) for s in segments]
    fillers = annotate_fillers(seg_dicts, lang)
    coverage_src = ns_spans if spans == "non_silent" else ns_spans
    coverage = (sum(s["duration"] for s in coverage_src) / media_dur) if media_dur > 0 else 0.0
    t = Transcript(path=str(src), language=lang, language_probability=round(lang_prob, 4),
                   language_mode=language_mode, duration=media_dur, segments=segments,
                   segment_count=len(segments),
                   word_count=sum(len(s.words) for s in segments),
                   fillers=fillers, non_silent_spans=ns_spans,
                   non_silent_coverage=round(coverage, 4), engine=engine_info,
                   performance={"media_duration_s": media_dur, "processing_s": proc_s,
                                "realtime_factor": round(media_dur / proc_s, 2) if proc_s > 0 else 0.0},
                   config_used=config_used)
    payload = asdict(t)
    t.timestamp_issues = validate_transcript_dict(payload)
    return t


def _versions() -> dict:
    import platform
    return {"python": platform.python_version(), "engine": "0.1.0"}


def transcribe_to_project(input_path: str, *, project_id: str | None = None,
                          template: str = "youtube", preset: str = "youtube_1080p",
                          model: str = "small", language: str | None = None,
                          device: str = "auto", compute_type: str = "auto",
                          word_timestamps: bool = True, spans: str = "full",
                          allow_download: bool = False,
                          silence_db: float = -35.0, min_silence_s: float = 0.5,
                          download_root: str | Path | None = None,
                          timeout: int = 900) -> dict:
    """Project-scoped transcription with caching. Returns {project, cached, transcript}."""
    validate_model_name(model)
    dev = resolve_device(device)
    comp = resolve_compute(compute_type, dev)
    tcfg = {"model": model, "language": language or "auto", "device": dev,
            "compute_type": comp, "word_timestamps": word_timestamps, "spans": spans,
            "silence_db": silence_db, "min_silence_s": min_silence_s}
    project = load_project(project_id) if project_id else create_project(
        input_path, template=template, preset=preset)
    pid = project.id
    log_file = project_dir(pid) / "logs" / "run.jsonl"

    key = cache_key(project.input_path, "transcribe", tcfg)
    t0 = time.perf_counter()
    hit = cached(key)
    if hit is not None:
        import json
        payload = json.loads(hit.read_text(encoding="utf-8"))
        write_artifact(pid, "analysis", "transcript.json", payload)
        mark_stage(project, "transcribe", "cached", "analysis/transcript.json")
        log_event(log_file, "transcribe", "stt", "cached", time.perf_counter() - t0,
                  "analysis/transcript.json", _versions(),
                  {"model": model, "segments": payload.get("segment_count", 0),
                   "words": payload.get("word_count", 0)})
        return {"project": pid, "cached": True, "transcript": payload}

    # Reuse the shared analyze_audio cache entry when analyze ran before.
    audio_payload = None
    akey = cache_key(project.input_path, "analyze_audio",
                     {"silence_db": silence_db, "min_silence_s": min_silence_s})
    ahit = cached(akey)
    if ahit is not None:
        import json
        audio_payload = json.loads(ahit.read_text(encoding="utf-8"))
    try:
        result = transcribe_file(
            project.input_path, model=model, language=language, device=dev,
            compute_type=comp, word_timestamps=word_timestamps, spans=spans,
            allow_download=allow_download, silence_db=silence_db,
            min_silence_s=min_silence_s, download_root=download_root,
            audio_profile=audio_payload, timeout=timeout, log_file=log_file)
    except SpeechError as exc:
        mark_stage(project, "transcribe", "failed", str(exc)[:300])
        log_event(log_file, "transcribe", "stt", "failed", time.perf_counter() - t0,
                  str(exc)[:300], _versions(), {"model": model})
        raise
    payload = asdict(result)
    write_artifact(pid, "analysis", "transcript.json", payload)
    store(key, payload)
    mark_stage(project, "transcribe", "done", "analysis/transcript.json")
    log_event(log_file, "transcribe", "stt", "ok", time.perf_counter() - t0,
              "analysis/transcript.json", _versions(),
              {"model": model, "device": result.engine.get("device"),
               "compute_type": result.engine.get("compute_type"),
               "language": result.language,
               "segments": result.segment_count, "words": result.word_count,
               "processing_s": result.performance.get("processing_s"),
               "fallback": result.engine.get("fallback", "")})
    return {"project": pid, "cached": False, "transcript": payload}
