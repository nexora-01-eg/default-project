"""ffprobe wrapper (inspect stage). Graceful when FFmpeg is not installed yet."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

from .models import MediaInfo


class MediaProbeError(RuntimeError):
    pass


def ffprobe_path() -> str | None:
    raw = (os.environ.get("FFPROBE_PATH", "") or "").strip()
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in ("\"", "'"):
        raw = raw[1:-1]
    if raw:
        return raw if os.path.isfile(raw) else None
    return shutil.which("ffprobe")


def probe(path: str | Path) -> MediaInfo:
    src = Path(path)
    if not src.is_file():
        raise MediaProbeError(f"input not found: {src}")
    exe = ffprobe_path()
    if exe is None:
        raw = (os.environ.get("FFPROBE_PATH", "") or "").strip()
        if raw:
            raise MediaProbeError(
                f"FFPROBE_PATH points nowhere: {raw!r}. Fix the path or "
                f"unset FFPROBE_PATH to use PATH lookup."
            )
        raise MediaProbeError(
            "ffprobe not found on PATH and FFPROBE_PATH is unset. Install "
            "FFmpeg first: run `.\\setup.ps1 -Install`, or set "
            "FFPROBE_PATH to an explicit ffprobe.exe."
        )
    cmd = [exe, "-v", "quiet", "-print_format", "json",
           "-show_format", "-show_streams", str(src)]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=120)
    except subprocess.TimeoutExpired as exc:
        raise MediaProbeError(f"ffprobe timed out on {src}") from exc
    if out.returncode != 0:
        raise MediaProbeError(f"ffprobe failed: {out.stderr.strip()[:500]}")
    data = json.loads(out.stdout or "{}")
    return _parse(str(src), data)


def _fnum(value, default: float = 0.0) -> float:
    try:
        return float(str(value).split(" ")[0] or 0)
    except ValueError:
        return default


def _parse(path: str, data: dict) -> MediaInfo:
    info = MediaInfo(path=path)
    fmt = data.get("format", {})
    try:
        info.duration = float(fmt.get("duration", 0) or 0)
    except ValueError:
        info.duration = 0.0
    try:
        info.bitrate = int(fmt.get("bit_rate", 0) or 0)
    except ValueError:
        pass
    for stream in data.get("streams", []):
        ctype = stream.get("codec_type")
        if ctype == "video" and not info.video_codec:
            info.video_codec = stream.get("codec_name", "")
            info.width = int(stream.get("width", 0) or 0)
            info.height = int(stream.get("height", 0) or 0)
            info.video_start_time = _fnum(stream.get("start_time", 0))
            info.video_duration = _fnum(stream.get("duration", 0))
            fps_raw = stream.get("avg_frame_rate", "0/1")
            info.fps_rational = str(fps_raw)
            try:
                num, _, den = fps_raw.partition("/")
                info.fps = float(num) / float(den) if float(den) else 0.0
            except (ValueError, ZeroDivisionError):
                info.fps = 0.0
            try:
                nnum, _, nden = str(stream.get("r_frame_rate", "0/1")).partition("/")
                info.fps_nominal = float(nnum) / float(nden) if float(nden) else 0.0
            except (ValueError, ZeroDivisionError):
                info.fps_nominal = 0.0
            info.video_time_base = str(stream.get("time_base", ""))
        elif ctype == "audio":
            bitrate = 0
            try:
                bitrate = int(stream.get("bit_rate", 0) or 0)
            except ValueError:
                pass
            sample_rate = 0
            try:
                sample_rate = int(stream.get("sample_rate", 0) or 0)
            except ValueError:
                pass
            stream_dur = 0.0
            for key in ("duration", "tags:DURATION"):
                raw = stream.get(key, "")
                try:
                    stream_dur = float(str(raw).split(" ")[0] or 0)
                    if stream_dur:
                        break
                except ValueError:
                    continue
            info.audio_streams.append({
                "index": stream.get("index"),
                "codec": stream.get("codec_name", ""),
                "channels": int(stream.get("channels", 0) or 0),
                "sample_rate": sample_rate,
                "bitrate": bitrate,
                "duration": stream_dur,
                "start_time": _fnum(stream.get("start_time", 0)),
            })
            if not info.audio_codec:  # convenience fields = first audio stream
                info.audio_codec = stream.get("codec_name", "")
                info.audio_channels = int(stream.get("channels", 0) or 0)
                info.sample_rate = sample_rate
    return info
