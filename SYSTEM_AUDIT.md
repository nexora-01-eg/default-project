# SYSTEM_AUDIT.md — Local AI Video Editing Engine

**Date:** 2026-09-16 (UTC)
**Machine:** Windows 10 Pro for Workstations, 64-bit (Build 19045 / 22H2)
**Project dir:** `C:\Users\NOUR SOFT\Documents\Default Project` (empty, not a git repo)
**Audit mode:** read-only inspection, nothing installed or modified.

---

## 1. Hardware

| Component | Detail |
|---|---|
| CPU | Intel Core i7-7820HQ @ 2.90 GHz, 4 cores / 8 threads (Kaby Lake-H, mobile workstation) |
| RAM | 16 GB total (15.88 GiB visible), ~7.6 GB free at audit time |
| iGPU | Intel HD Graphics 630, 1 GB AdapterRAM, driver 31.0.101.2130 — **Intel Quick Sync Video available** (H.264 encode/decode assist) |
| dGPU | NVIDIA GeForce 940MX, 2 GB VRAM, driver 553.46 — entry-level Maxwell (GM108, CC 5.0), **not a compute GPU** |
| Storage | C: 111 GB free / 187 GB total · D: 361 GB free · E: 195 GB free · F: 200 GB free — ample space for footage, models, renders |

**Implications:**
- CPU is the primary workhorse. 4C/8T is fine for 1080p FFmpeg + Whisper `base/small`, slow for `medium+` or 4K.
- 940MX (2 GB) can accelerate H.264 NVENC/NVDEC for light work but **cannot comfortably run large PyTorch models**; VRAM too small for Whisper-large or SD-class workloads. Treat CUDA as *optional encode/transcribe assist*, not as training/inference server.
- 16 GB RAM is workable but tight if running Whisper + OpenCV + FFmpeg simultaneously on long footage. Pipeline must be **sequential/chunked, never load full video into RAM**.
- Intel Quick Sync (HD 630) is actually the most reliable HW encoder on this box for H.264 (`h264_qsv`).

## 2. Operating System

- Windows 10 Pro for Workstations, 64-bit, Build 19045.
- PowerShell 5.1 confirmed (this audit ran under it).
- No WSL check performed yet (optional; native Windows is the target per `setup.ps1` requirement).

## 3. Installed Software (verified)

| Tool | Version | Status |
|---|---|---|
| Node.js | v24.14.1 | ✅ installed |
| npm | 11.11.0 | ✅ installed |
| pnpm / bun | — | ❌ not found |
| Git | 2.53.0.windows.2 | ✅ installed |
| winget | v1.29.290 | ✅ available (primary installer route) |
| Python (`python`, `python3`, `pip`) | — | ❌ **NOT installed** (only MS Store shim stubs in WindowsApps) |
| `py` launcher | — | ❌ not found |
| conda / pipx | — | ❌ not found |
| FFmpeg / FFprobe | — | ❌ **NOT installed** |
| ImageMagick | — | ❌ not found |
| SoX | — | ❌ not found |
| NVIDIA driver / nvidia-smi | 553.46 / CUDA driver 12.4 | ✅ driver present |
| CUDA Toolkit (`nvcc`) | — | ❌ not installed (expected; not required) |
| chocolatey | — | ❌ not found |

No Python packages (torch, onnx, whisper, opencv, etc.) could exist — there is no Python interpreter to host them.
No prior project files exist — directory is empty.

## 4. Missing Dependencies (priority order)

1. **Python 3.11** (required — engine core). Prefer `winget install Python.Python.3.11`.
2. **FFmpeg full build + FFprobe** (required — all media I/O). Prefer `winget install Gyan.FFmpeg` or manual official build + PATH.
3. **Python venv + pip packages** (required): `numpy, pillow, opencv-python, faster-whisper, scenedetect, pydantic, click/rich, pytest`.
4. **Node Remotion toolchain** (deferred to Phase 11 — init only when graphics phase starts; Node already ready).
5. Optional: SoX, ImageMagick (deferred; FFmpeg covers 95%).

