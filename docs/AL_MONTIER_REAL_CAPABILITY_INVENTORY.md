# AL-MONTIER REAL CAPABILITY INVENTORY — Forensic Audit (2026-09-25)

**Mode:** AUDIT ONLY. Read-only. No code modified, nothing installed/downloaded/deleted, no config changed, no full production run, no VoiceTut retry, no Arsenal changes, no new features.
**Question answered:** "Exactly what tools and capabilities are REALLY WORKING in Al-Montier right now?"
**Machine:** i7-7820HQ 4C/8T · 16 GB · Intel HD 630 (QSV) + GTX 940MX 2 GB (Maxwell GM108, weak) · Windows 10 Pro 22H2 · `C:\Users\NOUR SOFT\Documents\Default Project`
**Repo scale (directly verified today):** 72 `engine/**/*.py` · 43 `test_*.py` · 76 `docs/*.md` · 3617 `projects/*/` dirs · 1163 `*.mp4` under projects · 950 `.cache` files · `output/` = `.gitkeep` only.
**Key timeline note:** docs dated 2026-09-24 (FORENSIC/MOTION_FORENSICS/GAP_MATRIX) correctly state "renderer has no overlay op" **for that date**. 2026-09-25 proof reports (OVERLAY_ICON_PIPELINE 13/13, GRAPHICS_COMPOSITION 16/16, PLANNER_3_1_RENDER_INTEGRATION) supersede them with `overlay_asset` + `compose_shot` + `camera_push` manifests verified on disk today.

Status vocabulary (never conflated): implemented ≠ tested ≠ smoke-proven ≠ production-proven ≠ available-but-not-connected ≠ planned ≠ blocked ≠ placeholder/mock ≠ unavailable.

---

## 1. ENGINE / CORE

| Module/path | Purpose | Status | Public API | Executable? | Test evidence | Production evidence | Limitations | Deps |
|---|---|---|---|---|---|---|---|---|
| `engine/core/media.py` | ffprobe inspect wrapper | PRODUCTION_READY | `probe()` via `analyze` CLI | YES | unit + e2e fixture | every project `analysis/media_info.json` | trusts ffprobe; VFR nominal fps bogus (fixed downstream) | ffprobe 9.0.1 |
| `engine/core/project_store.py` | projects/<id>/ layout read/write | PRODUCTION_READY | `create/load_project, write_artifact, mark_stage` | YES | scaffold tests | 3617 project dirs | none material | stdlib |
| `engine/core/pipeline.py` | stage registry + content-hash cache | PRODUCTION_READY_WITH_LIMITATIONS | `cache_key/cached/store` | YES | cache-hit test (sample_10s) | 950 `.cache` files; overnight rerun reuse | analysis/manifest cache only, NOT segment video cache | stdlib sha256 |
| `engine/core/config.py` | layered config defaults<template<preset<CLI | PRODUCTION_READY | config merge/validate | YES | unit | orchestrator logs resolved config | none material | stdlib/yaml-in-code |
| `engine/core/orchestrator.py` | stage ordering + retry budget | PRODUCTION_READY | staged runner | YES | integration | micro-runs + named productions | retry is planning-level, render retry = full re-render | all stages |
| `engine/core/logging_utils.py` | JSONL per-run log | PRODUCTION_READY | `log_event` | YES | unit | `projects/*/logs/*.jsonl` | none | stdlib |
| `engine/core/models.py` | typed schemas (MediaInfo…PacingExecutionPlan) | PRODUCTION_READY | dataclasses | YES (import) | schema tests | every JSON artifact | Phase-1 keep/remove placeholder superseded by EDL | pydantic v2 |
| `engine/cli.py` (22 commands) | thin CLI over library | PRODUCTION_READY | `analyze, transcribe, download-model, scenes, edit, edit-analyze, render, visual, editor-plan, approve-plan, render-plan, captions, approve-captions, caption-visual, approve-caption-visual, caption-pacing, approve-caption-pacing, approve-caption-pacing-execution, execute-caption-pacing, status, doctor` (`qc` = NOT IMPLEMENTED stub) | YES | 43 test files reference CLI fns | named productions driven via scripts calling same fns | `qc` stub; spaced-path rule (`NOUR SOFT`) requires arg-lists | click+rich |
| `engine/rendering/ffmpeg.py` (960 lines, SOLE gateway) | all ffmpeg builds: trim/concat/keep/extract_audio/extract_frame/apply_vf/mix/gain/fade/burn/validate + encoder probe | PRODUCTION_READY_WITH_LIMITATIONS | `run_ffmpeg/trim/concat/render_keep/mix_audio/burn_subtitles/validate_output/overlay_asset` | YES | 15+ render tests; encoder smoke test | all renders + overlay/graphics proofs | NO xfade/lut3d defs; NO keyframed animation; overlay added 09-25 only (static, ≤2 layers) | ffmpeg 9.0.1 |
| `engine/rendering/execution.py` | EDL→master+manifest (executes, never invents) | PRODUCTION_READY | EDL execution | YES | Phase-9/17 e2e | editorial renders 21–28 MB | full re-encode only | ffmpeg |
| `engine/rendering/plan_execute.py` | approved-plan→timeline→single-concat render, dry-run | PRODUCTION_READY | plan execution | YES | plan tests | bench_integrated 79.14 s | cover-fit uniform (known workaround history) | ffmpeg |
| `engine/editing/decisions.py` | ANALYSIS→EDL pure timeline math (filler + long-silence, 2 rules) | PRODUCTION_READY_WITH_LIMITATIONS | EDL build | YES | Phase-8 tests | EDLs in projects (keep-all in E2E) | conservative; only 2 removal rules | analysis JSON |
| `engine/editing/*` (intelligence/brain/approval/punch/visual_execution/caption_pacing*) | safety/density/pacing/repetition/jump-cut; style plans; immutable approvals; TRIM/SPLIT pacing ops | PRODUCTION_READY_WITH_LIMITATIONS | `edit-analyze, editor-plan, approve-*, caption-pacing, execute-caption-pacing` | YES | 140→296-test chain claims | intelligence reports + pacing-derived EDLs | planning mostly; execution via Phase-13 engine only | OpenCV/faster-whisper |
| `engine/tools/assemble.py` | `render_shot/resolve_transform/detect_mismatch`, zoompan-vf builder | PRODUCTION_READY_WITH_LIMITATIONS | per-shot manifest `{requested,effective_source,op,params,result}` | YES | 15/15 planner-render tests | bench_integrated 20 shots 0 mismatches | 4 ops only (cover/zoompan/zoompan-x/zoompan-y/crop); else CAPABILITY_MISSING | ffmpeg |
| `engine/tools/adapters/providers.py` | PiperAdapter / WhisperAdapter / FFmpegAdapter incl. `camera_push` | PRODUCTION_READY_WITH_LIMITATIONS | adapter `run()` | YES (piper+whisper+ffmpeg) | `test_tool_adapters.py` | narration WAVs + STT + proofs | Piper hard-pinned paths; camera_push partial planner use | piper exe/onnx, whisper |
| `engine/audio/` , `engine/qc/` | placeholders | PLACEHOLDER | none | NO | none | none | real logic lives in `rendering/ffmpeg.py`, `tools/audio_director.py`, `review/` | — |

