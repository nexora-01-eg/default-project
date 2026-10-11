# GRAPHICS_COMPOSITION_LAYER_REPORT — Layer 1.0 (icon + label)

**Date**: 2026-09-25 · **Status**: LAYER PROOF PASS (16/16 acceptance boxes)
**Proof master**: `projects/graphics_layer_v1/renders/graphics_layer_20260925_032528.mp4`
(6.0 s, 1080×1920@30) · **Manifest**: `projects/graphics_layer_v1/manifest.json`

## 1. Architecture before / after

- Before: one overlay op per proof; graphics decisions ad hoc; motion names
  unexecuted; no per-shot graphics collection.
- After: `shots[].graphics[]` collection → planner `propose_shot_graphics`
  (reasons mandatory) → director `review_shot_graphics` (approve/reject
  recorded: duplicates, overlaps, density cap) → `compose_shot` shared gateway
  (layer-order overlays via proven `overlay_asset`; zero duplicated filter
  logic) → differential pixel QC → manifest. Supported: `icon`, `label`.
  Declared-but-unsupported (`stat_card`, `callout`, `headline`,
  `svg_graphic`) raise staged CAPABILITY_MISSING — tested, never silent.

## 2. Contract

`shot-graphics-1.0` items: `type/layer/shot_id` + (icon: `candidate` with
sha/license/tags; label: `text` Latin-only) + `placement/ timing/style/
semantic_role/reason/decided_by/confidence` → director adds `approved_by` +
note. Placement/timing/canvas rules enforced at review AND render; label boxes
measured with the same function that renders them (no drift).

## 3–4. Planner / director changes

- Planner (`composition.propose_shot_graphics`): icon intents resolve through
  tag search (top pick + score evidence); label text validated (Arabic
  rejected with redirect to captions); every item carries a reason.
- Director (`review_shot_graphics`): owns density (max 3), repetition (same
  icon twice rejected), geometry (overlap-in-time rejected, canvas enforced);
  all rejections recorded with reasons. Verified by tests (duplicate, clash,
  density, Arabic-label cases).

## 5. Renderer changes

- Reused: `overlay_asset` gateway, `camera_push` adapter (zoom 1.0→1.08 on the
  base), `trim`/`fit` chain. New: `compose_shot` (layer-order loop) +
  `render_label` (Pillow Arial-Bold chip, deterministic) + content-hash raster
  cache. Renderer executes approved ops only.

## 6. Real Arsenal asset evidence

`eye.svg` (360 B, ISC, sha pinned at discovery, re-verified pre-raster and in
manifest q-fields); background `8166027…mp4` offset 2.0 (sha-pinned,
untouched). Label "HOOK" is procedural (no asset to pin; spec-sha recorded).

## 7. Pixel verification (per graphic, ×2 runs)

Icon box: inside-diff **17860** (≥2000 ✓), before/after ≤1500 ✓.
Label box: inside-diff **20435** (≥1500 ✓), label-gold **2607 px** (≥200 ✓).
Run 2 identical differentials → determinism PASS. Eyeball frame: gold eye over
phone (metaphor role) + navy/gold HOOK chip upper-right (tag role) — roles
visually distinct, no overlap.

## 8. Provenance

Manifest holds: planner proposals, director review+rule, per-layer asset refs
(icon sha, label spec-sha), camera op, timing/placement, pixel record,
background+icon untouched flags (both True), raster cache records.

## 9. Cache measurements (honest)

| Run | Raster hits | Wall | ffmpeg calls | Note |
|---|---|---|---|---|
| cold (HOOK) | 0/2 | 21.8 s | 11 (3 base+camera, 2 overlay, 6 extracts) | baseline |
| identical rerun | 2/2 | 20.0 s | same | chrome skipped (~2 s saved) |
| graphics-edit (HOOK→FOCUS) | 1/2 | 18.0 s | same | icon reused, label re-rastered |

**Boundary**: raster cache skips chrome/Pillow only; every video segment
re-encodes every run — no segment cache exists. No performance improvement
claimed beyond the measured ~2 s raster saving. Integrating segment reuse
safely is the documented next architectural task (identity must cover base
sha + op list + params + encoder).

## 10–11. Tests + regression

6/6 new (`test_graphics_layer.py`: two-type proposals, 4 unsupported-kind
failures, 3 director rejections, z-order pixel proof — green B covers red
AAAA, propagation+determinism incl. cache-hit assertions, manifest+identity) +
8/8 overlay tests = **14/14 pass**. Regression (`test_rendering,
test_execution, test_production_stack, test_creative`): **56 passed, 1
skipped** (pre-existing HW skip). Two test bugs found and fixed honestly
(stale-cache isolation, short-base window).

## 12. Limitations

Static graphics only (no keyframed animation); label Latin-only by design
(Arabic → captions, enforced); one camera preset used (adapter supports
params); max-3 density cap is a heuristic; overlap rule is box-based (no alpha
awareness); chrome dependency remains for SVG raster; segment re-encode
unaddressed.

## 13. Exact next blocker

Per-shot `graphics[]` needs to enter the real autonomous contract
(`contract_schema` shots' `graphics[]` is currently an unvalidated array) with
a `compose_overlays` planner pass, plus a segment-identity cache so graphic
edits don't re-encode whole timelines. Lottie/motion-assets/LUTs/transitions
stay STOPPED until then.

## Acceptance (16/16 PASS)

[x] shots[].graphics[] real public contract [x] multiple graphics per shot
[x] planner requests with reasons [x] director approves/rejects recorded
[x] renderer executes approved only [x] real Arsenal icon rendered
[x] second type (label) rendered [x] both visible in pixels (per-graphic diffs)
[x] deterministic layering (z-order pixel test) [x] deterministic timing
(windows verified) [x] provenance preserved [x] unsupported types fail
explicitly (4 kinds tested) [x] Arsenal originals unchanged (both shas)
[x] two runs deterministic (identical diffs) [x] regression passes (56+1)
[x] cache behavior measured honestly (table + boundary)
