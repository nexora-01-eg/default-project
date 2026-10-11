"""Phase 4 — FFmpeg service/adapter layer (the ONLY place that builds ffmpeg commands).

Everything else (orchestrator, CLI, future phases) calls these functions;
nothing outside this module constructs ffmpeg argv. All invocations are
arg-lists (no shell), non-destructive (sources never modified), logged with
command/version/encoder/timing/exit/stderr.

Contents:
  - run_ffmpeg / FfmpegError          central runner + rich errors
  - detect_encoders / select_encoder  listed-plus-smoke-verified HW detection
  - trim / concat / render_keep       non-destructive cut/concat (EDL-driven)
  - extract_audio / extract_frame     single-purpose extractors
  - apply_vf / mix_audio              basic video / audio filtering
  - burn_subtitles                    ASS/SRT burned-in captions (Phase 14)
  - validate_output                   QCReport-based output validation
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

from engine.core.logging_utils import log_event
from engine.core.media import MediaProbeError, probe
from engine.core.models import QCCheck, QCReport

HW_CANDIDATES = ("h264_nvenc", "h264_qsv", "h264_amf")
SOFTWARE_CANDIDATES = ("libx264",)
AUDIO_ENCODER = "aac"
ENCODER_CODEC = {"h264_nvenc": "h264", "h264_qsv": "h264", "h264_amf": "h264",
                 "libx264": "h264", "libx265": "hevc"}


@dataclass
class RunResult:
    cmd: list[str]
    returncode: int
    stdout: str
    stderr: str
    duration_s: float


class FfmpegError(RuntimeError):
    def __init__(self, message: str, *, cmd: list[str], version: str,
                 exit_code: int, stderr_tail: str, duration_s: float):
        super().__init__(message)
        self.cmd = cmd
        self.version = version
        self.exit_code = exit_code
        self.stderr_tail = stderr_tail
        self.duration_s = duration_s


def _explicit_exe(var: str) -> str | None:
    """Explicit binary override (handles quoted paths with spaces)."""
    raw = (os.environ.get(var, "") or "").strip()
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in ("\"", "'"):
        raw = raw[1:-1]
    return raw or None


def which_ffmpeg() -> str | None:
    exp = _explicit_exe("FFMPEG_PATH")
    if exp:
        return exp if os.path.isfile(exp) else None
    return shutil.which("ffmpeg")


def ffmpeg_config_state() -> dict:
    """Observable resolution state (for doctor/diagnostics)."""
    exp = _explicit_exe("FFMPEG_PATH")
    if exp:
        ok = os.path.isfile(exp)
        return {"source": "FFMPEG_PATH", "explicit": exp,
                "explicit_valid": ok, "path": exp if ok else None}
    found = shutil.which("ffmpeg")
    return {"source": "PATH", "explicit": None,
            "explicit_valid": None, "path": found}


def ffmpeg_version() -> str:
    exe = which_ffmpeg()
    if exe is None:
        return "NOT FOUND"
    try:
        out = subprocess.run([exe, "-hide_banner", "-version"],
                             capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=30)
        first = (out.stdout or "").splitlines()
        return first[0].strip() if first else "unknown"
    except (OSError, subprocess.TimeoutExpired):
        return "unrunnable"


def _need_exe() -> str:
    exp = _explicit_exe("FFMPEG_PATH")
    if exp and not os.path.isfile(exp):
        raise FfmpegError(
            f"FFMPEG_PATH points nowhere: {exp!r}. Fix the path or unset "
            f"FFMPEG_PATH to use PATH lookup.",
            cmd=["ffmpeg"], version="MISCONFIGURED", exit_code=-1,
            stderr_tail="", duration_s=0.0)
    exe = which_ffmpeg()
    if exe is None:
        raise FfmpegError(
            "ffmpeg not found on PATH and FFMPEG_PATH is unset. Install "
            "FFmpeg first: run `.\\setup.ps1 -Install`, or set FFMPEG_PATH "
            "to an explicit ffmpeg.exe.",
            cmd=["ffmpeg"], version="NOT FOUND", exit_code=-1,
            stderr_tail="", duration_s=0.0)
    return exe


def _tail(text: str, lines: int = 30) -> str:
    return "\n".join((text or "").splitlines()[-lines:])


def run_ffmpeg(ffmpeg_args: list[str], timeout: int = 600,
               log_file: Path | None = None, stage: str = "render",
               op: str = "ffmpeg") -> RunResult:
    """Run ffmpeg with an arg-list. Raises FfmpegError (never returns failure)."""
    exe = _need_exe()
    cmd = [exe, "-hide_banner", *ffmpeg_args]
    version = ffmpeg_version()
    t0 = time.perf_counter()
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        dur = time.perf_counter() - t0
        if log_file:
            log_event(log_file, stage, op, "failed", dur, "",
                      {"ffmpeg": version},
                      {"cmd": cmd, "exit_code": -2, "stderr_tail": "TIMEOUT"})
        raise FfmpegError(f"ffmpeg timed out after {timeout}s: {' '.join(cmd[:6])}…",
                          cmd=cmd, version=version, exit_code=-2,
                          stderr_tail="TIMEOUT", duration_s=dur) from exc
    dur = round(time.perf_counter() - t0, 3)
    if proc.returncode != 0:
        tail = _tail(proc.stderr)
        if log_file:
            log_event(log_file, stage, op, "failed", dur, "",
                      {"ffmpeg": version},
                      {"cmd": cmd, "exit_code": proc.returncode, "stderr_tail": tail})
        raise FfmpegError(
            f"ffmpeg exit={proc.returncode}: {' '.join(cmd[:8])}…\n{tail}",
            cmd=cmd, version=version, exit_code=proc.returncode,
            stderr_tail=tail, duration_s=dur)
    if log_file:
        log_event(log_file, stage, op, "ok", dur, "",
                  {"ffmpeg": version},
                  {"cmd": cmd, "exit_code": 0,
                   "stderr_tail": _tail(proc.stderr, 5)})
    return RunResult(cmd=cmd, returncode=0, stdout=proc.stdout or "",
                     stderr=proc.stderr or "", duration_s=dur)


# ---------------- encoder detection ----------------

def _encoders_cache_path() -> Path:
    from engine.core.pipeline import CACHE_DIR
    return CACHE_DIR / "encoders.json"


def _parse_encoder_list() -> set[str]:
    exe = _need_exe()
    out = subprocess.run([exe, "-hide_banner", "-encoders"],
                         capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=60)
    if out.returncode != 0:
        raise FfmpegError("ffmpeg -encoders failed", cmd=[exe, "-encoders"],
                          version=ffmpeg_version(), exit_code=out.returncode,
                          stderr_tail=_tail(out.stderr), duration_s=0.0)
    names: set[str] = set()
    for line in (out.stdout or "").splitlines():
        m = re.match(r"\s*[A-Z.]{6}\s+([A-Za-z0-9_]+)\s", line)
        if m:
            names.add(m.group(1))
    return names


def _smoke_encode(candidate: str, tmpdir: Path) -> tuple[bool, str]:
    """Actually encode 1 s of synthetic media: listed != working (no-GPU sessions, etc.)."""
    out = tmpdir / f"smoke_{candidate}.mp4"
    try:
        run_ffmpeg(["-loglevel", "error",
                    "-f", "lavfi", "-i", "testsrc=size=128x128:rate=15:duration=1",
                    "-f", "lavfi", "-i", "anullsrc=cl=mono:r=44100:d=1",
                    "-pix_fmt", "yuv420p",
                    "-c:v", candidate, "-c:a", AUDIO_ENCODER, "-y", str(out)],
                   timeout=120)
    except FfmpegError as exc:
        return False, exc.stderr_tail.splitlines()[-1][:200] if exc.stderr_tail else f"exit={exc.exit_code}"
    ok = out.is_file() and out.stat().st_size > 0
    return ok, "" if ok else "no output file produced"


def detect_encoders(force_refresh: bool = False) -> dict:
    """Return {ffmpeg_version, encoders: {name: {listed, verified, error}}}.

    Cached in .cache/encoders.json; invalidated when the ffmpeg version changes.
    HW candidates are smoke-verified, never trusted from the list alone.
    """
    cache = _encoders_cache_path()
    version = ffmpeg_version()
    if not force_refresh and cache.is_file():
        try:
            data = json.loads(cache.read_text(encoding="utf-8"))
            if data.get("ffmpeg_version") == version and "encoders" in data:
                return data
        except (json.JSONDecodeError, OSError):
            pass
    listed = _parse_encoder_list()
    result: dict = {"ffmpeg_version": version, "encoders": {}}
    with tempfile.TemporaryDirectory(prefix="enc_smoke_") as tmp:
        tmpdir = Path(tmp)
        for name in (*HW_CANDIDATES, *SOFTWARE_CANDIDATES, AUDIO_ENCODER, "pcm_s16le"):
            entry = {"listed": name in listed, "verified": False, "error": ""}
            if entry["listed"] and name in (*HW_CANDIDATES, *SOFTWARE_CANDIDATES):
                ok, err = _smoke_encode(name, tmpdir)
                entry["verified"] = ok
                entry["error"] = err
            elif entry["listed"]:
                entry["verified"] = True  # audio/pcm: listing suffices, exercised by tests
            else:
                entry["error"] = "not listed by ffmpeg -encoders"
            result["encoders"][name] = entry
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def select_encoder(priority: list[str] | None = None) -> dict:
    """Pick the first verified encoder.

    Returns {selected_encoder, hardware_acceleration, reason, verified}.
    Never assumes HW exists: a listed-but-broken encoder is skipped with reason.
    """
    if priority is None:
        from engine.core import config as config_mod
        priority = list(config_mod.DEFAULTS.get(
            "encoder_priority", ["h264_nvenc", "h264_qsv", "h264_amf", "libx264"]))
    detected = detect_encoders()
    verified = {n: e["verified"] for n, e in detected["encoders"].items()}
    tried: list[str] = []
    for name in priority:
        if verified.get(name):
            hw = name in HW_CANDIDATES
            reason = (f"{name} smoke-verified on this machine"
                      + (f" (skipped unverified: {', '.join(tried)})" if tried else ""))
            return {"selected_encoder": name, "hardware_acceleration": hw,
                    "reason": reason, "verified": verified}
        tried.append(f"{name}({'listed' if detected['encoders'].get(name, {}).get('listed') else 'absent'})")
    raise FfmpegError(
        f"no verified encoder among priority={priority} (tried: {', '.join(tried)})",
        cmd=["ffmpeg"], version=detected["ffmpeg_version"], exit_code=-3,
        stderr_tail="", duration_s=0.0)


# ---------------- validation helpers ----------------

def validate_timestamps(start: float, end: float, duration: float) -> tuple[float, float]:
    """Validate a cut range BEFORE spawning ffmpeg (programmer errors raise)."""
    if start < 0 or end < 0:
        raise ValueError(f"timestamps must be >= 0 (got start={start}, end={end})")
    if not end > start:
        raise ValueError(f"end must exceed start (got start={start}, end={end})")
    if start >= duration:
        raise ValueError(f"start={start} beyond media duration={duration:.3f}")
    return round(start, 3), round(min(end, duration), 3)


def _resolve_encoder(encoder: str) -> tuple[str, str]:
    """Return (video_codec_arg, selection_reason). 'auto' probes the machine."""
    if encoder == "auto":
        sel = select_encoder()
        return sel["selected_encoder"], sel["reason"]
    return encoder, f"explicitly requested ({encoder})"


def _mp4_flags(dst: Path) -> list[str]:
    return ["-movflags", "+faststart"] if dst.suffix.lower() == ".mp4" else []


def vfr_status(info) -> dict:
    """Measured VFR diagnosis (no guessing, no thresholds on content).

    Returns {is_vfr, nominal, measured, fps_filter, reason}. A source is
    VFR when the container-default nominal rate is absurd (>1000 fps, e.g.
    phone 90000/1) or disagrees with the measured average by >5%.
    fps_filter is the measured avg_frame_rate rational for CFR normalization.
    """
    nominal = float(getattr(info, "fps_nominal", 0.0) or 0.0)
    measured = float(getattr(info, "fps", 0.0) or 0.0)
    rational = str(getattr(info, "fps_rational", "") or "")
    if measured <= 0:
        return {"is_vfr": False, "nominal": nominal, "measured": measured,
                "fps_filter": "", "reason": "unmeasured rate: legacy path"}
    if nominal > 1000:
        return {"is_vfr": True, "nominal": nominal, "measured": measured,
                "fps_filter": rational or repr(measured),
                "reason": f"bogus nominal {nominal:g}fps vs measured {measured:.3f}fps"}
    if abs(nominal - measured) / measured > 0.05:
        return {"is_vfr": True, "nominal": nominal, "measured": measured,
                "fps_filter": rational or repr(measured),
                "reason": f"nominal {nominal:g}fps disagrees with measured {measured:.3f}fps"}
    return {"is_vfr": False, "nominal": nominal, "measured": measured,
            "fps_filter": "", "reason": "CFR: nominal matches measured"}


def normalize_media(src: str | Path, dst: str | Path, *,
                    encoder: str = "auto", preset: str = "veryfast",
                    timeout: int = 600,
                    log_file: Path | None = None) -> Path:
    """Deterministic CFR proxy for VFR sources (project-local temp only).

    -vf fps=<measured rational> forces uniform frame timestamps;
    -af aresample=<src rate>:async=1 corrects timestamp drift by measured
    resampling (sub-1% tempo, inaudible, deterministic). Sources untouched;
    CFR inputs must never reach this function (callers gate on vfr_status).
    """
    from engine.core.media import probe as _probe
    src_p, dst_p = Path(src), Path(dst)
    info = _probe(src_p)
    st = vfr_status(info)
    if not st["is_vfr"]:
        raise ValueError("normalize_media refused: source is not VFR "
                         f"({st['reason']})")
    venc, _ = _resolve_encoder(encoder)
    rate = info.sample_rate or 48000
    video_dur = float(getattr(info, "video_duration", 0.0) or 0.0) or float(info.duration or 0.0)
    args = ["-loglevel", "error", "-i", str(src_p),
            "-vf", f"fps={st['fps_filter']}",
            "-c:v", venc, *_preset_args(venc, preset), "-pix_fmt", "yuv420p",
            "-af", f"aresample={rate}:async=1,apad=whole_dur={video_dur:.3f}",
            "-c:a", AUDIO_ENCODER,
            *_mp4_flags(dst_p), "-y", str(dst_p)]
    run_ffmpeg(args, timeout=timeout, log_file=log_file, op="normalize_vfr")
    return dst_p


def _preset_args(encoder: str, preset: str) -> list[str]:
    """-preset is an x264-family concept: ultrafast/superfast/placebo are
    rejected by hardware encoders (verified: h264_qsv refuses ultrafast).
    Only software encoders receive it; HW uses its own defaults."""
    if encoder in ("libx264", "libx265", "libvpx", "libvpx-vp9", "libaom-av1"):
        return ["-preset", preset]
    return []


# ---------------- operations ----------------

def trim(src: str | Path, start: float, end: float, dst: str | Path, *,
         encoder: str = "auto", accurate: bool = True,
         preset: str = "veryfast", timeout: int = 600,
         log_file: Path | None = None) -> Path:
    """Cut [start, end) non-destructively.

    accurate=True: output seeking + re-encode (frame-accurate, slower).
    accurate=False: input seeking + stream copy (fast, keyframe-approximate).
    """
    src_p, dst_p = Path(src), Path(dst)
    info = probe(src_p)  # raises MediaProbeError on missing/invalid input
    if info.duration <= 0:
        raise ValueError(f"cannot trim: unknown duration for {src_p}")
    start, end = validate_timestamps(float(start), float(end), info.duration)
    dst_p.parent.mkdir(parents=True, exist_ok=True)
    proxy = None
    fps_rate = float(getattr(info, "fps", 0.0) or 0.0)
    if accurate and vfr_status(info)["is_vfr"]:
        # VFR sources accumulate per-trim timestamp overshoot over multi-part
        # timelines. Normalize once to a deterministic CFR proxy (temp, cleaned
        # with the workdir on success) and run the identical trim logic on it.
        # CFR sources take the byte-identical legacy path below.
        proxy = dst_p.parent / f"_vfr_{time.time_ns()}.mp4"
        try:
            normalize_media(src_p, proxy, encoder=encoder, preset=preset,
                            timeout=timeout, log_file=log_file)
        except Exception:
            proxy.unlink(missing_ok=True)
            raise
        src_p = proxy
        # The proxy's true rate (not the source average) drives frame-exact
        # counting; probe averages round and would systematically undercount.
        try:
            fps_rate = float(probe(proxy).fps or 0.0)
        except Exception:
            pass
    try:
        return _trim_src(src_p, dst_p, start, end, info, fps_rate,
                         encoder=encoder, accurate=accurate, preset=preset,
                         timeout=timeout, log_file=log_file)
    finally:
        if proxy is not None and dst_p.is_file():
            proxy.unlink(missing_ok=True)


def _trim_src(src_p: Path, dst_p: Path, start: float, end: float, info,
              fps_rate: float, *, encoder: str, accurate: bool,
              preset: str, timeout: int, log_file: Path | None) -> Path:
    has_audio = bool(info.audio_codec)
    if accurate:
        venc, reason = _resolve_encoder(encoder)
        # Frame-exact video length: -t alone rounds each part UP to a frame
        # end (systematic +bias that accumulates over multi-part timelines).
        # Counting frames from the measured rate centers the error (±half
        # quantum, zero-mean) while -t still caps the audio stream.
        span = end - start
        nframes = max(1, round(span * fps_rate)) if fps_rate > 0 else 0
        args = ["-loglevel", "error", "-i", str(src_p),
                "-ss", repr(start), "-t", repr(span),
                "-c:v", venc, *_preset_args(venc, preset), "-pix_fmt", "yuv420p"]
        if nframes:
            args += ["-frames:v", str(nframes)]
        args += ["-c:a", AUDIO_ENCODER] if has_audio else ["-an"]
        args += [*_mp4_flags(dst_p), "-y", str(dst_p)]
        run_ffmpeg(args, timeout=timeout, log_file=log_file, op=f"trim_accurate[{venc}]")
    else:
        args = ["-loglevel", "error", "-ss", repr(start), "-i", str(src_p),
                "-t", repr(end - start), "-c", "copy",
                *_mp4_flags(dst_p), "-y", str(dst_p)]
        run_ffmpeg(args, timeout=timeout, log_file=log_file, op="trim_fast_copy")
    return dst_p


def concat(parts: list[str | Path], dst: str | Path, *,
           reencode: bool = False, encoder: str = "auto",
           preset: str = "veryfast", timeout: int = 600,
           log_file: Path | None = None) -> Path:
    """Join parts via the concat demuxer. reencode=False uses -c copy (fast, exact)."""
    if len(parts) < 1:
        raise ValueError("concat needs at least one input part")
    for p in parts:
        if not Path(p).is_file():
            raise MediaProbeError(f"concat input not found: {p}")
    dst_p = Path(dst)
    dst_p.parent.mkdir(parents=True, exist_ok=True)
    lst = dst_p.parent / f"_concat_{time.time_ns()}.txt"
    # Absolute paths: the demuxer resolves list entries relative to the
    # list file, not the process CWD — relative entries break silently.
    lst.write_text("".join(f"file '{Path(p).absolute().as_posix().replace(chr(39), chr(39)+chr(92)+chr(39)+chr(39))}'\n"
                           for p in parts), encoding="utf-8")
    try:
        if reencode:
            venc, _ = _resolve_encoder(encoder)
            try:
                has_audio = bool(probe(parts[0]).audio_codec)
            except MediaProbeError:
                raise
            args = ["-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst),
                    "-c:v", venc, *_preset_args(venc, preset), "-pix_fmt", "yuv420p"]
            args += ["-c:a", AUDIO_ENCODER] if has_audio else ["-an"]
            args += [*_mp4_flags(dst_p), "-y", str(dst_p)]
            op = f"concat_reencode[{venc}]"
        else:
            args = ["-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst),
                    "-c", "copy", *_mp4_flags(dst_p), "-y", str(dst_p)]
            op = "concat_copy"
        run_ffmpeg(args, timeout=timeout, log_file=log_file, op=op)
    finally:
        lst.unlink(missing_ok=True)
    return dst_p


def render_keep(src: str | Path, keep: list, dst: str | Path, *,
                encoder: str = "auto", accurate: bool = True,
                fast_copy: bool = False, preset: str = "veryfast",
                timeout: int = 600, log_file: Path | None = None) -> Path:
    """Render an EDL keep-list: trim each span, then join. Sources untouched.

    keep entries: (start, end) tuples or {start,end} dicts (e.g. non_silent[]).
    Default re-encodes the join (correctness first); fast_copy=True joins with
    stream copy when the trims were also fast copies.
    """
    spans: list[tuple[float, float]] = []
    for k in keep:
        s, e = (k[0], k[1]) if isinstance(k, (list, tuple)) else (k["start"], k["end"])
        spans.append((float(s), float(e)))
    if not spans:
        raise ValueError("render_keep needs at least one keep span")
    dst_p = Path(dst)
    workdir = dst_p.parent / f"_edl_{time.time_ns()}"
    workdir.mkdir(parents=True, exist_ok=True)
    try:
        parts = [trim(src, s, e, workdir / f"part{i:03d}.mp4", encoder=encoder,
                      accurate=accurate and not fast_copy, preset=preset,
                      timeout=timeout, log_file=log_file)
                 for i, (s, e) in enumerate(spans)]
        return concat(parts, dst_p, reencode=not fast_copy, encoder=encoder,
                      preset=preset, timeout=timeout, log_file=log_file)
    finally:
        for p in workdir.glob("part*.mp4"):
            p.unlink(missing_ok=True)
        workdir.rmdir()


def extract_audio(src: str | Path, dst: str | Path, *,
                  sample_rate: int | None = None, channels: int | None = None,
                  start: float | None = None, duration: float | None = None,
                  timeout: int = 600, log_file: Path | None = None) -> Path:
    """Extract audio (optionally resampled / channel-converted / ranged).

    Seeking is placed AFTER -i (output seeking: sample-accurate, slower) so
    span extraction keeps exact source timestamps. New kwargs are additive.
    """
    src_p, dst_p = Path(src), Path(dst)
    info = probe(src_p)
    if not info.audio_codec:
        raise ValueError(f"no audio stream in {src_p}")
    if start is not None and start < 0:
        raise ValueError(f"extract start must be >= 0 (got {start})")
    if duration is not None and duration <= 0:
        raise ValueError(f"extract duration must be > 0 (got {duration})")
    acodec = "pcm_s16le" if dst_p.suffix.lower() == ".wav" else AUDIO_ENCODER
    dst_p.parent.mkdir(parents=True, exist_ok=True)
    args = ["-loglevel", "error", "-i", str(src_p)]
    if start is not None:
        args += ["-ss", repr(float(start))]
    if duration is not None:
        args += ["-t", repr(float(duration))]
    args += ["-vn"]
    if sample_rate is not None:
        args += ["-ar", str(int(sample_rate))]
    if channels is not None:
        args += ["-ac", str(int(channels))]
    args += ["-c:a", acodec, "-y", str(dst_p)]
    run_ffmpeg(args, timeout=timeout, log_file=log_file, op="extract_audio")
    return dst_p


def extract_frame(src: str | Path, t: float, dst: str | Path, *,
                  timeout: int = 120, log_file: Path | None = None) -> Path:
    src_p, dst_p = Path(src), Path(dst)
    if t < 0:
        raise ValueError(f"frame time must be >= 0 (got {t})")
    probe(src_p)
    dst_p.parent.mkdir(parents=True, exist_ok=True)
    # Full float precision (never %.3f): 3-decimal rounding once pushed a
    # seek 0.3 ms past its frame's pts and accurate seeking dropped the frame
    # (off-by-one at boundaries, found Phase 11). Round inputs unaffected.
    # -threads 1: the mjpeg frame-threaded encoder init races intermittently
    # in this build (exit 4294967274); single-frame output is unaffected.
    run_ffmpeg(["-loglevel", "error", "-threads", "1", "-ss", repr(float(t)),
                "-i", str(src_p), "-frames:v", "1", "-q:v", "2", "-y", str(dst_p)],
               timeout=timeout, log_file=log_file, op="extract_frame")
    return dst_p


def apply_vf(src: str | Path, vf: str, dst: str | Path, *,
             encoder: str = "auto", preset: str = "veryfast",
             timeout: int = 600, log_file: Path | None = None) -> Path:
    """Apply a video filter graph (resize/crop/fps…).

    Audio is re-encoded (same AAC policy as trim) so segments share uniform
    stream treatment for exact multi-part assembly; video is re-encoded.
    """
    if not vf or not vf.strip():
        raise ValueError("vf filter graph must be a non-empty string")
    src_p, dst_p = Path(src), Path(dst)
    info = probe(src_p)
    venc, _ = _resolve_encoder(encoder)
    dst_p.parent.mkdir(parents=True, exist_ok=True)
    args = ["-loglevel", "error", "-i", str(src_p), "-vf", vf,
            "-c:v", venc, *_preset_args(venc, preset), "-pix_fmt", "yuv420p"]
    args += ["-c:a", AUDIO_ENCODER] if info.audio_codec else ["-an"]
    args += [*_mp4_flags(dst_p), "-y", str(dst_p)]
    run_ffmpeg(args, timeout=timeout, log_file=log_file, op=f"apply_vf[{venc}]")
    return dst_p


def overlay_asset(base: str | Path, overlay_png: str | Path,
                  dst: str | Path, *, x: int, y: int, w: int, h: int,
                  start: float, duration: float, opacity: float = 1.0,
                  encoder: str = "auto", preset: str = "veryfast",
                  timeout: int = 600,
                  log_file: Path | None = None) -> Path:
    """Composite a PNG graphic over a video window (constructed-graphics path).

    Deterministic: fixed filter graph, fixed encoding policy. The PNG is
    looped as a secondary input; overlay is enabled only inside
    [start, start+duration]. Raises ValueError on invalid geometry/timing
    (structured contract failures are raised by the caller, never fallback).
    """
    base_p, ov_p, dst_p = Path(base), Path(overlay_png), Path(dst)
    if not base_p.is_file():
        raise MediaProbeError(f"overlay base not found: {base_p}")
    if not ov_p.is_file():
        raise MediaProbeError(f"overlay asset not found: {ov_p}")
    if x < 0 or y < 0 or w <= 0 or h <= 0:
        raise ValueError("overlay geometry must satisfy x,y>=0 and w,h>0")
    if not 0.0 < float(opacity) <= 1.0:
        raise ValueError("overlay opacity must be in (0, 1]")
    info = probe(base_p)
    if (info.width or 0) <= 0 or (info.height or 0) <= 0:
        raise ValueError(f"unknown base dimensions: {base_p}")
    if x + w > (info.width or 0) or y + h > (info.height or 0):
        raise ValueError("overlay placement exceeds base canvas")
    if start < 0 or duration <= 0:
        raise ValueError("overlay timing must satisfy start>=0, duration>0")
    if start + duration > float(info.duration or 0) + 1e-6:
        raise ValueError("overlay window exceeds base duration")
    venc, _ = _resolve_encoder(encoder)
    dst_p.parent.mkdir(parents=True, exist_ok=True)
    end = start + duration
    filt = (f"[1:v]format=rgba,colorchannelmixer=aa={float(opacity):.3f},"
            f"scale={w}:{h}:flags=lanczos[ov];"
            f"[0:v][ov]overlay={x}:{y}:enable='between(t,{start:.3f},{end:.3f})',"
            f"format=yuv420p")
    args = ["-loglevel", "error", "-i", str(base_p),
            "-loop", "1", "-framerate", "30", "-i", str(ov_p),
            "-filter_complex", filt, "-t", f"{float(info.duration):.3f}",
            "-c:v", venc, *_preset_args(venc, preset), "-pix_fmt", "yuv420p"]
    args += ["-c:a", AUDIO_ENCODER] if info.audio_codec else ["-an"]
    args += [*_mp4_flags(dst_p), "-y", str(dst_p)]
    run_ffmpeg(args, timeout=timeout, log_file=log_file,
               op=f"overlay_asset[{venc}]")
    return dst_p


def mix_audio(inputs: list[str | Path], dst: str | Path, *,
              timeout: int = 600, log_file: Path | None = None) -> Path:
    """Mix >= 2 audio sources with amix (duration=longest)."""
    if len(inputs) < 2:
        raise ValueError("mix_audio needs at least two inputs")
    for p in inputs:
        if not Path(p).is_file():
            raise MediaProbeError(f"mix input not found: {p}")
    dst_p = Path(dst)
    dst_p.parent.mkdir(parents=True, exist_ok=True)
    args = ["-loglevel", "error"]
    for p in inputs:
        args += ["-i", str(p)]
    args += ["-filter_complex", f"amix=inputs={len(inputs)}:duration=longest",
             "-c:a", AUDIO_ENCODER, "-y", str(dst_p)]
    run_ffmpeg(args, timeout=timeout, log_file=log_file, op="mix_audio")
    return dst_p


def fade_audio(src: str | Path, dst: str | Path, *,
               fade_in: float = 0.0, fade_out: float = 0.0,
               timeout: int = 600, log_file: Path | None = None) -> Path:
    """Gentle afade in/out on an audio stream."""
    from engine.core.media import probe as _probe
    if fade_in <= 0 and fade_out <= 0:
        raise ValueError("fade_audio needs fade_in>0 or fade_out>0")
    src_p, dst_p = Path(src), Path(dst)
    info = _probe(src_p)
    if not info.audio_codec:
        raise ValueError(f"no audio stream in {src_p}")
    dur = float(info.duration or 0)
    if dur <= 0:
        raise ValueError(f"unknown duration for {src_p}")
    if fade_in + fade_out >= dur:
        raise ValueError("fades exceed media duration")
    filt = []
    if fade_in > 0:
        filt.append(f"afade=t=in:st=0:d={fade_in:.3f}")
    if fade_out > 0:
        filt.append(f"afade=t=out:st={dur - fade_out:.3f}:d={fade_out:.3f}")
    dst_p.parent.mkdir(parents=True, exist_ok=True)
    args = ["-loglevel", "error", "-i", str(src_p),
            "-af", ",".join(filt), "-c:a", AUDIO_ENCODER,
            "-y", str(dst_p)]
    run_ffmpeg(args, timeout=timeout, log_file=log_file, op="fade_audio")
    return dst_p


def gain_audio(src: str | Path, dst: str | Path, *, gain_db: float,
               timeout: int = 600, log_file: Path | None = None) -> Path:
    """Apply a fixed gain in dB (volume filter, deterministic).

    Range limited to [-24, +24] dB. Used for per-scene audio states.
    """
    from engine.core.media import probe as _probe
    if not (-24.0 <= float(gain_db) <= 24.0):
        raise ValueError(f"gain_db out of range [-24, 24]: {gain_db}")
    src_p, dst_p = Path(src), Path(dst)
    info = _probe(src_p)
    if not info.audio_codec:
        raise ValueError(f"no audio stream in {src_p}")
    dst_p.parent.mkdir(parents=True, exist_ok=True)
    args = ["-loglevel", "error", "-i", str(src_p),
            "-af", f"volume={float(gain_db):.2f}dB",
            "-c:a", AUDIO_ENCODER, "-y", str(dst_p)]
    run_ffmpeg(args, timeout=timeout, log_file=log_file, op="gain_audio")
    return dst_p


def color_clip(color: str, width: int, height: int, duration: float,
               dst: str | Path, *, fps: int = 30,
               timeout: int = 600, log_file: Path | None = None) -> Path:
    """Deterministic solid-color video clip (title cards, backgrounds).

    Color as 0xRRGGBB. Reusable gateway op like make_silence.
    """
    import re as _re
    if not _re.fullmatch(r"0x[0-9a-fA-F]{6}", color):
        raise ValueError(f"color must be 0xRRGGBB, got {color!r}")
    if width <= 0 or height <= 0 or duration <= 0 or fps <= 0:
        raise ValueError("color_clip needs positive dimensions/duration/fps")
    dst_p = Path(dst)
    dst_p.parent.mkdir(parents=True, exist_ok=True)
    args = ["-loglevel", "error", "-f", "lavfi", "-i",
            f"color=c={color}:s={width}x{height}:d={duration}:r={fps}",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            *_mp4_flags(dst_p), "-y", str(dst_p)]
    run_ffmpeg(args, timeout=timeout, log_file=log_file, op="color_clip")
    return dst_p


# ---------------- Phase 14 burned-in captions (additive) ----------------

def _escape_sub_path(path: str) -> str:
    """Escape a subtitle path for the subtitles/ass filter argument.

    Windows drive letters and backslashes must be escaped; the whole value
    is single-quoted (arg-list invocation, no shell involved)."""
    return str(path).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")


def burn_subtitles(src: str | Path, sub_file: str | Path, dst: str | Path, *,
                   encoder: str = "auto", preset: str = "veryfast",
                   fontsdir: str | None = None, timeout: int = 600,
                   log_file: Path | None = None) -> Path:
    """Burn ASS/SRT subtitles into video (libass). Video re-encoded, audio
    stream-copied untouched (captions never alter audio)."""
    src_p, dst_p, sub_p = Path(src), Path(dst), Path(sub_file)
    info = probe(src_p)
    if not info.video_codec:
        raise ValueError(f"no video stream in {src_p}")
    if not sub_p.is_file():
        raise MediaProbeError(f"subtitle file not found: {sub_p}")
    if sub_p.suffix.lower() not in (".ass", ".ssa", ".srt"):
        raise ValueError(f"unsupported subtitle format {sub_p.suffix!r} "
                         f"(ass/srt only)")
    venc, _ = _resolve_encoder(encoder)
    filt = f"subtitles=filename='{ _escape_sub_path(str(sub_p)) }'"
    if fontsdir:
        filt += f":fontsdir='{ _escape_sub_path(str(fontsdir)) }'"
    dst_p.parent.mkdir(parents=True, exist_ok=True)
    args = ["-loglevel", "error", "-i", str(src_p), "-vf", filt,
            "-c:v", venc, *_preset_args(venc, preset), "-pix_fmt", "yuv420p",
            "-c:a", "copy", *_mp4_flags(dst_p), "-y", str(dst_p)]
    run_ffmpeg(args, timeout=timeout, log_file=log_file, op=f"burn_subtitles[{venc}]")
    return dst_p


# ---------------- Phase 13 track utilities (additive) ----------------

def trim_streams(src: str | Path, start: float, end: float, dst: str | Path, *,
                 streams: str = "av", encoder: str = "auto",
                 preset: str = "veryfast", timeout: int = 600,
                 log_file: Path | None = None) -> Path:
    """trim() restricted to stream subsets. streams=av is identical to trim();
    video drops audio (-an); audio drops video (-vn)."""
    if streams not in ("av", "video", "audio"):
        raise ValueError(f"streams must be av|video|audio (got {streams!r})")
    if streams == "av":
        return trim(src, start, end, dst, encoder=encoder, accurate=True,
                    preset=preset, timeout=timeout, log_file=log_file)
    src_p, dst_p = Path(src), Path(dst)
    info = probe(src_p)
    if info.duration <= 0:
        raise ValueError(f"cannot trim: unknown duration for {src_p}")
    start, end = validate_timestamps(float(start), float(end), info.duration)
    dst_p.parent.mkdir(parents=True, exist_ok=True)
    if streams == "video":
        if not info.video_codec:
            raise ValueError(f"no video stream in {src_p}")
        venc, _ = _resolve_encoder(encoder)
        args = ["-loglevel", "error", "-i", str(src_p),
                "-ss", repr(start), "-t", repr(end - start),
                "-map", "0:v:0", "-c:v", venc, *_preset_args(venc, preset),
                "-pix_fmt", "yuv420p", "-an",
                *_mp4_flags(dst_p), "-y", str(dst_p)]
        op = f"trim_video[{venc}]"
    else:
        if not info.audio_codec:
            raise ValueError(f"no audio stream in {src_p}")
        args = ["-loglevel", "error", "-i", str(src_p),
                "-ss", repr(start), "-t", repr(end - start),
                "-map", "0:a:0", "-vn", "-c:a", AUDIO_ENCODER,
                "-y", str(dst_p)]
        op = "trim_audio"
    run_ffmpeg(args, timeout=timeout, log_file=log_file, op=op)
    return dst_p


def mux(video: str | Path, audio: str | Path | None, dst: str | Path, *,
        timeout: int = 600, log_file: Path | None = None) -> Path:
    """Stream-copy mux of a video track with an audio track (or none).
    Inputs must already share container-compatible codecs."""
    v_p, dst_p = Path(video), Path(dst)
    if not v_p.is_file():
        raise MediaProbeError(f"mux video input not found: {v_p}")
    args = ["-loglevel", "error", "-i", str(v_p)]
    if audio is not None:
        a_p = Path(audio)
        if not a_p.is_file():
            raise MediaProbeError(f"mux audio input not found: {a_p}")
        args += ["-i", str(a_p), "-map", "0:v:0", "-map", "1:a:0?",
                 "-c", "copy"]
    else:
        args += ["-map", "0:v:0", "-c", "copy", "-an"]
    args += [*_mp4_flags(dst_p), "-y", str(dst_p)]
    run_ffmpeg(args, timeout=timeout, log_file=log_file, op="mux")
    return dst_p


def make_silence(duration: float, dst: str | Path, *, sample_rate: int = 44100,
                 channels: int = 1, timeout: int = 120,
                 log_file: Path | None = None) -> Path:
    """Generate digital-silence WAV (fills muted replacement tracks)."""
    if duration <= 0:
        raise ValueError(f"silence duration must be > 0 (got {duration})")
    dst_p = Path(dst)
    dst_p.parent.mkdir(parents=True, exist_ok=True)
    layout = "mono" if channels == 1 else "stereo"
    run_ffmpeg(["-loglevel", "error", "-f", "lavfi", "-i",
                f"anullsrc=cl={layout}:r={int(sample_rate)}:d={float(duration)}",
                "-c:a", "pcm_s16le", "-y", str(dst_p)],
               timeout=timeout, log_file=log_file, op="make_silence")
    return dst_p


def fit_filter(src_w: int, src_h: int, dst_w: int, dst_h: int,
               strategy: str = "cover", fps: float | None = None) -> str:
    """Build an aspect-safe fit filter. cover (default) fills + center-crops;
    contain letterboxes with padding; crop center-crops (source must cover
    the target). Never distorts: plain stretching is refused."""
    if strategy not in ("cover", "contain", "crop", "letterbox"):
        raise ValueError(f"fit strategy must be cover|contain|crop|letterbox "
                         f"(got {strategy!r})")
    for name, value in (("src_w", src_w), ("src_h", src_h),
                        ("dst_w", dst_w), ("dst_h", dst_h)):
        if int(value) <= 0:
            raise ValueError(f"{name} must be > 0")
    if strategy == "cover":
        vf = (f"scale={dst_w}:{dst_h}:force_original_aspect_ratio=increase,"
              f"crop={dst_w}:{dst_h}")
    elif strategy in ("contain", "letterbox"):
        vf = (f"scale={dst_w}:{dst_h}:force_original_aspect_ratio=decrease,"
              f"pad={dst_w}:{dst_h}:(ow-iw)/2:(oh-ih)/2")
    else:
        if src_w < dst_w or src_h < dst_h:
            raise ValueError(f"crop {dst_w}x{dst_h} exceeds source {src_w}x{src_h}")
        vf = f"crop={dst_w}:{dst_h}"
    if fps is not None:
        if float(fps) <= 0:
            raise ValueError("fps must be > 0")
        vf += f",fps={float(fps)}"
    return vf


def frame_health_check(src: str | Path, *, black_min_d: float = 0.5,
                       black_pix_th: float = 0.10, timeout: int = 600,
                       log_file: Path | None = None) -> dict:
    """One analysis pass: black intervals (blackdetect) + stderr error lines.
    Returns {black: [{start,end,duration}], errors: [...]}. Never raises for
    content findings (only for unreadable input / ffmpeg failure)."""
    src_p = Path(src)
    probe(src_p)  # raises MediaProbeError on missing/invalid input
    exe = _need_exe()
    cmd = [exe, "-hide_banner", "-i", str(src_p), "-an",
           "-vf", f"blackdetect=d={float(black_min_d)}:pix_th={float(black_pix_th)}",
           "-f", "null", "-"]
    import re as _re
    import subprocess as _sp
    import time as _time
    t0 = _time.perf_counter()
    try:
        proc = _sp.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=timeout)
    except _sp.TimeoutExpired as exc:
        raise FfmpegError(f"frame health check timed out on {src_p}", cmd=cmd,
                          version=ffmpeg_version(), exit_code=-2,
                          stderr_tail="TIMEOUT",
                          duration_s=round(_time.perf_counter() - t0, 3)) from exc
    if proc.returncode != 0:
        raise FfmpegError(f"frame health check failed on {src_p}",
                          cmd=cmd, version=ffmpeg_version(),
                          exit_code=proc.returncode,
                          stderr_tail=_tail(proc.stderr),
                          duration_s=round(_time.perf_counter() - t0, 3))
    stderr = proc.stderr or ""
    black: list[dict] = []
    for m in _re.finditer(r"black_start:([0-9.]+)\s+black_end:([0-9.]+)", stderr):
        s, e = float(m.group(1)), float(m.group(2))
        black.append({"start": s, "end": e, "duration": round(e - s, 3)})
    errors = [ln.strip() for ln in stderr.splitlines()
              if "error" in ln.lower()][:20]
    return {"black": black, "errors": errors}


# ---------------- output validation ----------------

@dataclass
class ValidateExpect:
    duration: float | None = None
    duration_tol: float = 0.4
    width: int | None = None
    height: int | None = None
    fps: float | None = None
    fps_tol: float = 1.0
    video_codec: str | None = None
    audio_codec: str | None = None
    require_audio: bool = False
    av_sync_tol: float = 0.5


def validate_output(path: str | Path, expect: ValidateExpect) -> QCReport:
    """Assess a render against expectations. Missing file = fail verdict (not raise)."""
    checks: list[QCCheck] = []
    p = Path(path)
    if not p.is_file():
        return QCReport(verdict="fail",
                        checks=[QCCheck("file_exists", False, f"missing: {p}")],
                        suggested_fix="re-run the render; inspect the render log")
    checks.append(QCCheck("file_exists", True, f"{p.stat().st_size} bytes"))
    try:
        info = probe(p)
    except MediaProbeError as exc:
        return QCReport(verdict="fail",
                        checks=[*checks, QCCheck("readable", False, str(exc))],
                        suggested_fix="output is corrupt; re-render")
    checks.append(QCCheck("readable", True, f"{info.video_codec}/{info.audio_codec or 'no-audio'}"))

    def _check(name: str, ok: bool, detail: str) -> None:
        checks.append(QCCheck(name, ok, detail))

    if expect.duration is not None:
        _check("duration", abs(info.duration - expect.duration) <= expect.duration_tol,
               f"got={info.duration:.3f}s want={expect.duration:.3f}s tol={expect.duration_tol}")
    if expect.width is not None:
        _check("width", info.width == expect.width, f"got={info.width} want={expect.width}")
    if expect.height is not None:
        _check("height", info.height == expect.height, f"got={info.height} want={expect.height}")
    if expect.fps is not None:
        _check("fps", abs(info.fps - expect.fps) <= expect.fps_tol,
               f"got={info.fps:.2f} want={expect.fps:.2f}")
    if expect.video_codec is not None:
        _check("video_codec", info.video_codec == expect.video_codec,
               f"got={info.video_codec} want={expect.video_codec}")
    if expect.audio_codec is not None:
        _check("audio_codec", info.audio_codec == expect.audio_codec,
               f"got={info.audio_codec} want={expect.audio_codec}")
    if expect.require_audio:
        _check("audio_present", bool(info.audio_codec),
               "audio stream present" if info.audio_codec else "NO audio stream")
    if info.audio_streams and float(info.audio_streams[0].get("duration") or 0) > 0:
        gap = abs(info.duration - float(info.audio_streams[0]["duration"]))
        _check("av_sync", gap <= expect.av_sync_tol,
               f"|container-audio|={gap:.3f}s tol={expect.av_sync_tol}")
    else:
        _check("av_sync", True, "skipped: per-stream durations unavailable")
    failed = [c.name for c in checks if not c.passed]
    return QCReport(verdict="pass" if not failed else "fail", checks=checks,
                    suggested_fix="" if not failed else f"failed: {', '.join(failed)}; re-render or loosen tolerances")