## 2. VIDEO INGEST / ANALYSIS

| Capability | Verdict | Evidence |
|---|---|---|
| probing / duration / FPS / resolution / codec / audio-stream detection | REAL (production-proven) | `media.py` + every `media_info.json`; ffprobe 9.0.1 verified today |
| VFR handling (detect + CFR proxy + frame-exact trim) | REAL (production-proven, with limits) | VFR_PHONE_VIDEO_FIX_REPORT: offset 0.72→0.05 s; `vfr_status/normalize_media`, project-temp proxy only |
| scene detection (PySceneDetect content/threshold + ffmpeg fallback, fallback recorded) | REAL | `scenes` CLI; scenedetect 0.7.1 doc-claim; zero-cuts = single scene |
| silence detection (silencedetect + volumes + loudness) | REAL | `analysis/audio.py` 3-pass measure; EDL silence rule |
| speech detection (webrtcvad) | REAL (lib present) | requirements `webrtcvad-wheels`; used in analysis chain |
| frame extraction | REAL | `extract_frame`; px_before/inside/after PNGs in overlay + graphics proofs |
| visual analysis (OpenCV deterministic sampling + metrics) | REAL WITH LIMITS | `visual` CLI; adapters report available/unavailable honestly |
| face/subject analysis | NOT REAL on this box | adapters return UNAVAILABLE; geometry-only, no identity; no models downloaded |
| source normalization | REAL (VFR proxy) | see VFR row; no full transcode library |

## 3. AUDIO

| Capability | Verdict | Evidence |
|---|---|---|
| narration (Arabic) | REAL WITH LIMITS — exactly 1 producible voice (Piper Kareem, MSA/Jordanian, NOT Egyptian) | hook_second 69.24 s narration; blind_social aug WAVs; narr WAVs in seconds |
| TTS Piper/KAREEM | PRODUCTION_READY_WITH_LIMITATIONS | `tools/tts/piper/piper/piper.exe` (0.49 MB) + `ar_JO-kareem-medium.onnx` (60.27 MB) + espeak-ng-data verified on disk; 22050 Hz; RTF 0.17–0.22 CPU; offline OK; license NEEDS VERIFICATION; NOT Egyptian (ج→g/ق→ʔ missing) |
| TTS MOHAMED/VOICETUT | BLOCKED | HF Space `run_b_oneshot` → `error/data:null` ×3 (`audition_log.json`); no WAV ever produced; local install hardware-gated (needs >2 GB VRAM); rights UNKNOWN; NOT retried per task |
| TTS CHATTERBOX-EG | AVAILABLE_BUT_NOT_CONNECTED | `tools/tts/chatterbox-eg/` + own `.venv` + `cb_test.py` on disk; bounded test RTF **37.6** (~38 min per 60 s narration); quality/rights unconfirmed; NO engine adapter; never used in production |
| TTS Sayed reference | PLACEHOLDER (1 WAV, not a TTS) | `wavs/voicetut_Sayed.wav` 16.53 s youthful, rights unknown; audition refs Aly/Kamal/Mohamed/Omar/Zaki are harvested clips, not engines |
| SAPI | AVAILABLE (test-fixture only, en-US) | David/Zira en-only; used to synthesize `speech_sapi.wav` fixtures; NOT a production narration path |
| espeak/coqui/xtts/torch TTS | UNAVAILABLE | zero pip entries (`torch/coqui/piper-tts` absent from freeze); espeak only as Piper `--espeak_data` dep (GPL boundary) |
| STT Whisper (en, tiny, cpu/int8) | PRODUCTION_READY | faster-whisper 1.2.1 + `models--Systran--faster-whisper-tiny` cached; E2E en p=0.994, 2 seg/20 words |
| STT Arabic + word timing | IMPLEMENTED_BUT_NOT_PRODUCTION_PROVEN | code supports (filler list AR 11 tokens; spans full/non_silent); no Arabic production transcript proven in a master |
| silence removal (EDL TRIM) / gain / fade / mix / mux / AAC-PCM | REAL | ffmpeg gateway; Aitech bed + fades in masters; −19.2 LUFS measured |
| loudness measure (volumedetect/loudnorm-JSON) | REAL | `analysis/audio.py`; pyloudnorm 0.2.0 installed |
| loudnorm execution / beat-snapping | IMPLEMENTED_BUT_NOT_PRODUCTION_PROVEN | smoke-proven 09-24, unused in hook_second (forensic R6) |
| ducking / EQ / compressor / de-ess | NOT IMPLEMENTED (planned) | no defs; correctly absent from docs as built |
| music (Incompetech CC-BY bed) | REAL WITH LIMITS | path-only hardcoded use; 0/1441 tracks searched; attribution required on publication |
| SFX (4 kinds: sting resolves, 3 fileless) | REAL WITH LIMITS (1/4) | sting sample ×3 in master; shelf genuinely empty (0 WAVs, incomplete zips) |
| audio QC + A/V sync check/fix | REAL | offset/loudness/silence checks; VFR apad-tail fix |

