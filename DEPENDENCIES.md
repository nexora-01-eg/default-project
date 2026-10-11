# DEPENDENCIES.md — evaluated tool matrix (free-first)

Legend: **R** required · **O** optional · **D** deferred to its phase. All licenses verified as free/open-source or gratis-official.

## Required (install in Phase 2 via `setup.ps1`)

| Dependency | Why | Method (Windows) | Version pin | License | Req |
|---|---|---|---|---|---|
| Python 3.11 | engine runtime; widest wheel coverage on Win | `winget install Python.Python.3.11` (official) | 3.11.x | PSF | R |
| FFmpeg + FFprobe (full build) | all decode/encode/cut/mix/probe; the media backbone | `winget install Gyan.FFmpeg`11024+PATH, verify `ffmpeg -version` | ≥ 6.0 (7.x preferred) | GPL/LGPL (build-dependent) | R |
| pip + venv | isolated Python env (`.venv`) | ships with Python | — | MIT/PSF | R |
| faster-whisper | local STT, CTranslate2 CPU-friendly, word timestamps | `pip install faster-whisper` | `>=1.0,<2` (installed 1.2.1, CTranslate2 4.8.2) | MIT | R |
| Whisper weights (per-model, on demand) | STT accuracy; fetched explicitly via `download-model` | Hugging Face `Systran/faster-whisper-*` | tiny ~75 MB · base ~145 MB · small ~466 MB · medium ~1.5 GB · large-v3 ~3 GB | derived from OpenAI Whisper (MIT); see HF repo | D |
| scenedetect (`PySceneDetect`) | scene/shot boundaries | `pip install scenedetect` (+ `opencv-python` pulls) | `>=0.6` | MIT | R |
| opencv-python | faces/motion/frames | `pip install opencv-python` | `>=4.8` | Apache-2.0 | R |
| numpy / pillow | numeric + image overlays/thumbnails | pip | `numpy>=1.26`, `pillow>=10` | BSD/HPND | R |
| pydantic v2 | typed project/EDL/QC schemas | pip | `>=2.0` | MIT | R |
| click + rich | CLI + readable terminal output | pip | `click>=8`, `rich>=13` | BSD/MIT | R |
| pytest | unit/integration/real-media tests | pip | `>=8` | MIT | R |
| Git | versioning (already ✅ 2.53) | present — do not reinstall | 2.53 | GPL | R |

## Deferred / phase-gated (do NOT install now)

| Dependency | Why deferred | Phase |
|---|---|---|
| Node Remotion toolchain | needs subtitle data model first; Node 24 already ✅ | 11 |
| whisper.cpp | low-RAM STT alternative if `small` OOMs on 16 GB | 6 |
| ONNX Runtime / DirectML | optional accel after CPU baseline works | 6+ |
| SoX / RNNoise / LADSPA | FFmpeg `afftdn,acompressor,loudnorm` covers v1; revisit if QC flags audio | 9 |
| MoviePy | rejected for v1 — FFmpeg CLI is faster/deterministic; keep documented only | — |
| Blender / Kdenlive / MLT | rejected for v1 — poor headless-automation fit vs FFmpeg+Remotion | — |
| ImageMagick | FFmpeg+Pillow cover thumbnails/overlays; add only on demand | 13 |

## Installation policy (enforced by `setup.ps1`)

1. Detect-first: every step checks `Get-Command` / `--version` before installing; working tools are never reinstalled.
2. Official sources only: winget official manifests + PyPI. No cracked/pirated/suspicious binaries, ever.
3. Verify-after: each install re-runs its version check; failure aborts with a human-readable error (never silently continues past a critical dependency).
4. Record: `setup.ps1` writes `logs/setup_report.json` with `{tool, version, method, status}`.
5. `video-engine doctor` re-verifies at any time and reports PATH problems (esp. MS Store Python shim shadowing).

## Current machine delta (from SYSTEM_AUDIT.md)

- Install now (Phase 2): Python 3.11, FFmpeg, then `.venv` + `requirements.txt`.
- Already OK: Node 24, npm 11, Git 2.53, NVIDIA driver 553.46, winget.
- Never needed here: full CUDA toolkit (`nvcc`), choco, conda.

---
## Phased implementation plan (status-tracked)

