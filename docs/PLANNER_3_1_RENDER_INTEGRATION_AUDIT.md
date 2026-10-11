# Planner 3.1 → Render Integration Audit (read-only findings)

**Date**: 2026-09-25 · **Scope**: trace one shot end-to-end, locate every point where planner motion/camera is lost.

## Trace: shot sh_001 (neon, 1.5–8.7 s) in bench_diverse_v1

1. **Planner decision** (`visual_plan.enrich_shot`): emits `motion: {"primitive": "HOLD", ...}`-shaped dict (hardcoded HOLD), `camera` = raw director string (`"cut in, hold"`), `typography: {mode}`, `caption_behavior`. `select_motion`/`select_camera` are NEVER called in the bench path — planner-owned selectors exist but are unwired.
2. **Plan object** (`plan_shots_diverse` output): carries the above fields; `asset_score` is a **tuple** (not JSON-serializable); motion/camera reasons absent.
3. **Timeline representation** (bench script `segs` list): keeps ONLY `(kind, file, span, label)`. motion/camera/typography/graphic fields dropped here — **loss point #1 (authoritative)**.
4. **Render assembly** (bench render loop): applies uniform `fit_filter(cover)` + `src_off` formula to every clip. No branch reads any motion/camera field — **loss point #2 (authoritative: the fit-stage workaround)**. Uniform treatment also overwrites punch variety and ignores static-vs-push intent.
5. **Actual FFmpeg params**: `scale+crop+fps` (+libx264 concat). No zoompan/pan/crop-reframe ever emitted — **loss point #3 (capability gap, not a bug)**.
6. **Manifest** (`build.json`): records duration/output/elapsed only. No per-shot requested-vs-executed record — **traceability gap**.

## Fit-stage workaround (exact location)

`scripts/bench_director_v1.py`: `fit_assets()` alt-asset replacement + uniform cover assembly. `scripts/bench_diverse_v1.py` lines ~106–136: uniform trim→cover→concat loop; `src_off = (i*1.7) % ...` formula invents framing with no planner input. The renderer performs technical normalization (fps/resample/concat) legitimately, but ALSO makes creative choices (uniform motion, invented offsets) that contradict planner intent.

## Contract/schema status

`contract_schema.CONTRACT_SCHEMA` permits `motion: object` but nothing validates its shape downstream and nothing consumes it. `montier_controller.load_contract` requires only canvas+shots.

## What must change (minimal, additive)

1. enrich: emit Phase-2 `{type, parameters, reason, source:"planner"}` motion/camera objects via select_motion/select_camera (shared memory).
2. New `engine/tools/assemble.py`: single `render_shot()` consuming those objects; uniform loop replaced; unsupported primitive → structured CAPABILITY_MISSING (no substitution).
3. plan_shots_diverse: JSON-safe asset_score (tuple→list).
4. Manifest: per-shot requested/normalized/params/result + mismatch detection.
5. Tests for all 15 acceptance behaviors; new benchmark render through the integrated path.