## 4. CAPTIONS / TEXT — all REAL except karaoke

Planning (`captions.py`, transcript-is-truth, words never rewritten) → formats (SRT/VTT/ASS, 5 styles, karaoke explicitly NOT modeled = REJECTED) → approval → execution (`render.py`: sidecar file-I/O + burned-in single ASS pass via libass) → polish (`visual_captions`: placement/emphasis, faces UNAVAILABLE honestly) → kinetic (`kinetic_captions.py`: ≤8-word chunks, `\kf` per-word from STT only) → pacing (15 signal types, 8 actions, plan-only + approval-gated TRIM/SPLIT execution). Proven: E2E 3 cues QC-pass; from-scratch 36 body + 6 keyword + cards burned, RTL verified on 8 frames, no tofu; hook 50 cues burned. Fonts: local-only discovery (`fonts.py`, KNOWN_ARABIC_FONTS, lists `C:\Windows\Fonts`), Arial default; U+FFFD scrubbed; `has_rtl()` detection. Limits: Latin-only labels in graphics proofs; no animation beyond ASS tags; caption-visual calibrated QC only.

## 5. MOTION SYSTEM

| Capability | Implemented? | Executed in real media? | Planner connected? | Renderer connected? |
|---|---|---|---|---|
| ASS fade/rise/slide_in/emphasis/dialogue (captions) | YES (`creative/motion.py`) | YES (50 cues) | YES (grammar roles) | YES (libass burn) |
| camera push/pull/pan/tilt (zoompan) | YES (adapter + `assemble._zoompan_vf`) | YES (smoke + overlay/graphics/bench proofs) | PARTIAL (maps roles; hook_second stored HOLD×8 strings, never called) | YES (`camera_push` op) |
| punch reframes (static crop) | YES | YES (narrated_tech, benchmark) | recipe-dependent | YES |
| hard cuts, beat-snapped cuts | YES (cuts) / smoke-only (beat-snap) | YES (20 cuts; beat-snap unused in master) | YES (cuts) | YES (trim/concat) |
| static icon/label overlays | YES (09-25) | YES (2 proofs w/ differentials) | YES (`propose_shot_graphics`) | YES (`overlay_asset`+`compose_shot`) |
| xfade/dissolve/wipe | NO (binary HAS `xfade`, engine has NO op) | NO | NO ("fade" = ASS/string only) | NO |
| keyframes / easing engine / springs / particles / glitch / parallax / tracking / speed-ramps / whip-pans / match-cuts / stabilization-exec | NO (19 primitives → structured `CAPABILITY_MISSING`; `easing` is a param name only) | NO | NO | NO |
| Lottie / GSAP / Remotion / Manim runtime | NO (TIER-2 contracts; Remotion license-blocked) | NO | NO | NO |

Motion grammar (roles, reasons, combo warnings) is real as text; execution is limited to the 4 `assemble` ops + ASS + crop.

## 6. GRAPHICS / COMPOSITING — pixel-proven set (with limits)

Proven on disk (manifests + PNGs + MP4s read today): Lucide `eye.svg` → tag search → Chrome raster → `overlay_asset` → `overlay_proof_20260925_031640.mp4` (6 s 1080×1920@30; inside-box Δ 23217 px vs ≤174 outside; 2 runs byte-identical); `compose_shot` layered icon+label+`camera_push` 1.0→1.08 → `graphics_layer_20260925_032528.mp4` (icon Δ 17860, label Δ 20435, gold 2607 px; 14/14 tests); Pillow "87% FASTER" card frame-verified (smoke); svgwrite `stat.svg` valid sidecar; 3 navy `color_clip` cards in hook master. Gateway supports opacity/position/scale/layer/z-order per-shot but position/size fixed per op, ≤2 layers verified, static only, Latin-only, Chrome-dependent, no segment cache. Explicitly raising (never silent): `stat_card/callout/headline/svg_graphic` as composited types. Phosphor/tabler + flat `svg/` dir, Fabric/ECharts/Vega/Mermaid/three-TIER2: contract only.

