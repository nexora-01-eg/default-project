# ARCHITECTURE.md — Local AI Video Editing Engine

## 1. Design principles

1. **Non-destructive by construction.** Source footage is never modified. All edits are data (EDL/JSON) first; renders are derived artifacts.
2. **Staged pipeline with cache.** Each stage reads the previous stage's JSON and writes its own. Re-running skips completed stages via content-hash cache.
3. **CPU-first, accelerate optionally.** Every HW path (NVENC/QSV/CUDA) is probed at runtime with CPU fallback. No stage may hard-require NVIDIA.
4. **CLI + library, not CLI-only.** Every capability is an importable Python function; the CLI (`video-engine`) is a thin wrapper.
5. **Free-first / offline-capable.** No cloud API in the critical path. Network use is limited to one-time installs/downloads.
6. **Extensible registries.** Templates, presets, and pipeline stages register by name — adding one never rewrites the orchestrator.

## 2. Pipeline (the Brain)

```
INPUT → INSPECT → ANALYZE → UNDERSTAND → PLAN → EXECUTE → RENDER → QC → (FIX → RENDER → QC) → FINAL
```

| Stage | Module | Input → Output |
|---|---|---|
| inspect | `core.media` (ffprobe) | file → `analysis/media_info.json` |
| analyze | `analysis/*` (scenes, silence, speech, faces…) | media + config → per-stream JSON |
| understand | `editing.decisions` (rule engine) | analysis → `edit/edit_decision.json` (EDL) |
| plan | `core.planner` | EDL + template + preset → `edit/render_plan.json` (ffmpeg filter graph description) |
| execute | `rendering.ffmpeg` | render_plan → `renders/v*.mp4` |
| qc | `qc/*` | render → `qc/QC_REPORT.json` (pass/fail + metrics) |
| fix | `core.orchestrator` retry loop | QC failures → adjusted plan, max N retries |

The **Orchestrator** (`core/orchestrator/`) owns stage ordering, caching, logging, and the retry budget. It never hard-codes edit taste — thresholds live in template/preset config.

## 3. Repository layout (implemented in Phase 1)

```
project/
├── engine/                 # importable Python package (the brain)
│   ├── __init__.py
│   ├── cli.py              # `video-engine` entry (click)
│   ├── core/
│   │   ├── config.py       # layered config: defaults < template < preset < CLI flags
│   │   ├── logging_utils.py
│   │   ├── media.py        # ffprobe wrapper (inspect)
│   │   ├── models.py       # pydantic project schema (Project/Media/Transcript/EDL/QC)
│   │   ├── orchestrator.py # staged runner + retry budget
│   │   ├── pipeline.py     # stage registry + cache (sha256 of inputs)
│   │   └── project_store.py# projects/<id>/ layout read/write
│   ├── analysis/           # (stubs → real in Phases 5-7)
│   ├── editing/            # edit-decision engine (Phase 8)
│   ├── audio/              # cleanup/mix (Phase 9)
│   ├── subtitles/          # srt/ass/vtt writers (Phase 10)
│   ├── graphics/           # Remotion bridge (Phase 11)
│   ├── rendering/          # ffmpeg builder + encoder probe (Phases 4,12)
│   ├── qc/                 # checks + report (Phase 13)
│   └── templates/          # built-in template/preset registry (Phase 14)
├── templates/              # user-visible template packs (youtube/shorts/…)
├── assets/                 # local B-roll / music / sfx library (+ .gitkeep)
├── scripts/                # make_test_media.py (synthetic lavfi generator)
├── tests/                  # pytest: unit + integration + real-media (synthetic)
├── docs/                   # PIPELINE.md, DEVELOPMENT.md, TROUBLESHOOTING.md
├── input/ output/ projects/
├── requirements.txt        # pinned Python deps
├── setup.ps1               # idempotent Windows installer
├── README.md  DEPENDENCIES.md  SYSTEM_AUDIT.md  ARCHITECTURE.md
```

Why `engine/` and not `core/` at top level: avoids collision with the spec's `core/` concept while keeping imports clean (`from engine.core.models import …`). The on-disk Ori structure from the brief maps 1:1 inside `engine/`.

## 4. Internal representation (JSON-first, stdlib dataclasses)

`engine/core/models.py` defines (v0.3, Phase 3):

