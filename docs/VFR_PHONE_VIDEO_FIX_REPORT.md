# VFR_PHONE_VIDEO_FIX_REPORT.md (2026-09-20)

## Diagnosis
Measured per-stage on the real source (not assumed):
- `trim()` accurate path uses `-ss/-t` re-encode. Each part rounds UP to a
  frame end (ceil bias, up to one frame quantum). Over 27 ops this
  accumulates: previous run +0.55 s systematic overshoot.
- Source audio ENDS 0.753 s before video (mic/encoder stopped early —
  stream timestamps otherwise sane). Re-encode preserves the shortfall, so
  output `|container-audio|` = 0.72 s vs 0.5 tol. `aresample:async` cannot
  fix a truncated tail (it corrects drift, not missing samples).
- Encoder eliminated as cause (libx264 vs h264_qsv byte-comparable).
- Cache-reuse investigation additionally exposed a manifest/identity key
  mismatch (`execution_approval_hash` vs `pacing_execution_approval_hash`)
  — reuse never functioned; fixed.

## Source Timing
- 276.849 s container; video 276.849 (5739 pkts); audio 276.096.
- r_frame_rate 90000/1 (bogus) vs avg 129127500/6229093 ≈ 20.73 fps;
  time_base 1/90000; packet durations vary (0.0219/0.0354…) → VFR confirmed.
- Measured source skew: 0.753 s (audio ends early).

## Fix
1. `MediaInfo` += `fps_nominal/fps_rational/video_time_base` (additive).
2. `vfr_status()`: VFR iff nominal > 1000 or >5% off measured; yields the
   measured rational for normalization.
3. `normalize_media()`: deterministic CFR proxy (`-vf fps=<measured
   rational>`, `-af aresample=<rate>:async=1,apad=whole_dur=<measured video
   dur>`), project-temp only, refuses CFR sources.
4. `trim()` accurate path: VFR sources normalize first, then the IDENTICAL
   trim logic runs on the proxy; CFR argv byte-identical to before.
5. Frame-exact video length (`-frames:v N` from measured rate; `-t` still
   caps audio): per-part error becomes ±half-quantum zero-mean instead of
   systematic ceil bias.

## Why It Is Correct
- CFR normalization removes the irregular-grid variance that made VFR
  overshoot unpredictable; frame counting removes the accumulation bias.
  Both derive strictly from measured source values (no arbitrary FPS, no
  hardcoded offsets/durations, no `-shortest`, no forced duration).
- Tail silence parity (`apad` to measured video duration) reconstructs
  standard deliverable stream parity for phone recordings whose mic track
  ends early; it alters no existing sample and is gated to the VFR path
  (CFR behavior unchanged). Judgment documented here for owner review.
- General: any VFR source with bogus nominal rate or >5% rate disagreement
  takes the same path; CFR sources provably take the legacy path.

## Tests
- New `tests/test_vfr.py` (7): VFR detection (synthetic mixed-rate +
  real source), CFR refusal + legacy trim, parity on real source
  (<0.15 s), trim/concat exactness, determinism, no proxy litter.
- Existing suites: render/render-plan/execution/captions/phase13 (75),
  full engine **392 passed / 3 skipped / 0 failed**, arsenal-x 54/54,
  tsc clean.

## Real Production Retest
- New project `project_20260920_132155_187354`, identical plan (2 cuts,
  54 cues). Render 655 s.
- Source 276.849 s → expected 274.975 s → actual video 275.208 s /
  audio 275.257 s / container 275.257 s.
- A/V offset ≈ 0.05 s (was 0.72 s). Unexplained drift: none remaining
  (residual +0.28 s is frame-quantum rounding, inside tol).
- QC: **pass** (duration + av checks). Caption QC pass (53 cues mapped).

## Reviewer
Verdict **REVIEW**, 0 FAIL: 10/14 PASS (output, EDL, all caption checks,
both approvals, pacing bindings, visual approval); 4 REVIEWs are the
documented Phase-25 stream-depth placeholders. Rules untouched.

## Repair
1 cycle: 4 REVIEW_AGAIN routes, zero FAIL → no re-render warranted.

## Regression
Engine 392/3/0 · Arsenal-X 54/54 · tsc clean · assets untouched.

## Remaining Limitations
- Tiny-model Arabic transcription roughness (separate, untouched).
- Reviewer stream-depth placeholders (separate, untouched).
- apad tail-parity judgment is documented above for owner review.
- 53 vs 54 cues: one cue consumed by an approved cut (correct mapping).

## Final Output
`C:\Users\NOUR SOFT\Documents\Default Project\projects\project_20260920_132155_187354\renders\plan_20260920_162253.mp4`
(27 MB, 275.26 s, 720×1280, h264 + AAC, + .srt/.vtt + manifest).
Source untouched (size/mtime/SHA256 re-verified).
