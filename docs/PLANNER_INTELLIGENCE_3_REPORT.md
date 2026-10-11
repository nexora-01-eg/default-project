# Planner Intelligence 3.0 — Report

**Date**: 2026-09-25 · **Status**: PLANNER_INTELLIGENCE_3_READY_WITH_LIMITATIONS
**Benchmark**: `projects/bench_diverse_v2_20260925/renders/bench_diverse_20260925_003748.mp4` — 79.14 s, 1080×1920@30, H.264 + AAC, A/V offset 0.24 s.

## 1. Implementation

`engine/tools/diversity.py` (v3.0.0): DiversityMemory (15 dimensions, recency/counts), 9 repetition types + INTENTIONAL_CALLBACK with explicit allow-record, size-scaled budgets, `validate_creative_plan` (PASS/WARNING/FAIL + shot/dimension/evidence/severity/correction/auto-repairable), planner `repair_plan`, recency-windowed `rank_candidates` (relevance − penalty, irrelevant never wins), rhythm model, 15-relation map, escalation curve. `visual_plan.plan_shots_diverse` wires memory+budget+validate+repair deterministically (seed recorded, v3.0).

## 2. Tests

23/23 pass: all 8 repetition types, callback exemption, budget scaling (short/long), validation structure, repair behavior, windowed optimization, seed determinism, relevance protection (irrelevant excluded; relevant repeat stands), escalation, relationships, rhythm, asset/motion ranking, composition tracking.

## 3. Benchmark comparison (same topic/script/render chain)

| Measure | BEFORE (bench v0) | AFTER (diverse v2) |
|---|---|---|
| Distinct files | 2 (6× neon, 6× dubai) | 6 (max 4×, beat-driven) |
| Pre-render validation | FAIL (hook + repetition) | FAIL (hook only) → 1 pre-render repair (montage split) |
| Post-render repair rounds | 2 (r1 montage+diversity, r2 eq split) | **0** |
| R2 final | REVIEW | REVIEW (residual 2–4× reuse) |
| Creative / quality | PASS / 1.0 | REVIEW (repetition heuristic) / 0.95, no critical FAIL |
| Determinism | n/a | seed-7 identical plans (test); single renders (no double-render proof claimed) |

## 4. Repetition prevented before render

Hook montage enforced pre-render (3 shots <5 s); beat-aligned needs route each scene to distinct relevant files; budget caps reuse; validator blocks bad plans from rendering.

## 5. Repairs required after render

Zero. Residual: 2–4× file reuse across 79 s (reviewer REVIEW, accepted) + carried-over narration/audio limitations from v1 track.

## 6. Determinism result

Planner: identical plans across runs (test_14). Assembly: fixed spans/filters/encoders (construction-deterministic; double-render not performed — stated, not claimed).

## 7. Remaining limitations

- Rank-swap path never fires: `acceptable = rel>0` gate too strict when one file dominates a need; keeps are correct per §9 but unlogged as decisions — next step: log keep-with-reason + relative relevance floor.
- Diversity lives in beat-needs, not cross-scene memory pressure; motion/camera/typography variety still manual.
- Same carried voice/audio/provenance limits as v1 track.

## 8. Single most important next engineering step

Relative-floor ranking with logged keep-reasons (spec §9/§13 fully), then planner-owned motion/camera alternation.
