# Local AI Video Editing Engine

Autonomous, local-first, free/open-source video editing brain. See `SYSTEM_AUDIT.md`, `ARCHITECTURE.md`, `DEPENDENCIES.md`.

## Status (2026-09-16)

- ✅ Phase 0: system audit (this machine: Win10, i7-7820HQ, 16 GB, Intel HD 630 + 940MX, no Python/FFmpeg yet)
- ✅ Phase 1: core scaffold (`engine/` + CLI + tests) — `pytest` 6/6 pass
- ✅ Phase 2: Python 3.11.9 + FFmpeg 9.0.1 + 40 pip packages installed; `analyze` verified e2e on synthetic 10 s fixture (cache hit confirmed)
- ✅ Phase 3 (2026-09-17): audio analysis — volumes, loudness, silence/non-silent timestamps; `analyze` writes `media_info.json` + `audio_analysis.json`
- ✅ Phase 4 (2026-09-17): FFmpeg service layer — smoke-verified encoder auto-select (**h264_qsv** on this box), trim/concat/EDL render, `render` CLI, output validation
- ✅ Phase 5/6 (2026-09-17): local Whisper STT — `transcribe` + `download-model` CLI, word timestamps, filler annotation, span-aware caching (**cpu/int8** verified, ~7x realtime on tiny)
- ✅ Phase 7 (2026-09-17): scene detection — `scenes` CLI (content/threshold/ffmpeg), frame-exact boundaries, recorded auto-fallback, cache invalidation (PySceneDetect 0.7.1)
- ✅ Phase 8 (2026-09-17): edit decision engine — `edit` CLI builds KEEP/REMOVE EDL on source coordinates (silence + filler rules, scene-aware, conservative defaults; plan only, no rendering)
- ✅ Phase 9 (2026-09-17): EDL execution — `render` CLI executes the EDL to `renders/*.mp4` + manifest (plan→render→QC, A/V sync checked, reuse on identical work; 118 passed / 1 skipped)
- ✅ Phase 10 (2026-09-17): editing intelligence — `edit-analyze` CLI over the base EDL (evidence-backed safety/density/pacing/repetition/jump-cut analysis + conservative refinement; analysis only; 140 passed / 1 skipped)
- ✅ Phase 11 (2026-09-17): visual intelligence — `visual` CLI over project scenes (OpenCV metrics, deterministic sampling, honest capability reporting; faces/objects/embeddings unavailable on this box, no downloads; 158 passed / 1 skipped)
- ✅ Phase 12 (2026-09-17): editor brain — `editor-plan` CLI (11 styles, hook/story/density/pacing/cut/broll/audio/repetition/conflict planning with evidence; conservative, planning only; 188 passed / 1 skipped)
- ✅ Phase 13 (2026-09-18): plan execution — `approve-plan` + `render-plan` CLIs (immutable approval, B-roll overlays, extended QC, provenance manifests, reuse cache; 232 passed / 1 skipped)
- ✅ Phase 14 (2026-09-18): subtitles/captions — `captions` + `approve-captions` CLIs, `render-plan --captions` (segmentation, 5 styles, Arabic/RTL, SRT/VTT/ASS, sidecar + burned-in, timeline mapping, caption QC; 270 passed / 1 skipped)
- ✅ Phase 15 (2026-09-19): caption visual polish — `caption-visual` + `approve-caption-visual` (contrast/placement/emphasis intelligence, visual ASS, calibrated visibility QC; 296 passed / 1 skipped)
- ✅ Phase 16 (2026-09-19): caption-aware scene pacing — `caption-pacing` + `approve-caption-pacing` (deterministic pacing signals + conservative recommendations + approval; plan only, no rendering, no EDL mutation)
- ✅ Phase 17 (2026-09-19): approval-gated pacing execution — `approve-caption-pacing-execution` + `execute-caption-pacing` (explicit selection, EDL-compatible TRIMs, caption/visual remap, Phase 13 render reuse, QC + manifest)

## Quickstart (after Phase 2)

```powershell
.\setup.ps1 -Install
.\.venv\Scripts\Activate.ps1
python scripts\make_test_media.py
python -m engine.cli doctor
python -m engine.cli analyze tests\fixtures\sample_10s.mp4
python -m engine.cli status <project_id>
python -m engine.cli render <project_id> --keep "0-5,8-12.5"
python -m engine.cli download-model tiny   # one-time, explicit (~75 MB)
python -m engine.cli transcribe input.mp4 --model tiny
python -m engine.cli scenes input.mp4 --method content
python -m engine.cli edit <project_id> --min-silence 0.8
python -m engine.cli render <project_id>   # EDL mode (or --keep ranges)
python -m engine.cli edit-analyze <project_id>   # intelligence (no render)
python -m engine.cli visual <project_id>   # visual analysis (no render)
python -m engine.cli editor-plan <project_id> --style talking_head   # plan (no render)
python -m engine.cli approve-plan <project_id> --broll-map "0-4=clip.mp4"   # approve
python -m engine.cli captions <project_id> --style clean   # caption plan (no render)
python -m engine.cli approve-captions <project_id> --mode burned_in   # approve captions
python -m engine.cli render-plan <project_id> --captions   # render with captions
python -m engine.cli caption-visual <project_id>   # visual polish plan (no render)
python -m engine.cli approve-caption-visual <project_id>   # approve polish
python -m engine.cli caption-pacing <project_id> --style general   # pacing plan (no render)
python -m engine.cli approve-caption-pacing <project_id>   # approve pacing
python -m engine.cli approve-caption-pacing-execution <project_id> --recommendation-id rec_0001   # approve ops
python -m engine.cli execute-caption-pacing <project_id> --dry-run   # preview (no render)
python -m engine.cli execute-caption-pacing <project_id>   # render approved pacing ops
python -m engine.cli render-plan <project_id> --dry-run   # validate only
python -m engine.cli render-plan <project_id>   # execute approved plan
```

- ⏳ Next phases per `DEPENDENCIES.md` — NOT started

## Layout

`engine/` (brain) · `templates/` · `assets/` · `scripts/` · `tests/` · `docs/` · `input/` `output/` `projects/`