## 7. ARSENAL INTEGRATION (`F:\Arsenal` AVAILABLE, 33 top entries, verified today)

| Asset class | Arsenal reality | Discoverable? | Semantic search? | Planner access? | Director access? | Renderer access? | Used in production? |
|---|---|---|---|---|---|---|---|
| video (05_VideoAssets: Blender/NASA/Stock-Footage; MH بصري) | files present | MANUAL PATH ONLY (MH catalog-invisible) | NO (manual tags) | BROLL kind only | recipe files-on-disk | trim/concat/cover | YES (18 B-roll clips) |
| music (04_Music: Incompetech + LICENSE.txt; موسيقى/) | ~1441 tracks claimed | PATH ONLY | NO (0 searched) | gain-state decisions | bed intent | mux/fade | YES (Aitech bed ×masters) |
| SFX (03_SFX: GDC2019/2024; مؤثرات صوتية/) | SHORTAGE (0 WAVs usable, incomplete zips) | NO | NO | 4-kind rules | sting intent | mux | PARTIAL (sting ×3 only) |
| icons (02_Icons: lucide full checkout + phosphor + tabler; svg/ 63 files) | present | LUCIDE ONLY (tag-score + sha pin) | NO (token match) | YES (propose_shot_graphics) | YES | YES (overlay, 09-25) | proofs ONLY (not feature masters) |
| SVG flat / Lottie (lottie/ 17 .lottie + 10_MotionDesign/lottie-library/ 154 JSON + lottie-mega) | present | NO (no index/search/kind/path) | NO | NO | NO | NO | NO |
| fonts (01_Fonts, Fonts-Organized, Google Fonts, 1-خطوط; catalog.json 164k lines) | cataloged | cataloged BUT UNUSED (Arial default; fontconfig path unvalidated) | NO | CAPTION_FONT kind | YES (intent) | libass | YES (default only) |
| LUT (08_3D_Assets/LUTs-Film: 9 cats; colorslide/ 26 .cube e.g. kodak_kodachrome_64.cube; LUTs-Camera/sony) | present | NO | NO | NO | NO | NO | NO |
| motion assets (10_MotionDesign 16 entries: textures, blender-demos, codrops, gltf-assets, threejs, meteocons…) | present (~5000 files claimed) | NO | NO | NO | NO | NO | NO |
| 3D (marble_01_4k.blend single .blend + ambientCG/PolyHaven-HDRI/textures + خامات 3D dirs) | present | NO | NO | NO | NO | NO | NO |
| models (07_AI_Models) / templates (06_Templates = HTML5UP/tailwind/meraki/GitClones web-only) | present | NO / correctly unused | NO | NO | NO | NO | NO |

"Available in Arsenal" ≠ "usable by Al-Montier". Only Lucide-icons (+proofs), B-roll-by-path, music-by-path, default fonts are connected.

## 8. LUT / COLOR

`lut3d` EXISTS in the ffmpeg binary (verified `ffmpeg -filters` today) but has NO engine op, NO planner kind, NO search, NO render, NO pixel diff. `OcioAdapter` is a numpy exposure-gain demo on inline pixels, not a `.cube` reader. Style contract + color_clip cards + cover-fit exist; color consistency is manual. **LUT execution: UNPROVEN / NOT CONNECTED.**

## 9. 3D / ADVANCED VISUALS

Files only: 1 `.blend`, HDRI/texture sets, three.js full checkout in Arsenal. No Blender binary (Get-Command negative), no adapter `run()`, registry TIER-3 `needs_download`, `orbit` → `THREE_D` missing. No depth/particles/shaders/GPU-visual path. **3D assets: AVAILABLE_BUT_NOT_CONNECTED. 3D rendering: BLOCKED. Zero 3D renders.**

## 10. STORY / CREATIVE DIRECTOR — DECIDES ONLY (never executes)

`autonomy/director.py plan_production` + `tools/visual_director.py` (pure/deterministic): concept→beats→hook→arc (4- vs 7-state by duration)→metaphor (15 cats)→shot/asset/motion/camera/typography/SFX/music/transition intents→diversity/callbacks/escalation/ending. Voice-first + text-driven modes; ≥2 shots/scene + hook ≥3 in 5 s; headline ≤8 words; 5 music gain states; foreign-UI veto + 720p floor. Only `BROLL + CAPTION_FONT` requirement kinds reach the renderer; motion/camera/typography reach only via narrow grammar→assemble path (fixed 09-25). Duration budget is assert-only (hook 79.06 s: 69.24 narration + 1.5 + 4.5 + 3.6 + 0.21; <60 s needs cutting ≥3 lines — never enforced).

## 11. PLANNER 3.1