- [x] **Phase 0 — System audit** (`SYSTEM_AUDIT.md` done 2026-09-16)
- [x] **Phase 1 — Architecture + core scaffold** (verified 2026-09-16: `pytest` 6/6 pass)
- [x] **Phase 2 — Dependency installation** (verified 2026-09-16: Python 3.11.9 + FFmpeg 9.0.1 + 40 pip pkgs; synthetic 10 s fixture analyzes e2e, cache hit confirmed)
- [x] **Phase 3 — Core project engine** (project store + config + cache + JSONL live since Phase 1; audio analysis `analyze_audio` added 2026-09-17, 18/18 tests)
- [x] **Phase 4 — FFmpeg integration** (encoder smoke-detection + service layer + cut/concat + `render` CLI, 2026-09-17, 33 passed / 1 HW-skip; auto-selects `h264_qsv` on this box)
- [x] **Phase 5 — Media analysis** (done as audio analysis in Phase 3: cached mediainfo + silence + volume stats, 2026-09-17)
- [x] **Phase 6 — Whisper integration** (faster-whisper, word timestamps, filler annotation, span-aware cache, 2026-09-17: 55 passed / 1 HW-skip; verified cpu/int8 on this box, CUDA rejected — CC 5.0)
- [x] **Phase 7 — Scene detection** (PySceneDetect 0.7.1 content/threshold + ffmpeg fallback, `scenes` CLI, 2026-09-17: 71 passed / 1 HW-skip)
- [x] **Phase 8 — Automatic editing (plan)** (rule-based EDL: long silence + filler removal, scene-aware, conservative; 2026-09-17: 90 passed / 1 HW-skip; plan only, no rendering)
- [x] **Phase 9 — EDL rendering / execution** (plan→render→QC + manifest + reuse, 2026-09-17: 118 passed / 1 HW-skip; auto `h264_qsv`, libx264 fallback verified)
- [x] **Phase 10 — Editing intelligence** (evidence-backed safety/density/pacing/repetition/jump-cut + conservative refinement, 2026-09-17: 140 passed / 1 HW-skip; no rendering)
- [x] **Phase 11 — Visual intelligence** (OpenCV metrics + sampling + adapters + `visual` CLI, 2026-09-17: 158 passed / 1 HW-skip; no models downloaded, no rendering)
- [x] **Phase 12 — Editor brain** (style-driven professional plan + `editor-plan` CLI, 2026-09-17: 188 passed / 1 HW-skip; planning only, no rendering)
- [x] **Phase 13 — Plan execution** (approval boundary + B-roll overlays + extended QC + manifests, 2026-09-18: 232 passed / 1 HW-skip; local assets only, no downloads)
- [x] **Phase 14 — Subtitles/captions** (segmentation, styles, Arabic/RTL, SRT/VTT/ASS, sidecar + burned-in, mapping, caption QC, 2026-09-18: 270 passed / 1 HW-skip; no new models, no downloads)
- [x] **Phase 15 — Caption visual polish** (contrast/placement/emphasis, visual ASS, calibrated visibility QC, 2026-09-19: 296 passed / 1 HW-skip; no downloads, no identity, no animation)
- [x] **Phase 16 — Caption-aware scene pacing** (deterministic signals + conservative recommendations + approval, 2026-09-19; plan only, no rendering)
- [x] **Phase 17 — Approval-gated pacing execution** (explicit selection, EDL-compatible TRIMs, caption/visual remap, Phase 13 render reuse, QC + manifest, 2026-09-19)
- [ ] **Phase 18+ — further capabilities** — NOT started
- [ ] **Phase 8 — Automatic editing** (rule-based EDL: silence/filler/repeat/dead-air)
- [ ] **Phase 9 — Audio engine** (afftdn, de-ess-ish EQ, compressor, loudnorm, ducking)
- [ ] **Phase 10 — Subtitle engine** (srt/ass/vtt writers, safe-margin line breaking)
- [ ] **Phase 11 — Remotion graphics** (animated captions, lower thirds, titles from subtitle JSON)
- [ ] **Phase 12 — Rendering** (filter-graph builder from RenderPlan, preset matrix)
- [ ] **Phase 13 — Quality control** (`QC_REPORT.json`, retry budget ≤ 3)
- [ ] **Phase 14 — Templates** (youtube/shorts/podcast/educational packs + presets 1080p/4K/9:16/1:1)
- [ ] **Phase 15 — End-to-end testing** (synthetic media → full pipeline → QC pass on THIS machine)

Rule: no phase is marked complete without its tests passing on this machine or a dated note explaining the blocker.
