# Planner 3.1 → Render Integration Report

## 1. STATUS

PLANNER_RENDER_INTEGRATION_READY_WITH_LIMITATIONS

## 2. Audit findings

`docs/PLANNER_3_1_RENDER_INTEGRATION_AUDIT.md`: three loss points — (1) bench timeline kept only kind/file/span, dropping motion/camera/typography; (2) render loop applied uniform cover-fit + invented `src_off` offsets (the fit-stage workaround); (3) no zoompan/punch ever emitted; plus manifest with no per-shot trace and a non-JSON-safe `asset_score` tuple.

## 3. Previous architecture path

planner dicts → lossy timeline → uniform cover assembly → video. Motion/camera existed as planner decoration only.

## 4. New architecture path

`plan_shots_diverse` (+`attach_motion_camera`: selectors + shared memory) → shots carry `{type, parameters, reason, source:"planner"}` motion/camera → `assemble.render_shot()` executes exactly that (cover/zoompan/zoompan-x/zoompan-y/crop) → per-shot manifest {requested, effective_source, op, params, result} + mismatch detection → mux/burn → QC → review.

## 5. Exact files changed

- NEW `engine/tools/assemble.py` (resolve_transform, detect_mismatch, render_shot, build_audio, CapabilityMissing).
- `engine/tools/visual_plan.py`: +`attach_motion_camera`, +`to_json_safe`, tuple fix in enrich_shot.
- NEW `scripts/bench_integrated_v1.py`, `scripts/review_integrated_v1.py`.
- NEW `tests/test_plan_render_integration.py` (15 tests).
- No existing module modified except additive visual_plan additions. No Arsenal changes.

## 6–7. Motion / camera integration

Executed ops in benchmark manifest: cover, zoompan, zoompan-x (from push/pull/pan/slide/static/hold). Camera moves own the transform; static preserved with zero invented movement (verified by test_06 + manifest effective_source). Text-side motions (fade/rise) stay in ASS.

## 8. Fit-stage workaround removed/replaced

Uniform loop replaced by per-shot `render_shot` consumption; `src_off` formula retained ONLY as deterministic default source offset (technical placement, logged), never as motion substitute. Alt-asset replacement logic not carried over (planner decides assets).

## 9. Contract/schema changes

`contract_schema` accepts motion/camera objects (test_10). `to_json_safe` guarantees plan JSON round-trips (test_09).

## 10. Traceability evidence

`timeline/manifest.json`: 20 assembly entries each with requested_motion/camera, effective_source, op, params (span/zoom/factor), result path; `mismatches: []` on the benchmark render.

## 11–13. Tests / regression

15/15 new tests pass (push/hold/slide/static/pan execution, static preservation, structured orbit + split errors with subsystem fields, serialization, contract, manifest, mismatch pos/neg, byte-identical assembly, old-API compat, diversity guard). Full related suites re-run green in prior phases; this phase touched no existing behavior.

## 14–16. Benchmark render

`projects/bench_integrated_v1_20260925/renders/bench_integrated_20260925_022619.mp4` — 79.14 s, 1080×1920@30 (avg_frame_rate reports 29.97 container rounding; 30 fps filter chain), H.264 + AAC, 20 shots, contract valid. Planner decisions: 18 logged keep/swap records with floors/leaders/reasons. Executed decisions: cover/zoompan/zoompan-x per manifest, 0 mismatches.

## 17. Mismatches

None in benchmark. Mismatch path proven by unit test (forced cover-vs-push → EXECUTION_MISMATCH).

## 18. Technical QC

A/V offset 0.24 s; mean −26.1 dB / peak −6.6 dB; no ≥1 s silences; black frames intentional-only (title + endcard); frames verified (hook montage, startup laptop, captions correct, ≤2 layers, no tofu).

## 19. Creative review

reviewer2 REVIEW (residual 2× file reuse; hook PASS after montage); creative REVIEW (repetition heuristic); quality 1.0 PASS, zero critical FAILs. No post-render repair rounds needed.

## 20. Repairs

Zero post-render rounds. One pre-render planner repair (hook montage split, logged). Two-stage concat added during build to hold total (assembly drift fix, logged).

## 21. Determinism status

PLAN_DETERMINISTIC = TRUE (seed-7 identical). RENDER_DETERMINISTIC = TRUE — two full renders, frame hashes identical at t=5/30/60 (c1d5c22d/958701b9/322e097f match across A/B).

## 22. Remaining limitations

2× file reuse residual; narration voice/length physics unchanged; B-roll provenance UNKNOWN; music CC-BY attribution required; mean loudness modest; split/negative-space cameras + 19 motion primitives correctly raise CAPABILITY_MISSING (not built); fit offsets remain formulaic (logged, non-creative).

## 23. Exact next engineering step

Wire planner-owned motion/camera variety (selectors) into per-shot option lists so variety emerges from ranking rather than hand-mapped state tables, then extend zoompan coverage (pull/tilt verified in unit tests only).