Decision types: beat needs, asset keep/swap (relative-floor ranking, logged reasons), repetition-budget (9 types + INTENTIONAL_CALLBACK, size-scaled, recency-windowed), hook-montage split, motion select + camera select (story-first, composition-aware, combo warnings), rhythm/relations/escalation advice, `validate_creative_plan` PASS/WARNING/FAIL + `repair_plan`, determinism (PLAN_DETERMINISTIC + RENDER_DETERMINISTIC, frame hashes c1d5/9587/322e match A/B). Audit→fix arc: bench audit found 3 loss points (timeline kept kind/file/span/label only; invented src_off; no zoompan) → fixed via `plan_shots_diverse + attach_motion_camera` (`{type,parameters,reason,source:"planner"}`) + `render_shot` + per-shot manifest + mismatch detection. Bench `bench_integrated_20260925_022619.mp4` 79.14 s, 20 shots, 0 mismatches, 15/15 tests.
Trace (planner→renderer→pixels): MOTION `camera_push` → `assemble` zoompan → `graphics_layer ...032528.mp4` work `base_r*_push.mp4` + icon/label differentials; CAMERA cover/push → same; ASSET Lucide `eye.svg` (sha-pinned) → Chrome raster `eye_300.png` → overlay MP4 (23217-px inside Δ); GRAPHICS label chip → `compose_shot` → `comp_r2.mp4` (20435-px Δ). Residual: 2–4× asset reuse (R2 REVIEW), 1 pre-render hook repair.

## 12. DIRECTOR — rules list (ALL: DECIDES, never EXECUTES)

Visual grammar, 15-cat metaphor engine, shot planner (per-sentence idea/intent/emotion/info_type), motion grammar (vocab refs), typography rules (claims/diagrams/abstractions), audio states (5 gain), composition rules (cover, ≤2 layers, box-overlap), style contract, quality model hooks, repair routes (WEAK_MOTION→vocab, TEXT_OVERLOAD, ASSET_REPETITION…). Execution belongs to `assemble.render_shot` + ffmpeg. Forensic R6 stands for feature masters (proven capabilities unused 09-24/25); proofs + bench show the wired path works when requested.

## 13. REVIEW / QC — what each reviewer ACTUALLY verifies (recomputed, never trusts manifests)

`review/reviewer.py` (Phase-25 independent: output exists/non-empty, EDL order, caption overlap/intervals/empty/readspeed, approvals + fingerprint match, pacing bindings, A/V offset, loudness mean/peak, silence ≥1 s, black-frame intentional-only, frame sampling hook/captions/layers/tofu/foreign-UI, hook/pacing/dupe, ending tail+endcard; ffprobe-absent → UNKNOWN never PASS); `creative/review.py` (hook ≥3 shots <5 s + question, density/ending/repetition/quality/relevance/motion/audio); `tools/reviewer2.py` (shot-level hook/pacing/text/motion/dupes, audio, ending — killed scene-bin artifact); `tools/visual_review.py` + `quality_score.py` (20 criteria, no aggregate). Proven: E2E QC pass; VFR 4 REVIEW_AGAIN zero FAIL; Planner-3.1 zero post-render rounds; proofs 13/13 + 16/16 + determinism hashes; 30 viewed frames (forensics) + 8 frame gates (stress test).

## 14. REPAIR SYSTEM (planning-only; FULL RERENDER only)

| Trigger | Action | Scope | Cache | Verify | Retry limit |
|---|---|---|---|---|---|
| FAIL (QC/reviewer) | REPLAN via route table (captions/editing/visual/audio/technical/provenance/BAD_ASSET/WEAK_SHOT_SEQUENCE/STATIC_PACING/…) | FULL re-render (all segments re-encoded; 315 s/run; 42 segs ×3 in forensics) | analysis/manifest reuse only | reviewer recompute | MAX 2 → BLOCKED_REQUIRES_HUMAN_REVIEW |
| REVIEW (incl. v2 MOTION_TOO_STATIC/TEXT_OVERLOAD/ASSET_REPETITION) | REVIEW_AGAIN routed to subsystem | same (or NO render if unwarranted: VFR 4 REVIEW_AGAIN → 0 re-renders) | same | same | same |
| pre-render planner flag | hook-montage split etc. | plan patch, single render | same | determinism hashes | — |

NO segment-rerender executor exists. `CAPABILITY_MISSING` raised, never substituted; `EXECUTION_MISMATCH` on param drift.

## 15. CACHE / PERFORMANCE

Content-hash JSON cache (stage+config+size+mtime+first-MB → `.cache/*.json`), source fingerprint (size+mtime+sample), plan hash, pacing-approval hash, raster cache (sha PNGs), encoder cache (`.cache/encoders.json`). Reuse proven: overnight "cache never worked before" fix + rerun reuse + tamper invalidation; VFR manifest fix; planner byte-identical double render. NOT cached: video segments (identical B-roll re-encoded 3× across masters + burn). Cost anatomy (hook 79.06 s ≈ 50 min wall): ~13 min re-encodes + ~12 min from-scratch indexing (MH unindexed) + ~10 min manual frame review (found all 4 defects) + ~10 min crash-fix ×4 + ~5 min STT/QC + ~5 min reports; TTS/STT <1 min. Smoke-render times: overlay proof 6 s in seconds; bench 79 s in ~5 min/run order.

## 16. TOOLS / EXTERNAL BINARIES (directly verified today unless noted)