## 5. GPU / AI Acceleration Capabilities

| Capability | Status | Notes |
|---|---|---|
| NVIDIA driver + CUDA UMD | ✅ CUDA 12.4 driver | `nvidia-smi` works, 0 MiB in use |
| NVENC/NVDEC (940MX) | ⚠️ present but weak | H.264 encode OK; H.265 encode **not supported** on GM108. Always probe encoders at runtime, fall back to CPU/QSV |
| CUDA compute for PyTorch | ⚠️ CC 5.0, 2 GB | PyTorch CUDA builds still support CC 5.0 for now, but OOM risk is high. **Default to CPU inference**; CUDA opt-in only |
| Intel Quick Sync | ✅ via HD 630 | Best local H.264 HW path (`h264_qsv`). Verify with `ffmpeg -encoders \| findstr qsv` after install |
| ONNX Runtime / OpenVINO / DirectML | ❌ not installed | Evaluate in Phase 6; DirectML is the interesting Windows-native option for Intel+NVIDIA |
| whisper.cpp | ❌ not installed | Candidate for low-RAM transcription path vs `faster-whisper` |

**Architecture rule derived from this:** every accelerated path MUST have a CPU fallback, probed at runtime — never assume NVIDIA exists.

## 6. Recommended Architecture

Given this box (mid CPU, weak dGPU, no Python/FFmpeg yet):

- **Language split:** Python = analysis/editing/audio/subtitles/QC brain; Node/Remotion = isolated animated-caption renderer only.
- **Media backbone:** FFmpeg CLI (subprocess) for all decode/encode/cut/mix — never hand-roll codecs.
- **STT:** `faster-whisper` (CTranslate2, CPU-friendly) default model `small` (fallback `base` if RAM-constrained); `whisper.cpp` documented as low-RAM alternative.
- **Scene detection:** PySceneDetect (content-based) + FFmpeg `select` filters as fallback; OpenCV for faces/motion later.
- **Orchestration:** staged Python pipeline (inspect → analyze → plan → execute → render → QC → fix) with JSON project state + per-stage caching so re-runs never redo expensive analysis.
- **Render strategy:** 1080p-first; 4K allowed but flagged slow on this hardware. Encoder auto-select: `h264_nvenc` → `h264_qsv` → `libx264`.
- **Storage strategy:** keep models + cache on D: (361 GB free) if C: pressure arises; renders default to project-local `output/`.

## 7. Installation Plan (free-first, official sources only)

1. `setup.ps1 -Install` → installs Python 3.11 + FFmpeg via winget (official manifests), verifies + records versions.
2. `setup.ps1 -PythonOnly/-FfmpegOnly` flags for granular runs; never reinstalls working tools (idempotent checks first).
3. Create `.venv` in project, `pip install -r requirements.txt` (pinned, PyPI only).
4. `video-engine doctor` re-verifies everything and writes `logs/doctor.json`.
5. Remotion scaffold deferred to Phase 11.

## 8. Potential Compatibility Problems

1. **Python 3.12+ vs `faster-whisper`/Torch wheels:** pin Python **3.11** for widest prebuilt-wheel coverage on Windows.
2. **940MX + new CUDA toolkits:** no local CUDA toolkit needed; only driver matters. Do not install full toolkit unless NVENC debugging demands it.
3. **Node 24 vs old Remotion templates:** scaffold with current Remotion at Phase 11; don't pre-install now (version drift risk).
4. **Windows path spaces** (`NOUR SOFT`): all subprocess calls must use arg-lists, never shell-string concatenation. Tests must cover spaced paths.
5. **MS Store Python shim:** `python` currently opens the Store. Real install must take PATH precedence; installer verifies with `python --version` + `where.exe python`.
6. **RAM pressure on long 4K jobs:** enforce chunked analysis + 1080p proxy workflow; document in TROUBLESHOOTING.md.
7. **No test footage:** must generate synthetic media (FFmpeg lavfi) — never require copyrighted samples.

---
*Next: see `ARCHITECTURE.md` for the module design this audit drives, and `DEPENDENCIES.md` for the evaluated tool matrix.*
