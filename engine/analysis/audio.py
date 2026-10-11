"""Phase 3 — audio/media analysis: stats, loudness, silence.

Non-destructive: only reads the source. Three ffmpeg measurement passes
(volumedetect, loudnorm-JSON, silencedetect) plus stream facts from
core.media.probe (never re-implements ffprobe parsing).

Public entry: analyze_audio(path, media=None, silence_db=..., min_silence_s=...).
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

from engine.core.media import MediaProbeError, probe
from engine.core.models import AudioAnalysis, MediaInfo, SilenceInterval

_SIL_START = re.compile(r"silence_start:\s*(-?\d+(?:\.\d+)?)")
_SIL_END = re.compile(r"silence_end:\s*(-?\d+(?:\.\d+)?)\s*\|\s*silence_duration:\s*(\d+(?:\.\d+)?)")
_VOL = re.compile(r"(mean_volume|max_volume):\s*(-?\d+(?:\.\d+)?|n/a)\s*dB")


class AudioAnalysisError(RuntimeError):
    pass


def ffmpeg_path() -> str | None:
    return shutil.which("ffmpeg")


def _run_af(ffmpeg: str, src: Path, audio_filter: str, timeout: int) -> str:
    """Run a measurement filter, return combined stderr (where ffmpeg logs)."""
    cmd = [ffmpeg, "-hide_banner", "-nostats", "-i", str(src),
           "-af", audio_filter, "-vn", "-f", "null", "-"]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise AudioAnalysisError(f"audio analysis timed out on {src} [{audio_filter}]") from exc
    if out.returncode != 0:
        raise AudioAnalysisError(
            f"ffmpeg {audio_filter} failed on {src}: {(out.stderr or '').strip()[-800:]}"
        )
    return out.stderr or ""


def parse_volumedetect(stderr: str) -> dict:
    """Return {'mean_volume_db': float|None, 'max_volume_db': float|None}."""
    found = dict(_VOL.findall(stderr))
    def _num(key: str):
        raw = found.get(key, "n/a")
        try:
            return float(raw)
        except ValueError:
            return None
    return {"mean_volume_db": _num("mean_volume"), "max_volume_db": _num("max_volume")}


def parse_loudnorm_json(stderr: str) -> dict:
    """Extract the loudnorm print_format=json block; {} when absent/unparseable."""
    start = stderr.find("{")
    end = stderr.rfind("}")
    if start < 0 or end <= start:
        return {}
    try:
        data = json.loads(stderr[start:end + 1])
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) and "input_i" in data else {}


def parse_silencedetect(stderr: str, audio_duration: float) -> list[SilenceInterval]:
    """Pair silence_start/silence_end lines; a dangling start closes at EOF duration."""
    spans: list[SilenceInterval] = []
    open_start: float | None = None
    for line in stderr.splitlines():
        if "silence_start" not in line and "silence_end" not in line:
            continue
        m_end = _SIL_END.search(line)
        if m_end and open_start is not None:
            end = round(float(m_end.group(1)), 3)
            spans.append(SilenceInterval(start=open_start, end=end,
                                         duration=round(end - open_start, 3)))
            open_start = None
            continue
        m_start = _SIL_START.search(line)
        if m_start and open_start is None:
            open_start = round(max(0.0, float(m_start.group(1))), 3)
    if open_start is not None:  # trailing silence: silencedetect emits no end at EOF
        end = round(max(open_start, audio_duration), 3)
        spans.append(SilenceInterval(start=open_start, end=end,
                                     duration=round(end - open_start, 3)))
    return spans


def complement(spans: list[SilenceInterval], total: float) -> list[SilenceInterval]:
    """Invert silence spans over [0, total] into non-silent segments."""
    out: list[SilenceInterval] = []
    cursor = 0.0
    for span in sorted(spans, key=lambda s: s.start):
        if span.start > cursor:
            out.append(SilenceInterval(start=round(cursor, 3), end=span.start,
                                       duration=round(span.start - cursor, 3)))
        cursor = max(cursor, span.end)
    if cursor < total:
        out.append(SilenceInterval(start=round(cursor, 3), end=round(total, 3),
                                   duration=round(total - cursor, 3)))
    return [s for s in out if s.duration > 0]


def analyze_audio(path: str | Path, media: MediaInfo | None = None,
                  silence_db: float = -35.0, min_silence_s: float = 0.5,
                  timeout: int = 300) -> AudioAnalysis:
    src = Path(path)
    if not src.is_file():
        raise AudioAnalysisError(f"input not found: {src}")
    ffmpeg = ffmpeg_path()
    if ffmpeg is None:
        raise AudioAnalysisError(
            "ffmpeg not found on PATH. Install FFmpeg first: run `.\\setup.ps1 -Install`."
        )
    try:
        info = media or probe(src)
    except MediaProbeError as exc:
        raise AudioAnalysisError(str(exc)) from exc

    result = AudioAnalysis(
        path=str(src),
        num_audio_streams=len(info.audio_streams),
        config_used={"silence_db": silence_db, "min_silence_s": min_silence_s},
    )
    if not info.audio_streams:
        return result  # valid no-audio outcome, never an error

    primary = info.audio_streams[0]
    result.audio_present = True
    stream_dur = float(primary.get("duration") or 0)
    result.audio_duration = round(stream_dur or info.duration, 3)
    result.channels = int(primary.get("channels") or 0)
    result.sample_rate = int(primary.get("sample_rate") or 0)
    result.codec = str(primary.get("codec") or "")
    result.bitrate = int(primary.get("bitrate") or 0)

    vols = parse_volumedetect(_run_af(ffmpeg, src, "volumedetect", timeout))
    result.mean_volume_db = vols["mean_volume_db"]
    result.max_volume_db = vols["max_volume_db"]

    result.loudness = parse_loudnorm_json(
        _run_af(ffmpeg, src, "loudnorm=print_format=json", timeout))

    af = f"silencedetect=noise={silence_db}dB:d={min_silence_s}"
    result.silence = parse_silencedetect(_run_af(ffmpeg, src, af, timeout),
                                         result.audio_duration)
    result.non_silent = complement(result.silence, result.audio_duration)
    result.silence_total_s = round(sum(s.duration for s in result.silence), 3)
    return result