| Binary | Installed? | Version | Path | Healthy? | Used by production? | Used by tests? |
|---|---|---|---|---|---|---|
| FFmpeg | YES | 9.0.1-full_build-www.gyan.dev (GPL static, libx264/x265/ass/nvenc/qsv, whisper) | WinGet Gyan package `…\ffmpeg-9.0.1-full_build\bin\ffmpeg.exe` | YES | YES (all renders) | YES |
| FFprobe | YES | 9.0.1-full_build | same package `ffprobe.exe` | YES | YES (probe/QC) | YES |
| Python (.venv) | YES | 3.11.9 | `.venv\Scripts\python.exe` | YES | YES | YES |
| system python | NO (Store shim) | — | — | NO | NO | NO |
| Node | YES | v24.14.1 | `D:\node.js\node.exe` | YES | NO (Remotion unused) | NO |
| Git | YES | 2.53.0.windows.2 | `D:\Git\cmd\git.exe` | YES | NO | NO |
| faster-whisper (+tiny) | YES (pip 1.2.1 + HF hub cached) | 1.2.1 / tiny | `.venv` + HF hub `models--Systran--faster-whisper-tiny` | YES (cpu/int8) | YES (E2E STT) | YES |
| Piper (+Kareem) | YES (vendored exe, not pip) | 2023.11.14-2 + ar_JO-kareem-medium 60 MB | `tools/tts/piper/…` | YES | YES (narration) | YES (adapter probe) |
| onnxruntime/librosa/pyloudnorm/mediapipe/rembg/rapidocr/… | YES (pip) | 1.30.0 / 0.11.0 / 0.2.0 / 1.0.1 / 2.0.85 / 1.4.4 … | `.venv` | YES | partial (measure/adapter) | YES |
| torch/coqui/xtts/piper-tts (pip) | NO | — | — | — | NO | NO |
| Chrome | FILE EXISTS, NOT IN PATH | — | `C:\Program Files\Google\Chrome\Application\chrome.exe` | used by raster | YES (icon raster dep) | YES |
| ImageMagick / Blender / SoX | NOT FOUND | — | — | — | NO | NO |

## 17. HARDWARE (SYSTEM_AUDIT 2026-09-16 + live re-query today)

CPU `Intel i7-7820HQ @ 2.90 GHz, 4C/8T` confirmed; GPUs `Intel HD 630` + `NVIDIA 940MX` confirmed; RAM 16 GB (15.88 visible, ~7.6 free at audit); disks C:111/187, D:361, E:195, F:200 GB free (audit-time). Constraints: CPU is workhorse; 1080p-first (4K flagged slow); sequential/chunked, never full video in RAM; encoder order `h264_nvenc → h264_qsv → libx264` with runtime smoke-verify (auto-selects `h264_qsv` here); HEVC output CPU-only (no GM108 HEVC encode); CUDA CC 5.0 2 GB → PyTorch-CUDA rejected, CPU inference default; every accel path needs CPU fallback. No CUDA-install proposal (per task).

## 18. LICENSE / PROVENANCE

Code MIT/Apache/HPND/ISC/BSD clean; FFmpeg Gyan invoked as subprocess (GPL boundary, never linked); espeak-ng present via Piper. Models: Whisper tiny MIT OK; Piper Kareem NEEDS VERIFICATION; rembg/MediaPipe/RapidOCR per-model verify. Voices: NO TTS voice cleared for commercial use (Kareem unverified; Mohamed rights UNKNOWN; Sayed UNKNOWN; Chatterbox unconfirmed). Music Incompetech CC-BY (attribute Kevin MacLeod on publication). B-roll Pexels/MH provenance UNKNOWN (use under caution). Deliberately kept out: pedalboard/aubio (GPL-3), Essentia/Aeneas (AGPL), Coqui XTTS (CPML), Fish/SAM/F5 (NC), YOLO (AGPL), Remotion (company-license gate). Full matrix: `docs/PRODUCTION_LICENSE_AUDIT.md`.

## 19. REAL PRODUCTION EVIDENCE (tests ≠ proof; only rendered media)

| CAPABILITY | PROJECT | PROOF | PIXEL VERIFIED? | REVIEW VERIFIED? | STATUS |
|---|---|---|---|---|---|
| ffprobe inspect + media_info | all (3617 dirs) | `analysis/media_info.json` per project | N/A (data) | reviewer fingerprint | PROVEN |
| silence/volumes/loudness measure | all | `audio_analysis.json` | N/A | QC loudness/silence | PROVEN |
| Whisper tiny STT en + word timing | project_20260920_112442_203839 (E2E) | 2 seg/20 words p=0.994 → 3 cues → 8.83 s `plan_20260920_143014.mp4` h264_qsv QC pass | frames sampled | reviewer recompute | PROVEN |
| EDL TRIM/concat render + manifest | Phase-17 chain; editorial re-renders 21–28 MB | `renders/*.mp4` + manifests; reuse on identical work | A/V sync checked | QC pass | PROVEN |
| Piper Kareem narration (MSA) | hook_second_v1_20260924; blind_social; narrated_tech | 69.24 s narration; aug/beat WAVs; masters 15–20 MB | lip-sync N/A (B-roll) | audio review | PROVEN (non-Egyptian) |
| Arabic ASS captions burned + RTL, no tofu | from_scratch_ai_video_20260920_210038; hook_second | 36 body + 6 keyword + cards; 50 cues; 8-frame RTL check | YES (frames) | caption QC | PROVEN |
| hard cuts + cover reframes + music bed + sting | hook_second `hook_second_20260925_021538.mp4` 20.44 MB 79.06 s | 18 B-roll + 3 navy cards + Aitech bed + sting ×3 | YES (30 frames) | R2 + forensic | PROVEN |
| planner→renderer determinism (20 shots, 0 mismatches) | bench_integrated `..._022619.mp4` 18.52 MB 79.14 s (+022007/023255 determinism pair) | per-shot manifest; frame hashes match A/B | YES (hashes) | reviewer | PROVEN |
| static Lucide overlay | overlay_proof_v1 `overlay_proof_20260925_031640.mp4` (+030828/030953 identical) | manifest + eye_300.png + px_*.png; inside Δ 23217 vs ≤174 outside | YES | 13/13 proof gates | PROVEN (single icon) |
| layered icon + label + camera_push | graphics_layer_v1 `graphics_layer_20260925_032528.mp4` | raster_cache 3 PNGs + work push/fit pairs; icon Δ 17860, label Δ 20435 | YES | 16/16 gates | PROVEN (static, Latin) |
| SVG sidecar + Pillow card + color_clip cards | stat.svg; smoke card; hook navy cards | valid XML; frame-verified card | YES (card) | visual review | PROVEN |
| VFR→CFR proxy + A/V fix | VFR phone case | offset 0.72→0.05 s; frame-exact trim | frames | 4 REVIEW_AGAIN 0 FAIL | PROVEN |
| blind autonomous build | blind_social `blind_social_20260925_024502.mp4` 15.81 MB | body/joined/lead/bed/aug work files | work files | partial | PROVEN (build exists) |
| music/SFX beyond bed+sting; xfade; LUT; Lottie; 3D; Egyptian TTS; ducking/EQ | — | NO master contains them | — | — | NOT PROVEN (see §20) |

