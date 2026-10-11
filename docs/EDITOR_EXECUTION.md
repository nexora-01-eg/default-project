# EDITOR_EXECUTION.md — Phase 13 (`engine/editing/approval.py`, `engine/rendering/plan_execute.py`)

## Implementation plan (written before code, 2026-09-17)

EXISTING plan → explicit APPROVAL → source-coord composition → gateway-only
render → extended QC → provenance manifest. Nothing rebuilt: Phase 9
primitives reused, gateway EXTENDED (not bypassed) with 5 small additive
functions, all covered by unit tests + full-suite regression.

1. **Gateway** (`ffmpeg.py`, additive only): `trim(streams=av|video|audio)`,
   `mux()` (stream-copy track mux), `make_silence()` (lavfi), `fit_filter()`
   (cover/contain/crop vf builder), `frame_health_check()` (blackdetect +
   error scan). Existing commands byte-identical for existing callers.
2. **Models**: `BrollAsset`, `PlanApproval` (immutable snapshot), `ExecutionOp`
   (base|broll_replace|broll_overlay + layer), `ExecutionPlanModel`.
3. **Approval** (`editing/approval.py`): asset register/validate (exists,
   probe, hash-pinned); approve cuts (approve/approve_with_mitigation only —
   reject/downgrade/investigate never execute); `--broll-map` exact-span
   assignment (unmapped = skipped, base kept); jump mitigation gating
   (accept/preserve always executable; broll needs asset; reframe/transition
   unsupported); immutability = plan hash + source fingerprint + asset
   hashes revalidated at render.
4. **Composition** (source coords, single pass): EDL keeps minus removals,
   overlays clamped to keeps (warning) or failing closed; per-op source→
   output offsets; base trims + prepared broll parts (cover/contain/crop,
   fps-normalized, mute/original audio) → ONE concat re-encode (copy only
   when provably uniform — default re-encode, correctness first).
5. **QC**: Phase 9 `validate_output` + mapped black-frame check + mapped
   silence check + broll placement proof (dhash+hist vs asset AND vs base;
   ambiguous → warning, never forced fail/pass) + decode errors.
6. **Manifest/cache/CLI**: `renders/plan_*.mp4 + plan_*_manifest.json`
   (kind=plan, full provenance); identity = source fp + plan/approval/exec
   hashes + assets + config + encoder; reuse revalidates; `approve-plan`
   and `render-plan [--dry-run|--force|--output|--encoder|--json]`.
   Dry-run resolves NOTHING that encodes (no smoke tests, no ffmpeg writes).
7. **Tests** (~30): approval/validation/broll/timeline/render/QC/cache/
   dry-run + real chain (static_12s + local colorbars asset) + full suite.

## Architecture

```text
SOURCE MEDIA -> ANALYSIS -> EDITOR BRAIN -> EDITOR PLAN
    -> editing/approved_edit_plan.json (EXPLICIT approval)
    -> validation -> ExecutionPlanModel (source-coord ops)
    -> gateway trims/mux/concat (ONE uniform re-encode)
    -> extended QC -> renders/plan_*.mp4 + plan_*_manifest.json
```

`engine/editing/approval.py` (decision side: assets, approval, immutability)
and `engine/rendering/plan_execute.py` (execution side: compose, render, QC,
manifest, cache) are separate by design. The brain never authorizes; the
renderer never decides.

## Approval model

`approve-plan` snapshots: plan hash (wall-clock excluded) + source pin
(size/mtime/sha) + analysis hashes + approved cut ids + B-roll assignments
(opportunity span, asset, hash, offset, audio, fit, placement) + jump
mitigation gating (accept/preserve executable; reframe/transition
unsupported). Cuts with reject/downgrade/investigate verdicts are never
approved; explicit `--include` of an UNSAFE cut fails the approval.
Unmapped opportunities stay base footage — never substituted.

## Execution models

