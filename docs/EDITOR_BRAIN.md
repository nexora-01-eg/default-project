# EDITOR_BRAIN.md — Phase 12 (`engine/editing/brain.py`)

## Implementation plan (written before code, 2026-09-17)

Decision layer ABOVE Phases 2–11 (nothing rebuilt, nothing re-analyzed):
existing artifacts in → 8 explicit passes → `editing/editor_plan.json` out.
No rendering, no downloads, no media fetching, no timeline mutation.

1. **Models** (additive): `StyleProfile` (11 styles), `HookAssessment`,
   `StorySegment`, `DensityWindow`, `CutCandidate`, `BrollOpportunity`,
   `VisualChange`, `AudioRecommendation`, `EditorialRepetition`,
   `QualityRisk`, `ConflictResolution`, `ProfessionalEditPlan`.
2. **Passes** (pure functions): understand → structure → density/hook/story
   → pacing → cut candidates (validating base REMOVEs + repetition trims,
   never inventing cuts) → jump mitigations → B-roll/visual/audio plans →
   conflicts → ranking → master plan. No combined magic scores; components
   exposed; priority ⟂ confidence.
3. **Conservative core**: KEEP on ambiguity; safety vetoes (never overridden,
   not even by `--aggressive`); outliers/risks flagged, never deleted for
   being outliers; repetitions are candidates, never auto-trims.
4. **Project integration**: required audio/transcript/scenes/base-EDL;
   refined/intelligence/visual optional (used when present, `unknown` +
   reason when absent). Cache stage `editor_plan` (all hashes + style +
   version). Stage + JSONL logging. CLI `editor-plan`.
5. **Tests**: hand-built units per §27 + full real chain on mixed_6s (static,
   speechless — limitation stated) and SAPI speech (real hook/story).
   Full suite must stay green.

## Architecture

`engine/editing/brain.py` (~800 lines). Eight explicit passes over cached
analysis dicts; no rendering, no downloads, no re-analysis:

```text
audio + transcript + scenes + base EDL (+ refined/intel/visual if present)
  P1 understand/validate -> P2 hook/story/density -> P3 pacing
  P4 visual coverage -> P5 candidates (cuts/jump/broll/visual/audio/repetition)
  -> P6 safety + conflicts -> P7 ranking -> P8 ProfessionalEditPlan
  -> editing/editor_plan.json
```

## Editorial philosophy

"Should this be cut?" — never "Can this be cut?". KEEP on ambiguity;
meaning is never sacrificed for cut frequency; knowing when NOT to edit is
a feature (most recommendations on ordinary content are `maintain` /
`informational`). Outliers and risks are flagged, never deleted for being
outliers. Audio-only sources reuse the Phase 8 degenerate-scene rule
(recorded warning).

## Decision hierarchy

`story_continuity > edit_safety > content_value > visual_quality > pacing`
(configurable order in `resolve_conflict`). Safety vetoes (UNSAFE reject,
CAUTION downgrade) are never overridden — not even by `--aggressive`
(which only shifts tolerances/density styles).

## Evidence system

Phase 10 `Evidence` (8 mandatory fields) on every factor, mitigation, risk,
and conflict. Clean verdicts still carry their basis. No combined magic
scores anywhere; priority (editorial value) and confidence (evidence
strength) are separate fields on every recommendation.

## Hook analysis

First min(30 s, 20%): question/word/filler/silence/first-delay signals;
removable preamble = leading silence + filler-only opening; strategies
`trim_preamble` (≥1 s) / `keep_as_is` / `investigate` (no words). Confidence
0.7/0.4/0.2 — stated, not precise.

## Story structure

Scene-bounded segments; CTA keywords → `call_to_action` (0.7); positional
hook/conclusion/main_point/transition (0.35–0.45); wordless → `unknown`
(0.2). Low by design — position is weak evidence and the numbers say so.

## Pacing

Per-scene `maintain` default; `add_visual_change` for static scenes carrying
speech (change the picture, never punish words); `tighten` for long sparse
static speechless spans; global `open_up` past style cut ceilings;
`target_duration` gaps are `investigate` notes — never auto-fit cuts.

## Cut intelligence

Ten evidence factors per base REMOVE (continuity, sentence, word timing,
scene containment, visual context, resulting shots, base evidence, size,
plus safety lookup and downstream keeps). Verdicts `approve /
approve_with_mitigation / downgrade_keep / reject`, plus repetition spans
as `candidate_for_trim` (never EDL edits). Disagreements with the refined
EDL become explicit conflicts, not silent overrides.

## Jump-cut handling

Severity from gap + same-scene evidence; mitigations ordered
(`accept_cut`, `preserve_section`, `broll`, `cutaway`, …) by style
tolerance. Recommendations only — reframe/zoom are `investigate` notes
(no capability in this phase).

## B-roll opportunities

Static/long scenes, jump concealment, 2×-median scenes; keyword topics from
measured word frequency (len>3, non-filler, tiny stop list — documented);
`recommended` only for concealment, ≥8 s stagnation, or high-intensity
styles. Never downloads, generates, or inserts media.

## Audio recommendations

Silence/filler spans from approved removals, loudness check vs −16 LUFS,
sentence-adjacent pauses preserved, music/noise honestly `later_phase`
(unmeasured by current analysis — stated, not guessed).

## Repetition

Phase 10 candidates + policy mapping (`keep`/`investigate`/`candidate_for_
trim`); editorial reason cites style policy; removal needs conservative
evidence and stays a candidate.

## Conflict resolution

Pro vs con signals resolved by principle rank with recorded winner,
principle, and explanation. Cross-checked against refined EDL.

## Confidence

Three labeled kinds (source passthrough / rule heuristic / safety state),
never merged. Priority mapping: safety→high, hook→per `hook_importance`,
broll recommended→medium/optional→low, observations→informational.

## Priorities

critical/high/medium/low/informational separate material improvements from
observations; P7 ranks highlights by (priority, −confidence, start).

## Cache

Stage `editor_plan`: all present analysis hashes + resolved style dict +
`BRAIN_VERSION` + **source-code hash** (engine edits auto-invalidate; added
after a stale cache served pre-fix logic mid-session). Deterministic reruns
byte-equal modulo `processing_s`/`cached`.

## CLI

`video-engine editor-plan <project> [--style NAME] [--target-duration S]
[--aggressive] [--json]`. Requires analysis + base EDL; exits 0/2.

## Limitations

- Story labels are positional heuristics (confidence ≤0.7, CTA excepted).
- Sentence inference inherits Phase 10 punctuation limits.
- Visual reasoning degrades to `unknown` without visual analysis (never
  guessed); broll topics are keyword frequency, not semantics.
- Target durations are advisory; the brain will not cut to fit.
- `processing_s` excluded from determinism comparisons.

## Examples

```
video-engine editor-plan <project>
video-engine editor-plan <project> --style talking_head --target-duration 60
video-engine editor-plan <project> --style social_short --aggressive --json
```