## 20. CAPABILITY CLASSIFICATION (each capability in exactly one category)

**A. PRODUCTION_READY (29):** ffprobe probe; duration/FPS/resolution/codec/audio-stream detect; frame extraction; silence detect; volume/loudnorm-JSON measure; Whisper tiny en STT + word timing; EDL TRIM/concat render + manifest; trim/concat/keep ops; AAC/PCM convert; gain/fade/mix/mux; ASS burn + sidecar SRT/VTT/ASS; Arabic RTL captions + font discovery + U+FFFD scrub; caption QC; A/V-sync check; VFR detect + CFR proxy + frame-exact trim; hard cuts; cover reframes; project store/pipeline-cache-fingerprint/config/logging/schemas; CLI (22 cmds); encoder smoke-select (qsv); reviewer recompute (UNKNOWN-never-PASS); deterministic rerender verify; black-frame check.
**B. PRODUCTION_READY_WITH_LIMITATIONS (22):** Piper Kareem narration (MSA-only, license-unverified); music bed path-only (0/1441 searched, CC-BY attribution); SFX sting-only (1/4); visual analysis (metrics-only, faces/objects unavailable); EDL 2-rule engine (silence+filler, conservative/keep-all); editing intelligence + editor brain + approvals + pacing execution (plan-heavy, Phase-13-engine-only); `render_shot` 4-op subset; `camera_push` (planner-partial); punch reframes; static Lucide overlay + layered icon/label + SVG sidecar + Pillow card + color_clip cards (single-icon/static/Latin/Chrome-dep/proof-scale); planner 3.1 determinism (residual 2–4× reuse); director intents (BROLL+CAPTION_FONT only); repair FULL-rerender-only; analysis-cache reuse (no segment cache); beat-snapped cuts (cuts proven, snapping smoke-only).
**C. IMPLEMENTED_BUT_NOT_PRODUCTION_PROVEN (15):** Arabic STT; loudnorm execution; librosa beat-snapping; pyloudnorm QC loop; scene-intelligence safety/density/pacing/repetition/jump-cut refinement; kinetic `\kf` word highlight; caption pacing signals/recommendations; diversity memory + rank/validate/repair; quality model (20 criteria); reviewer2 shot-level (outside bench/hook); visual review; style contract; OTIO export; font-catalog use.
**D. AVAILABLE_BUT_NOT_CONNECTED (16):** Chatterbox-EG artifacts; SAPI voices; ffmpeg `xfade`/`lut3d`/`overlay_cuda` filters (binary-has, engine-lacks); Lottie files (171+); `.cube` LUT files (26+); 3D asset files; three.js checkout; motion-design 5000 files; phosphor/tabler + flat-SVG sets; font catalog (164k lines); music catalog (1441 tracks); MH footage pool; graphics_kit counters/bars/timelines; rapidocr/mediapipe/rembg models (installed, unrouted); Node toolchain.
**E. PLANNED (17):** ducking; EQ/compressor/de-ess; crossfade/dissolve/wipe op; keyframed animation; easing engine; springs/particles/glitch/parallax/tracking/speed-ramps/whip-pans/match-cuts/masks/morphs/motion-blur; semantic asset search; discovery/requirement layer; voice-selection logic; segment-level video cache; duration-budget enforcement; under-60s auto-cut; VLM tagging; per-shot graphics auto-layout; animated overlays; Lottie→frames path; 3D→video path; cloud-free upscale path.
**F. BLOCKED (8):** Mohamed/VoiceTut TTS (HF error + GPU-gate + rights); Chatterbox realtime (RTF 37.6 + VRAM); Whisper medium+ on 16 GB/long-form; GPU compute on 940MX (CC 5.0 2 GB); HEVC HW encode (GM108); Remotion (company-license gate); 4K feature pipeline (RAM/CPU wall); commercial TTS clearance (no voice cleared).
**G. PLACEHOLDER / MOCK (4):** `engine/audio/` (empty); `engine/qc/` (empty); `qc` CLI stub (NOT IMPLEMENTED); Sayed single-WAV "voice".
**H. REJECTED (6):** karaoke ASS modeling (explicitly NOT modeled); MoviePy (FFmpeg covers it); Blender/Kdenlive/MLT v1 (automation fit); pedalboard/aubio (GPL-3); Essentia/Aeneas (AGPL) + Coqui XTTS (CPML) + Fish/SAM/F5 (NC) + YOLO (AGPL); full CUDA toolkit install (driver-only policy).

