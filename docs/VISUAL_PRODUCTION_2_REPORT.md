# Visual Production 2.0 — Phase Report

**Date**: 2026-09-24 · **Status**: VISUAL_PRODUCTION_2_READY_WITH_LIMITATIONS
**Benchmark**: `projects/bench_director_v1_20260924/renders/bench_director_r2_20260924_231835.mp4` — 78.89 s, 1080×1920@30, H.264 + AAC, A/V offset 0.16 s.

## Implemented (all tested)

- Render foundation: 10-case Arabic/RTL/diacritics/mixed/numerals/punctuation/kinetic/SVG-text/over-video/emoji burn suite (13 tests) + Pillow alpha composite + SVG-raster structured-missing test.
- Findings fixed: Latin-run bidi isolates (`isolate_latin`, U+2066/2069) after "workflowالـ" defect; emoji → CAPABILITY_MISSING (tofu confirmed, no font in chain; PNG-overlay alternative documented).
- Confidence-aware timing: HIGH/MEDIUM/LOW tiers; >35% LOW forces phrase mode (no karaoke).
- Motion: 35-primitive table (supported + structured-missing), grammar roles incl. NO_MOTION, parameterized presets, visual grammar states.
- Typography: layers ≤2, 8-word wrap, safe zones, emphasis spans, role→style map.
- Visual Director: per-sentence records (intent/emotion/info/metaphor/shot/asset/motion/typo/SFX/music/transition/camera), 16-state story grammar, 15-category metaphor engine, short-form arc selector.
- Shot planner 2.0: enrich (18 fields) + validators (overlap/dead/pacing/asset/text/motion/repetition).
- Graphics kit: counter/bars/progress/timeline/network SVG (deterministic, byte-identical) + Pillow raster cards.
- Composition rules + reject helper; SFX/music directors (states, ducking, beat-snap); style contract + checker.
- Reviewer 2.0 (shot-level, no scene bins; FAILs carry time/shot/evidence/cause/repair) + 18 new repair routes + MAX_V2_REPAIR_ROUNDS=3 + 20-criteria quality model with critical-FAIL override.

## Tested

45 new tests pass (13 foundation + 12 v2 + 7 stack + 13 tool). Pre-existing fast suites re-run green (69 tests). No existing code modified except additive repair-route dict entries + reviewer2 card-guard fix.

## Benchmark: autonomous director path

Topic in → plan_production → direct_script (7 beats, 7 states) → storyboard (12 shots, NARRATED) → enrich/validate → fit-assets (logged) → music/sfx directors → style check → render → QC → review → 2 repair rounds → manifest. No manual shot/animation/asset/timing decisions.

## Repairs (bounded, 2 rounds)

1. R2 hook FAIL (7.2 s opening) → 3-cut montage, sync preserved; R2 repetitive-selection REVIEW (same file 6×) → diversity re-pick (max 2×, non-adjacent).
2. R2 residual REVIEWs + new eq shot (9th distinct file). Final: R2 REVIEW (2×-reuse only), creative PASS, quality 1.0 PASS.

## Key honest findings

- Autonomous plan_shots without diversity memory picks one file per scene (6× neon / 6× dubai in v0) — reviewer caught it, repair fixed it; planner upgrade recorded as future work (gap).
- Creative-reviewer scene bins were the artifact source; reviewer2 is shot-level.
- Narration physics unchanged (Piper ~2.4 s/char → sparse 2-line script); all v1 limitations carry over.
- Mean loudness −26.1 dB (accepted; peak −6.6 dB safe).
- Unavailable stays unavailable: emoji font, SVG raster, web runtimes, 3D execution, GPU/torch models, NC/viral licenses — all with structured evidence, none faked.
