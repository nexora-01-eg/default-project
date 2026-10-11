# OVERLAY_ICON_PIPELINE_REPORT — first real constructed-graphics path

**Date**: 2026-09-25 · **Status**: PROOF PASS (all 13 acceptance boxes checked)
**Proof master**: `projects/overlay_proof_v1/renders/overlay_proof_20260925_031640.mp4`
(6.0 s, 1080×1920@30, H.264) · **Manifest**: `projects/overlay_proof_v1/manifest.json`

## 1. Before / after architecture

- Before: constructed visuals existed only as plan strings (`motion` names,
  `graphics:"some"`) or uncalled generators (`graphics_kit`); renderer offered
  trim/concat/fit/burn only. Icons (1779 Lucide + phosphor + tabler) had no
  index, no requirement kind, no raster path, no composite op.
- After: `ICON` requirement → tag-based discovery → planner decision →
  director approval → validated overlay contract → Chrome raster → ffmpeg
  `overlay_asset` gateway → pixels → differential QC → provenance manifest.
  Two additive code units; zero existing systems replaced.

## 2. Exact files changed / added

- ADDED `engine/graphics/icons.py` (274 lines): `search_icons`,
  `rasterize_icon`, `build_overlay_op`, `validate_overlay_op`,
  `execute_overlay`, `IconCapabilityError` (staged), `find_chrome`
  (PATH + Program-Files fallback — closes the audit's chromium detection gap).
- EDITED `engine/rendering/ffmpeg.py`: +`overlay_asset()` gateway op
  (rgba+opacity+scale+`overlay enable=between(t)`), same conventions
  (probe→validate→`_resolve_encoder`→`run_ffmpeg(op=...)`).
- ADDED `scripts/prove_overlay_icon_v1.py`: deterministic 9-ffmpeg-call proof.
- ADDED `tests/test_overlay_icon.py`: 8 focused tests.
- No Arsenal file touched (q9 manifest flag True; sha re-verified).

## 3. Contract

`icon-overlay-1.0` dict: `op_id/type/requirement{ICON,intent}/asset{name,set,
source_path,sha256,bytes,license}/placement{x,y,w,h}/timing{start,duration}/
style{color,opacity}/reason/decided_by/approved_by` (+ planner decision +
raster record at execution). Validation rejects: non-ICON/missing/non-SVG
assets, sha drift, out-of-canvas placement, window overrun, bad color/opacity,
missing reason or approver. Failures raise staged `IconCapabilityError`
(discovery|raster|contract|render) — no silent fallback anywhere.

## 4–5. Asset + discovery evidence

Requirement `req-icon-001`: "visual icon representing attention / scrolling /
focus". `search_icons` over 1779 Lucide sidecar tag sets (token-level, so
"watch"≠"swatch"; filename-only resemblance rejected by construction):
**eye wins** (tags view/watch/reveal…, score 9) over scan-eye/telescope.
`F:/Arsenal/02_Icons/lucide/icons/eye.svg` (360 B, ISC license), sha pinned at
discovery and re-verified before raster and in the manifest.

## 6–8. Planner / director / renderer

- Planner: REQUEST_OVERLAY eye (tag-evidence reason, window 1.0–5.0 s of 6.0 s,
  center 390,810,300 px, gold, HIGH confidence) — `controller_state` storyboard.
- Director: approved with recorded placement rationale (unambiguous
  center-stage proof, out of caption-zone convention).
- Renderer executed the approved op only: raster (Chrome headless, transparent
  300 px, inner SVG bytes verbatim — test asserts path/circle lines preserved)
  → `overlay_asset` (libx264). Renderer decided nothing.

## 9. Pixel verification (frames, not claims)

Box (390,810,690,1110). Same-timestamp final-vs-base differentials:
**inside t=3.0: 23217 px** (≥2000 ✓) · before t=0.3: 174 · after t=5.5: 133
(≤1500 ✓); gold support 21758 px. Director eyeball-confirmed: gold Lucide eye
over phone screen (frame `px_inside.png`). A first FAIL (naive gold-count
baselines hit by skin tones) forced the differential method — recorded, not
hidden. Two independent full runs produced **identical** differentials
(23217/174/133) — determinism evidence.

## 10. Manifest / provenance

`manifest.json` answers all 9 questions (asset+sha, why, planner, director,
renderer op+filter+encoder+raster record, timing, placement, hashes incl.
background source+offset, untouched flags) plus pixel record and performance.

## 11–12. Tests + regression

8/8 new tests pass (9.5 s): semantics-not-filename, contract valid/serializable,
4 rejection classes, asset rejections (missing/non-SVG/sha-drift), structured
missing-capability, raster determinism+byte-fidelity, real 2 s mini-render
pixel presence (diff ≥2000), 9-question manifest + sha re-check.
Regression: `test_rendering + test_execution + test_fs_ops +
test_production_stack` → **53 passed, 1 skipped** (pre-existing HW skip).

## 13. Render timing

Proof total **11.9 s**, 9 ffmpeg invocations (trim, fit, overlay, 6 frame
extracts). No stage re-encoded unnecessarily (single linear chain; no repair
loop). Existing `mh_index` cache reused for background discovery; **no segment
cache exists** (audit R7 stands — untouched by design).

## 14. Known limitations

- Raster depends on installed Chrome (now detected, still external); no pure-
  Python SVG fallback. Static overlays only (no per-frame animation — would
  need PNG-sequence + zoompan-style filter work). Position/size fixed per op
  (no keyframed motion). One icon per op (compositor loops can extend).
  Arabic text still libass-only. Overlay over bright content may need boxes
  (same lesson as captions).

## 15. Next blocker

Multi-graphic timelines: per-shot overlay lists in `contract_schema` shots'
`graphics[]` + a `compose_overlays` planner pass + segment-cache awareness so
graphic changes don't trigger full re-encodes. Then: camera push + overlay in
one shot (both executors exist now).

## Acceptance (13/13 PASS)

[x] Real Arsenal Lucide SVG discovered (eye, tag-evidence, sha-pinned)
[x] Selected semantically (token tag scoring, filename-only rejected)
[x] Planner requested it (logged decision + confidence)
[x] Director placed it (approval + rationale)
[x] Renderer executed it (overlay_asset, decided nothing)
[x] Visible in rendered pixels (23217-px differential + eyeball frame)
[x] Manifest records it (9 questions) [x] Provenance recorded (shas, license)
[x] Original byte-identical (q9 True) [x] No silent fallback (staged errors)
[x] Structured missing-capability failure (tested both stages)
[x] Deterministic smoke render succeeds (identical differentials ×2 runs)
[x] Regression tests pass (53+1skip; 8/8 new)