## 21. FINAL REAL TOOL COUNT (aliases collapsed; independently usable capabilities only)

1. Production-ready: **29**
2. Production-ready with limitations: **22**
3. Implemented but not production-proven: **15**
4. Available but disconnected: **16**
5. Planned: **17**
6. Blocked: **8**
7. Placeholders: **4**
8. Rejected: **6**
**Total classified: 117.**

## 22. CRITICAL PATH — 10 most important missing links (CONCEPT→…→FINAL)

1. **NARRATION (Egyptian voice)** — chain breaks at voice: only MSA Kareem producible; Mohamed BLOCKED, Chatterbox RTF 37.6 + unconnected → every "Egyptian" concept ships MSA or silent.
2. **ASSET DISCOVERY (semantic search)** — breaks at search: 5000 motion files + 171 Lottie + 1441 music + MH footage have no index/requirement layer; planner sees BROLL-by-path only (0 music searched, MH invisible).
3. **PLANNING→GRAPHICS (compositor breadth)** — breaks at op set: only static overlay + 4 shot ops; xfade/Lottie/animated overlays/keyframes have no gateway op → director intents narrow silently to holds + hard cuts.
4. **MOTION (transitions + camera follow-through)** — breaks at execution: feature masters store motion strings (HOLD×8) without calling `camera_push`; beat-snapping proven but unrequested.
5. **AUDIO (ducking/EQ/mix intelligence)** — breaks at mix: bed + sting + fades only; no ducking/compressor/EQ → narration-vs-music balance is manual/default.
6. **RENDER (segment cache)** — breaks at scale: no segment rerender; every repair re-encodes all segments (~13 min waste, 315 s/run) → iteration cost dominates wall time.
7. **QC→REPAIR (auto segment repair)** — breaks at loop: repair is planning-only + FULL rerender + MAX 2 → BLOCKED_REQUIRES_HUMAN; no hands-free fix-and-continue.
8. **DURATION BUDGET (<60 s)** — breaks at constraint: assert-only gate; 79.06 s ships because narration (69.24 s) was never cut (needs ≥3 lines cut, no auto-cut).
9. **SFX/MUSIC SUPPLY** — breaks at shelf: SFX 0 WAVs (1/4 kinds), music path-only → designs collapse to 1 bed + 1 sting.
10. **COLOR/FINISH (LUT + precise typography)** — breaks at finish: no LUT op (files idle), Latin-only labels, Arial default, font catalog unused → no graded, fully-Arabic-typed finish.

## 23. FINAL ANSWER

**WHAT AL-MONTIER HAS:** 72-module engine + 22-command CLI + 43-test suite + 950-file analysis cache + full Arsenal mirror (icons/Lottie/LUTs/3D/fonts/music/video) + Piper + Whisper-tiny + ffmpeg 9.0.1 + Node/Git/Chrome-file + 3617 project dirs of history.
**WHAT IT CAN ACTUALLY EXECUTE:** inspect→analyze→EDL→render→caption→QC→repair-plan loop; en STT; MSA narration; silence/filler EDL; trim/concat/cover; zoompan push (when requested); static Lucide overlay + labels; ASS captions RTL; gain/fade/mix/mux; VFR fix; deterministic planner→renderer builds with per-shot manifests.
**WHAT WAS PROVEN IN REAL MEDIA:** §19 table — E2E 8.83 s, editorials 21–28 MB, hook 79.06 s/20.44 MB, bench 79.14 s/18.52 MB (0 mismatches, hash-determinism), overlay + graphics-layer pixel-differential proofs, 36+6 and 50-cue Arabic burns, VFR 0.72→0.05 s, blind 15.81 MB build.
**WHAT EXISTS BUT IS NOT CONNECTED:** Chatterbox-EG, SAPI, xfade/lut3d binary filters, Lottie/.cube/3D/motion-design/phosphor/tabler + flat-SVG/font-catalog/music-catalog/MH-pool, graphics_kit extras, Node toolchain, heavy CV models.
**WHAT IS BLOCKED:** Egyptian TTS (Mohamed + Chatterbox-realtime), GPU compute, HEVC-HW, Remotion-license, 4K features, commercial voice clearance, Whisper-medium+ long-form.
**WHAT IS ONLY PLANNED:** ducking/EQ, transitions, keyframes/easing/particles, semantic search, segment cache + auto segment repair, duration enforcement, VLM tagging, animated/Lottie/3D paths.

**FINAL STATUS: CAPABILITY_INVENTORY_COMPLETE**

*Matrix companion: `docs/AL_MONTIER_CAPABILITY_MATRIX.csv`. Honesty note: test-pass counts (385/406/232…) are doc-reported, not re-executed in this audit-only run; every file/count/version/proof above was directly read or executed as a read-only check today.*
