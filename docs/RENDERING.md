# RENDERING.md — Phase 4 engine (`engine/rendering/ffmpeg.py`)

The ONLY module allowed to construct ffmpeg commands. Everything else
(orchestrator, CLI, future phases) calls these functions. All invocations are
arg-lists (no shell, spaces-safe), non-destructive, and logged with command,
ffmpeg version, encoder, timing, exit code, and stderr tail.

## Encoder detection (`detect_encoders` / `select_encoder`)

Two-step, because **listed ≠ working**:

1. Parse `ffmpeg -encoders` for `h264_nvenc / h264_qsv / h264_amf / libx264 / aac / pcm_s16le`.
2. Smoke-verify each video candidate: actually encode 1 s of synthetic media.
   A listed-but-broken encoder (no GPU session, missing runtime) is recorded
   with its error and skipped with reason.

Result cached in `.cache/encoders.json`, invalidated on ffmpeg version change.
`select_encoder(priority)` returns `{selected_encoder, hardware_acceleration,
reason, verified}` following `encoder_priority` from config
(`h264_nvenc → h264_qsv → h264_amf → libx264`).

Measured on the reference machine (FFmpeg 9.0.1, 2026-09-17):

| Encoder | Listed | Verified | Note |
|---|---|---|---|
| h264_nvenc | yes | **no** | 940MX present, but headless smoke encode yields no packets |
| h264_qsv | yes | **yes** | Intel HD 630 Quick Sync → **auto-selected** |
| h264_amf | yes | **no** | no AMD GPU (expected) |
| libx264 | yes | **yes** | guaranteed CPU fallback |

## Operations

| Function | Mode | Notes |
|---|---|---|
| `trim(src, start, end, dst)` | `accurate=True`: output seeking + re-encode (frame-accurate). `accurate=False`: input seeking + `-c copy` (fast, keyframe-approximate) | timestamps validated against probed duration BEFORE ffmpeg spawns |
| `concat(parts, dst)` | `reencode=False`: concat demuxer + `-c copy`; `True`: re-encode join | file-list escaping handles spaces/quotes in paths |
| `render_keep(src, keep, dst)` | trim each span → re-encode join (`fast_copy=True` opts into copy) | keep = `(start,end)` tuples or `{start,end}` dicts (e.g. `non_silent[]`); temp parts cleaned up |
| `extract_audio` | wav→pcm_s16le, else aac | raises on audio-less input |
| `extract_frame` | single frame at `t` | `t >= 0` validated |
| `apply_vf(src, vf, dst)` | video re-encode, **audio stream-copied** | empty filter rejected |
| `mix_audio(inputs, dst)` | `amix=inputs=N:duration=longest` | ≥2 existing inputs required |

Re-encode preset defaults to `veryfast` (speed first; quality preset policy arrives with Phase 12/14 templates).

## Errors & logging

`FfmpegError` carries `cmd, version, exit_code, stderr_tail (30 lines), duration_s`.
`run_ffmpeg(..., log_file, stage, op)` writes ok/failed JSONL events; timeouts
raise with `exit_code=-2`. Programmer errors (bad timestamps, empty EDL,
missing inputs) raise `ValueError`/`MediaProbeError` without spawning ffmpeg.

## Output validation (`validate_output`)

Returns the shared `QCReport` model (no parallel schema): file_exists,
readable, duration (±0.4 s), resolution, fps (±1), codecs, audio presence, and
A/V sync (|container−audio| ≤ 0.5 s, skipped honestly when ffprobe lacks
per-stream durations). Missing/corrupt output = `fail` verdict, not an exception.

## CLI

`video-engine render <project> [--keep "0-5,8-12.5"] [--encoder auto|NAME]
[--fast] [--out NAME]` → `projects/<id>/renders/*.mp4` + `*_validation.json`,
stage marked `done` / `validation_failed` / `failed`. Exit codes: 0 pass,
2 input error, 5 render failure, 6 validation failure.