`ExecutionOp` (keep/remove/broll_replace/broll_overlay; source AND output
coords; layer base|overlay; approval_state) and `ExecutionPlanModel`
(reconstructible timeline + warnings). Unapproved REMOVEs stay KEEP
(explicit). Overlays clamp to keeps with warnings; fully-outside or
overlapping assignments fail closed.

## B-roll assets

Local files only (`source_type: local`). Validation: exists, probeable,
duration > 0, video stream. Hash-pinned at approval; any drift fails render.
Short assets fail at approval (no looping in Phase 13); long assets trim.
`--broll-map "START-END=PATH[@OFFSET]"` matches by containment (partial
windows allowed; executed span is always the request span).

## Timeline mapping

Composition walks source keeps; overlays split keeps into sub-segments;
output offsets accumulate over the base layer only (overlays preserve
duration). Single uniform concat re-encode (correctness first); `direct`
shortcut only for single-keep Phase 9 paths (untouched).

## Jump-cut mitigation

`accept_cut`/`preserve_section` execute as no-ops; broll/cutaway/alternate
render as overlays when asset-mapped; reframe/transition recorded
`unsupported` with the safer edit preserved. Never faked.

## Audio behavior

Overlay = base dialogue intact (muxed under muted fitted video).
Replace + mute = generated silence (dialogue gap is explicit in the plan).
Replace + original = asset audio. `mix`/`duck` are rejected at approval
(unsupported in Phase 13) — never silently applied.

## Dry-run

`render-plan --dry-run` validates approval/source/assets, composes, prints
ops/assets/durations/warnings/encoder-note/QC plan. It resolves NOTHING
that encodes (no smoke tests) and writes no media.

## Rendering

Per-op gateway trims (explicit encoder resolved once), B-roll prepared
(trim → cover/contain/crop + fps normalize → mute/original audio → mux),
one concat re-encode, temp workdir kept on failure with its path in the
error. Phase 9 `render` CLI and EDL path untouched.

## QC

Phase 9 `validate_output` + start-time checks + mapped black-frame check
(output black must match source-mapped black) + mapped silence-profile
check + per-overlay placement proof (frame matches asset AND differs from
base; ambiguous → accepted-with-warning, mismatch → fail) + decode errors.
Any failure → `qc_failed`, render never marked successful.

## Manifest

`kind: plan` with source/editor-plan/approval/execution hashes,
fingerprints, config, encoder+reason, operations, assets, mappings,
expected/actual durations, QC, warnings, processing/RTF, schema versions.
Answers WHY each frame exists: op → decision → evidence refs.

## Cache

Identity = source + plan/approval/exec hashes + asset hashes + config +
encoder. Reuse re-probes output (exists, size, duration, streams); corrupt
outputs re-render. `--force` bypasses. Policy/config/asset/plan/source
drift all miss.

## Failure behavior

Missing/invalid approval, drifted source/plan/analyses/assets, bad
intervals, overlaps, unsupported actions, short assets, ffmpeg errors, QC
failures → explicit errors with stage (`input|plan|execute|validate`),
diagnostics retained, sources never touched, no silent fallback edits.

## Caption layer (Phase 14, additive)

`render-plan --captions` runs AFTER base QC passes: approved caption plan
is mapped via keep offsets, then sidecar files and/or one burned-in ASS
pass. Base flow without the flag is byte-identical to Phase 13. Caption
approval (`editing/approved_captions.json`) is separate from — and never
mutates — the plan approval. See `docs/CAPTIONS.md`; the transcript line
`Transcript ≠ Caption Plan ≠ Approved Caption Execution` holds end to end.

## Limitations

- No looping for short assets; no PiP; no mix/duck; no stock scraping.
- B-roll topics are keyword frequency (Phase 12), not semantics.
- Placement proof is hash+histogram similarity (documented thresholds).
- Silence QC tolerance ±1.0 s (AAC priming/padding).
- Cache reuse re-probes duration/streams (not full QC) by design.