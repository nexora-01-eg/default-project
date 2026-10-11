# E2E_REAL_PRODUCTION_TEST_REPORT.md (2026-09-20)

Project: `project_20260920_112442_203839` (= E2E_REAL_PRODUCTION_TEST run;
engine IDs are generated, recorded here).

## INPUT
- source: `tests/fixtures/speech_video.mp4` (designated sample; real media:
  SAPI English narration, not synthetic test tones; `input/` holds no user video)
- duration 8.648 s, 640×360 @30.0 h264, mono AAC 22050 Hz, 113638 bitrate,
  0.12 MB, ffprobe-readable, source never mutated.

## ANALYSIS
- ingest (`analyze`): media + audio (silence spans 2.877 s total) — SUPPORTED.
- scenes: 1 scene, no cuts (PySceneDetect) — SUPPORTED.
- transcript (tiny, cpu/int8): en (p=0.994), 2 segments / 20 words /
  0 fillers — "Hello World. This is a test of the local speech engine." +
  "The quick brown fox jumps over the lazy dog." — SUPPORTED.
- edit: 7 decisions (2 long-silence REMOVEs) — SUPPORTED.
- intelligence: SAFE 2 / CAUTION 1, 3 jump-cuts, refined EDL — SUPPORTED.
- visual: 3 frames, faces/embeddings honestly unavailable — PARTIAL.
- brain (talking_head): hook keep_as_is, 3 downgrade_keep, 1 broll
  opportunity, 1 risk — SUPPORTED.

## PRODUCTION PLAN
- director: 3 beats, corporate bed + transition sfx, default-clean captions.
- editor intent (evidence): keep-all production; 3 pacing SAFE TRIMs found
  but correctly BLOCKED by approval hierarchy (base approval: 0 cuts —
  `approve-caption-pacing-execution` refused with "must not override",
  verified in logs). No plan file was hand-edited.

## ASSETS (Arsenal-X live)
- `/api/plan` → 9 requirements (4 B-roll + music + transition + font +
  intro/outro). `/api/match` → evidence-backed candidates (e.g. 16:9
  black graphics, PARTIAL, UNKNOWN provenance). `/api/verify` → CAUTION
  (technical pass, provenance unknown — not collapsed to PASS).
- Decision: no asset inserted (no plan requirement; brain assigned 0
  overlays). B-roll overlay machinery proven by Phase 13 regression tests.
- No downloads (zero approved sources — correctly inert).

## EXECUTION
- `approve-plan` (0 cuts, 3 jumps reviewed) → `captions clean` (3 cues,
  max cps 19.27) → `approve-captions sidecar/Arial` → `caption-visual`
  (3 placed, 3 conflicts) → approve → pacing (3 TRIM + 3 REVIEW) → approve.
- `render-plan --captions`: h264_qsv, 8.83 s output (expected 8.648,
  tol 0.4), QC pass, 3 sidecar cues QC pass, rtf 1.48x, manifest written.
- Output: `projects/project_20260920_112442_203839/renders/plan_20260920_143014.mp4`
  (+ .srt/.vtt). ffprobe: h264 High 640×360 30p + audio stream, 261 frames.

## REVIEW
- Independent reviewer: **REVIEW** — 10/14 checks PASS (output exists/
  non-empty, EDL intervals/order, caption overlap/intervals/empty/
  readspeed, both approvals valid, pacing bindings hold, visual approval
  present); 4 REVIEWs are honest Phase-25 depth placeholders + one true
  note (no pacing-execution approval — correct, none ran).

## REPAIR
- 1 cycle: 4 routes, all REVIEW_AGAIN (zero FAIL) → no re-render required
  by loop logic. Attempt budget untouched (0/2).

## FINAL
- `renders/plan_20260920_143014.mp4` — 8.83 s, 640×360@30 h264 + AAC,
  reviewer REVIEW (no FAILs), memory events recorded (render/review/config).

## INTEGRITY
- Pristine: caption + pacing approvals validate.
- Disposable-copy tamper (caption text changed): detected
  (`CaptionError: caption plan changed…`), copy deleted.

## REGRESSION
- Engine: 385 passed / 3 skipped / 0 failed. Arsenal-X: 54/54. tsc clean.
  Completed projects untouched; no new dependencies.

## PERFORMANCE (measured)
- ingest 0.3 s; transcribe cached (~1 s; 3.8x realtime uncached);
  scenes 0.5 s; visual 0.5 s; render 6.2 s; review <2 s; full suite 3.9 min.
  CPU-only (i7-7820HQ), RAM nominal, no GPU path used.

## LIMITATIONS
1. Brain judged this content keep-all: the E2E render contains no cuts.
   Edit execution itself is proven by Phase 17 `test_real_chain_e2e`
   (TRIM render + reuse + drift) in regression.
2. No B-roll/music inserted (no motivated requirement; plan assigned none).
3. Reviewer stream depth is placeholder (REVIEW, never PASS-by-assumption).
4. Sample fixture, not user footage (`input/` empty — exact command to use
   real input: `python -m engine.cli analyze <path>` then the chain above).
5. Transcription model `tiny` (speed); larger models authorized by existing
   `--model` flag, not exercised here.