- `Project`: id, created_at, versions, input, template, preset, stages{}
- `MediaInfo`: duration, resolution, fps, codec, bitrate, audio channels/rate + `audio_streams[]` per-stream detail (Phase 3, additive)
- `Segment{start,end,label,score}` — generic span for silence/scene/speech/cuts
- `SilenceInterval{start,end,duration}` — required audio timestamp schema (Phase 3)
- `AudioAnalysis`: presence, streams, volumes, loudness, silence[], non_silent[] (Phase 3)
- `TranscriptWord{word,start,end,probability}`, `WhisperSegment{id,text,start,end,duration,words[]}`, `Transcript` (Phase 5/6; generic `Word`/`TranscriptSegment` stay as future-phase placeholders, unified in Phase 8/10)
- `Scene{scene_id,start,end,duration,start_frame,end_frame}`, `SceneDetectionResult` (Phase 7; full-precision seconds, probe fps/duration as timeline truth)
- `EditDecision{decision_id,start,end,action,reason,confidence,scene_id,word_refs,metadata}`, `EditDecisionList` (Phase 8; source coordinates, KEEP/REMOVE only; supersedes the unused Phase 1 keep/remove-list placeholder)
- `RenderConfig`, `ExecutionPlan{source,edl_hash,segments[]+output offsets}`, render manifest (Phase 9; renderer executes, never decides; gateway-only FFmpeg)
- `Evidence` (8 mandatory fields), `SceneSpeechMetrics`, `PacingMetrics`, `RepetitionCandidate`, `JumpCutCandidate`, `CutSafety{SAFE|CAUTION|UNSAFE}`, `IntelligenceReport` (Phase 10; measurements + conservative refinement, no rendering)
- `VisualFrame`, `FaceDetection` (geometry only, no identity/attributes), `ObjectDetection`, `SceneVisualSummary`, `VisualAnalysisResult` (Phase 11; capabilities honestly reported, heuristics labeled)
- `StyleProfile` (11 styles), `HookAssessment`, `StorySegment`, `DensityWindow`, `CutCandidate`, `BrollOpportunity`, `VisualChange`, `AudioRecommendation`, `EditorialRepetition`, `QualityRisk`, `ConflictResolution`, `ProfessionalEditPlan` (Phase 12; decision layer above analyses, planning only)
- `BrollAsset` (local-only), `PlanApproval` (immutable snapshot), `ExecutionOp` (source+output coords, layers), `ExecutionPlanModel` (reconstructible timeline) (Phase 13; approval boundary + execution, gateway-only FFmpeg)
- `CaptionWord`, `CaptionCue` (metrics + warnings), `CaptionPlan` (deterministic JSON source of truth) (Phase 14; transcript never rewritten, timing never invented)
- `CaptionVisualContext`, `CaptionPlacement` (anchor derived from position), `CaptionEmphasis` (transcript-timed), `VisualCaptionPlan` (Phase 15; measurements + approved deltas only, no animation)
- `CaptionPacingContext`, `PacingSignal` (15 types), `PacingRecommendation` (8 actions), `CaptionPacingPlan` (Phase 16; deterministic pacing intelligence, plan only, no rendering)
- `PacingExecutionApproval` (APPROVED/EXECUTED states, RECOMMENDED/INVALID reserved), `PacingExecutionOp` (TRIM/SPLIT executable, rest NOOP metadata), `PacingExecutionPlan` (derived EDL + mapping previews + execution hash) (Phase 17; approval-gated execution through the Phase 13 engine, no new gateway)
- `TranscriptSegment{text,start,end,words[]}` + `Word{w,start,end,conf}`
- `EditDecision`: `keep[]`, `remove[]`, reason codes (`silence`, `filler`, `repeat`, `low_value`…)
- `RenderPlan`: ffmpeg inputs, `-vf/-af` chains, encoder choice + reason, output preset
- `QCReport`: checks[{name, passed, detail}], verdict, suggested_fix

Every object serializes to JSON under `projects/<id>/…` so any stage can be inspected/debugged by hand.

## 5. Caching

`engine/core/pipeline.py`: `cache_key = sha256(file_bytes_sample + mtime + size + stage + config_hash)`.
Analysis artifacts live in `projects/<id>/analysis/` and global `.cache/` keyed identically — same file never analyzed twice.

## 6. Config layering

`defaults.yaml (in code) < templates/<name>.json < presets/<name>.json < CLI flags`.
`core/config.py` merges and validates; orchestrator logs the resolved config per run.

## 7. Logging

One JSONL log per run: `projects/<id>/logs/<timestamp>.jsonl` with `{ts, stage, op, duration_s, status, output, versions{ffmpeg, python, engine}}`. Human-readable summary via `video-engine status <id>`.

## 8. Encoder selection (this hardware)

Probe order at render time: `h264_nvenc` (if `ffmpeg -encoders` lists it AND runtime smoke-encode succeeds) → `h264_qsv` → `h264_amf` → `libx264`. Rationale: 940MX NVENC is weak but worth trying; QSV on HD 630 is the reliable HW path; libx264 is the guaranteed fallback. HEVC output is CPU-only on this box (no GM108 HEVC encode). Phase 4 verifies each candidate with a real 1 s smoke encode (listed ≠ working) and caches the result in `.cache/encoders.json`.

## 9. What is deliberately deferred (and why)

| Capability | Phase | Reason |
|---|---|---|
| faster-whisper STT | 6 | needs Python+FFmpeg first |
| PySceneDetect/OpenCV | 7 | same |
| Remotion animated captions | 11 | Node present but renderer unused until subtitle data model exists |
| Blender/Kdenlive/MLT | — | evaluated, **rejected** for v1: heavyweight, poor CLI-automation fit; FFmpeg+Remotion covers the brief |

## 10. Change policy

Major architectural changes require a dated note in `docs/DECISIONS.md` (created Phase 1) explaining reason + alternatives considered.
