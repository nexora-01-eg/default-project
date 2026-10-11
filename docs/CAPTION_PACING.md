# CAPTION_PACING.md — Phase 16 (`engine/editing/caption_pacing.py`)

## Status: implemented + verified (2026-09-19)

39 tests in `tests/test_caption_pacing.py` (38 unit/project/CLI + 1 real
chain, ffmpeg-gated); real-data verification on `speech_video.mp4` via
PyAV + cached tiny model (ffmpeg binary absent on this box). Full suite
regression green; Phases 13–15 untouched (no render changes).

## Implementation plan (written before code, 2026-09-19)

Intelligence layer ABOVE Phases 12–15 (nothing rebuilt, nothing re-analyzed
beyond reading artifacts): caption plan + visual plan + scenes + EDL +
intel report + brain plan + transcript/audio → signals → ranked
recommendations → plan → approval. No rendering, no EDL mutation, no
downloads, no ML deps.

1. **Models** (additive): `CaptionPacingContext`, `PacingSignal` (15 types),
   `PacingRecommendation` (8 actions), `CaptionPacingPlan`.
2. **Signal engine** (pure functions): caption density (CPS/WPM/gaps/rolling
   windows/scene density), visual pacing (static spans, motion, outliers,
   framing repetition, change points, placement/conflict flags), sentence +
   pause awareness (punctuation terminals, inter-word gaps ≥ threshold,
   cue/scene boundary coincidence), EDL + safety lookups (REMOVE coverage,
   CutSafety by decision_id).
3. **Correlation → candidates → safety filter → ranking**: the six spec
   cases as explicit rules; TRIM gated on EDL-REMOVE coverage + cue mapping
   validity + non-UNSAFE; SPLIT gated on pause + cue boundary + scene/safe
   boundary + safety; conflicts resolved by story > safety > content >
   visual > pacing with recorded winner/principle; ranking by
   (priority, −confidence, start) — no numeric quality scores.
4. **Styles**: read from Phase 12 `STYLES` (11 names verified in repo);
   bounded documented adaptations (social_short: denser thresholds, lower
   silence tolerance; podcast/documentary/cinematic: relaxed; educational:
   repetition tolerance). Overrides via existing config plumbing.
5. **Project integration**: required caption plan + scenes + EDL; transcript/
   audio/visual/intel/brain optional-with-limitation (missing → explicit
   warning + degraded signals, never fabricated). Cache stage
   `caption_pacing` (8-part identity + code hash). Artifacts
   `editing/caption_pacing_plan.json` + `editing/approved_caption_pacing_plan.json`;
   stage `caption_pacing`; JSONL logging.
6. **CLI** `caption-pacing [--style --force --json --dry-run]` +
   `approve-caption-pacing [--json]`; dry-run writes nothing (no store).
   No rendering changes whatsoever (not even metadata).
7. **Tests** (`tests/test_caption_pacing.py`): unit battery per §20 +
   hand-built fixture scenarios for all 8 media cases + full real chain on
   existing fixtures + full suite must stay green.

## Architecture
