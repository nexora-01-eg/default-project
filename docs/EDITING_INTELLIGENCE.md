# EDITING_INTELLIGENCE.md — Phase 10 (`engine/editing/intelligence.py`)

## Implementation plan (written before code, 2026-09-17)

BASE EDL (Phase 8, untouched) → INTELLIGENCE ANALYSIS → REFINEMENT →
FINAL EDL + `edit_intelligence.json`. No rendering, no gateway changes.

1. **Models** (`models.py`, additive): `Evidence` (8 fields), per-scene
   speech metrics, pacing metrics, repetition/jump-cut candidates,
   cut-safety assessments, `IntelligenceReport`.
2. **Pure analysis functions** (dict-in/dict-out, no I/O): scene speech
   density + duration outliers (flags only, never deletions); boundary
   continuity (measured word windows + punctuation heuristic with a recorded
   limitation); cut safety (SAFE/CAUTION/UNSAFE with per-check evidence);
   jump-cut candidates (same-scene gaps); pacing (shots, cuts/min, wpm,
   pauses/min — measurements only); exact-match repetition candidates
   (spans + similarity 1.0, no auto-delete by default); preferred cut
   points (word gaps ≥ 0.15 s, silence, scene boundaries — scored).
3. **Refinement** (conservative default): revert UNSAFE removals to KEEP
   with provenance (`original_action/reason/rule/evidence`); strict mode
   also reverts CAUTION; repetition removal strictly opt-in (2nd+
   occurrences, remnants ≥ min_keep, re-tiled, re-validated).
4. **Project integration**: load base EDL + cached analyses (no model
   downloads, no analysis reruns); cache stage `intelligence` on base-EDL
   hash + analysis hashes + policy + version; write `edit_intelligence.json`
   + `refined_edit_decision.json`; stage `intelligence`; JSONL logging.
5. **CLI** `edit-analyze <project>` mirroring `edit` conventions.
6. **Reuse, don't duplicate**: `edl_hash`/`validate_edl` imported from
   Phase 9 execution (validation only — no render path touched);
   `filler_set`/`normalize_token` from Phase 5/6; pipeline cache/log/store.
7. **Tests** (20): hand-built units for every signal + real-fixture chain
   (mixed_6s + SAPI speech). Full suite must stay green.

## Architecture

`engine/editing/intelligence.py`, ~600 lines, zero I/O in the analysis core:

```
base EDL (edit/edit_decision.json, Phase 8 untouched)
  + audio_analysis.json + transcript.json + scenes.json (cached, never rerun)
  -> analyze_intelligence() -> IntelligenceReport
  -> refine_edl() -> refined EDL dict (re-validated via Phase 9 validate_edl)
  -> edit/edit_intelligence.json + edit/refined_edit_decision.json
```

Reuse, not duplication: `edl_hash`/`validate_edl` from Phase 9 execution
(validation only — render path untouched); `filler_set`/`normalize_token`
from Phase 5/6; pipeline cache/log/project-store. No FFmpeg, no models,
no network anywhere in this layer.

## Base EDL vs refined EDL

The base EDL is never mutated: refinement copies decisions, flips only what
policy allows, and records `metadata.provenance{original_action,
original_reason, rule, evidence, refined_by}` on every change (ids renumbered
`ref_*` with `original_id` kept). Default conservative refinement only ever
KEEPS more (UNSAFE revert; strict also CAUTION). Repetition removal is
strictly opt-in and re-tiles + re-validates.

## Evidence model

`Evidence{evidence_type, source, start, end, metric, value, threshold,
explanation}` — all 8 fields mandatory. Clean SAFE verdicts still emit a
`safety_summary` entry (what was checked), so traceability covers every
non-trivial decision, not just flagged ones.

## Safety states

Technical states only, never quality rankings: word overlap with meaningful
speech / scene crossing / sub-minimum removal → UNSAFE; unplanned filler
touch / tight (<50 ms) padding / sentence split / sub-minimum neighboring
keep → CAUTION; else SAFE. Unknowns (no punctuation signals) skip their
check and are recorded in `sentence_signals.limitation`.

## Pacing metrics

Pure measurements, never "good/bad": shot avg/median, scene changes per
minute, words per minute of speech time, pauses per minute + avg pause.
Scene-duration outliers (`long` > 2× median, `short` < ½ median) are flags
only — outliers are never deleted for being outliers.

## Repetition candidates

Maximal exact repeats (fillers dropped, positions kept), `similarity: 1.0`
by construction, `confidence: 0.6` labeled rule confidence. Candidates only
by default; removal needs `--enable-repetition` + strict single-KEEP
containment + survivable remnants, else a recorded skip.

## Jump-cut detection

Removal gaps between same-scene KEEPs with gap < 2 s → `potential_jump_cut`
(true = likely continuity break); cross-scene gaps are natural cuts (false).
Metadata only — no zooms, B-roll, or transitions (later phases).

## Confidence handling

Three labeled kinds: source model confidence (word probabilities, passed
through), rule confidence (fixed heuristics: silence margin, 0.6 repetition,
documented formulas), safety status (not a probability at all). Never
combined into fake certainty.

## Conservative policy

Defaults: safety net ON, strict OFF, repetition removal OFF, min keep 0.5 s,
min remove 0.2 s, all analyses ON. Changing any key invalidates the cache.

## Limitations

- Sentence inference is punctuation-heuristic; word tokens rarely carry it
  (coverage recorded; placement prefers gaps/silence/boundaries instead).
- Repetition is exact-match only (no paraphrase/fuzzy).
- Jump-cut flag is heuristic (same scene + short gap), not visual analysis.
- `processing_s` is wall-clock: excluded from determinism comparisons.
- Refined EDLs are NOT auto-rendered (Phase 10 never calls the renderer).