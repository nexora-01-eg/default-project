# Diversity Memory Architecture

## Memory (`DiversityMemory`)

Per-production, seeded (default 7): `record(index, shot)` stores all 15 dimensions (asset, asset_category, shot_type, composition, camera, motion, transition, typography, graphics, visual_metaphor, color_treatment, sfx, music_state, spatial_position, visual_direction) with `count()` and `last_used()` (recency gap) queries plus `state()` (version/seed/count) for manifests.

## Budget (`diversity_budget`)

Scales with shots (sqrt) × density (low 0.7/medium 1.0/high 1.3): max_asset_reuse, min distinct motions/cameras/metaphors, hook_min_cuts (3, or 2 under 20 s), recency window 5. A 20 s and a 120 s production get different requirements by construction.

## Validation (`validate_creative_plan`)

Whole-plan inspection → PASS/WARNING/FAIL; findings carry shot_id, dimension, evidence, severity, suggested_correction, auto_repairable. Never renders.

## Repair (`repair_plan`)

Safe findings only (asset→procedural card when unmatched; motion/camera/typography alternation against memory). Structural fixes (hook montage split) execute in the driver as logged planner-repair rounds. Bounded: MAX_V2_REPAIR_ROUNDS=3.

## Ranking (`rank_candidates`)

score = relevance − recency-window penalty (0.06 core dims / 0.02 others); sorted by (−score, id); irrelevant excluded; relevant repeats may stand (recorded). Current gap: strict acceptability gate + unlogged keeps (see phase report §7).

## Rhythm / relations / escalation

`rhythm_profile` (LOW/MEDIUM/HIGH/PEAK + reset advice on 4-HIGH runs), `relation_to` (15 relations), `escalation_map` (INTRO→ENDING curve over story states).
