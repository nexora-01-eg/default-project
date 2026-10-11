# DECISIONS.md — architectural decision log
## 2026-09-16 — Phase 1 scaffold choices
- **Stdlib-only core (`argparse`, `dataclasses`) instead of click/pydantic on day one.** Reason: no Python exists on this box yet; the scaffold must import on vanilla 3.11 the moment it installs, with zero extra wheels. click/pydantic arrive in Phase 3 per DEPENDENCIES.md.
- **`engine/` package instead of top-level `core/`.** Reason: avoids confusion with the spec's conceptual `core/` and gives clean imports (`engine.core.models`).
- **FFmpeg CLI over MoviePy/MLT.** Reason: determinism, speed, hardware-encoder access, scriptability. Documented in ARCHITECTURE.md §9.
- **faster-whisper over whisper.cpp as default STT.** Reason: pip-installable, word timestamps out of the box, CPU-efficient via CTranslate2; whisper.cpp kept as low-RAM fallback.

## 2026-09-16 — Phase 2 installer lessons (setup.ps1)
- **Never name a PowerShell parameter `$args`.** The automatic variable shadowed the bound value, so `Get-Version` silently invoked `ffmpeg` with no arguments (exit 1 + stderr under `$ErrorActionPreference="Stop"` became a terminating error, swallowed by `catch` → `$null`). Symptom was a misleading "not on PATH" failure for a working binary. Renamed to `$verArgs`; failure branch now distinguishes "not found" from "found but would not execute" with captured output.
- **setup.ps1 must stay ASCII-only.** UTF-8 em-dashes (no BOM) are decoded as ANSI by PowerShell 5.1 and broke parsing. Verified with `Parser::ParseFile` (must report 0 errors).
- **Gyan.FFmpeg winget package is portable** (binaries under `%LOCALAPPDATA%\Microsoft\WinGet\Packages\Gyan.FFmpeg_*\...\bin`, no PATH registration). Installer now adds that bin dir to USER PATH persistently (`Repair-FfmpegPath`).
- **MS Store Python shim can win PATH order in stale sessions.** `Test-RealPython` falls back to the well-known `%LOCALAPPDATA%\Programs\Python\Python311\python.exe`, and venv creation uses the discovered interpreter path, never bare `python`.
- **Installer merges registry PATH into the process** (`Refresh-Path`) so verification works in the same session; still, brand-new shells are the ground truth for PATH.
- Pre-existing `Python312` dirs were found on disk with stale PATH entries; Python 3.11 takes precedence by PATH order. Left untouched deliberately (out of scope).

## 2026-09-17 — Phase 3 analysis choices
- **Stay on dataclasses; no pydantic migration.** The Phase 1 note promised pydantic in Phase 3, but no schema bug has appeared and `asdict()` JSON is clean. Migration risk buys nothing today. Revisit only on a real validation failure.
- **One artifact per stage (`audio_analysis.json`), not per metric.** Volumes, loudness, and silence share one cache key and one ffmpeg-input lifetime; splitting them would triple cache bookkeeping for no debuggability gain.
- **loudnorm first-pass JSON for loudness** instead of hand-rolled RMS math: structured output (`input_i/tp/lra`), EBU R128 standard, zero extra deps. volumedetect stays for peak/mean dB (loudnorm does not report them).
- **`analyze_audio` takes an optional `MediaInfo`** so the orchestrator never runs ffprobe twice for one file; standalone callers get an internal probe fallback.
- **No-audio is data, not an error** (`audio_present: false`). Only missing files / missing or crashing ffmpeg raise.
- **FFmpeg 9 reports `-91.0 dB`, not `n/a`, for digital silence.** Parser keeps `None` only for literal `n/a`; tests accept floor values. Documented so nobody "fixes" the parser back.

## 2026-09-17 — Phase 4 rendering choices
- **Smoke-verify encoders, never trust `-encoders` listing.** Proven on this box: `h264_nvenc` is listed yet produces zero packets on the headless 940MX; `h264_amf` is listed with no AMD GPU. List-only selection would have picked broken encoders. Result cached in `.cache/encoders.json`, keyed by ffmpeg version.
- **Re-encode the EDL join by default** (`render_keep`), `fast_copy` opt-in. Same-codec stream-copy joins can still glitch A/V sync at boundaries; correctness first per the brief, speed on request.
- **Reuse `QCReport`/`QCCheck` for output validation** instead of a new schema — Phase 13 QC will extend the same model.
- **Re-encode preset `veryfast` as Phase 4 default.** Speed-first while the engine is under test; quality policy moves to template/preset config in Phases 12/14.
- **`apply_vf` stream-copies audio.** Video-only filtering must not touch (or re-encode) the audio track.
- **Timestamps validated in Python before ffmpeg spawns.** `ValueError` for programmer errors (negative, inverted, out-of-range, empty EDL); `FfmpegError` only for genuine ffmpeg failures.

## 2026-09-17 — Phase 5/6 speech choices
- **`analyze` stays model-free; `transcribe` is standalone.** `analyze` must remain fast and offline-safe, so it never downloads weights. `transcribe <media>` creates (or `--project`-attaches) a project and follows identical project/cache/JSONL conventions — same architecture, separate command.
- **No silent downloads, ever.** Uncached model + no `--allow-download` = loud error naming size, source, and the `download-model` command. `download-model` verifies `model.bin` presence.
- **CUDA counts as available only if verified usable.** `cuda_usable()` = device count > 0 AND `nvidia-smi` compute capability ≥ 6.0. This box's 940MX (CC 5.0) counts as a device yet rejects all CUDA compute types — auto resolves to cpu/int8 (~7x realtime on tiny). Explicit `cuda` still allowed, with logged cpu fallback.
- **No-audio / fully-silent short-circuit before model touch.** Saves downloads, loads, and inference; `skipped_reason` records why. Phase 3 `non_silent[]` drives both the skip and the `non_silent` spans mode (timestamps shifted back, alignment-tested).
- **New `TranscriptWord`/`WhisperSegment`/`Transcript` models** instead of reusing generic `Word`/`TranscriptSegment` (different field contract per spec: `word`/`probability`). Generic ones stay untouched for Phase 8/10 unification.
- **Fillers are annotation-only** (`engine/analysis/fillers.py`, en+ar sets, prefix-matched, punctuation/case-insensitive). Deletion is Phase 8+.
- **`extract_audio` gained additive kwargs** (`sample_rate`, `channels`, `start`, `duration`; seeking after `-i` for exact offsets) rather than a parallel helper — one gateway, no duplication.
- **SAPI-synthesized speech fixtures** (offline built-in Windows voices) for real-inference tests: zero new deps, zero network, zero copyrighted audio. FAKE-model tests are labeled plumbing-only and never cited as speech proof.

## 2026-09-17 — Phase 7 scene choices
- **PySceneDetect 0.7.1 API, not 0.6 patterns.** `VideoManager` is gone
  (`open_video` + `SceneManager`); `.seconds`/`.frame_num` replace deprecated
  getters. Pinned by behavior + `detector_version()` in the cache key.
- **Empty scene list normalizes to one `[0, duration]` scene** (probe values).
  0.7.x returns `[]` on zero cuts; that is data, not an error.
- **Probe is the timeline truth**, never the detector's fps/duration.
  Timestamps stay full-precision (no rounding); validation mirrors the
  speech-timestamp pattern (`timeline_issues` stored, not dropped).
- **ThresholdDetector semantics recorded honestly**: fades to/from black
  only — bright hard cuts do not fire it, `add_final_scene=False` drops
  trailing fades. An early `==3` assumption was refuted by execution and
  corrected (see test). Never adjust fixtures/asserts to match guesses.
- **Fallback is recorded, not silent** (`fallback_from`, note, JSONL), and
  attempted exactly once. `scenes` is standalone; `analyze` untouched.
- **Resolved (not raw) threshold scopes the cache key**, with method-specific
  detector versions (pyscenedetect vs ffmpeg) so upgrades invalidate correctly.

## 2026-09-17 — Phase 8 edit-decision choices
- **Replaced the unused Phase 1 `EditDecision{keep,remove}` placeholder**
  with the per-decision schema. Zero usages existed (verified by grep);
  Phase 4 `render_keep` consumes keep spans, derivable from any EDL.
- **Conservative by default**: KEEP unless a configured rule fires; tiny
  pauses kept silently, padding can veto a removal, speech overlap vetoes
  filler cuts. `removal_ratio` stays near 0 on ordinary content.
- **Filler-vs-silence conflicts resolve by subtraction** (two removal rules
  only — no general sweep until a third rule lands).
- **Scene splits preserve traceability**: removals never straddle boundaries;
  merging requires same reason + same scene.
- **Audio-only EDL synthesizes the degenerate single scene + warning**
  (Phase 7 zero-cut precedent); video projects without `scenes.json` fail
  loudly. `detect_scenes` itself still refuses audio files.
- **Project ids now carry microseconds.** Same-second `create_project`
  collisions silently reused directories and corrupted `input_path` —
  caught by Phase 8 tests, fixed at the source (not papered over in tests).

## 2026-09-17 — Phase 9 execution choices
- **Execution lives in `rendering/execution.py`, gateway untouched except one
  gap**: `concat(reencode)` used `-c:a aac` unconditionally and broke on
  audio-less sources; it now probes the first part and uses `-an` when
  absent (audio path byte-identical, existing tests green).
- **`render` is EDL-first, legacy preserved**: EDL artifact present →
  execute it; `--keep` forces range mode; `--edl` forces EDL mode (missing →
  exit 2); otherwise legacy full transcode. No Phase 4 test changed.
- **Single-keep renders `direct` (trim→copy), multi-keep `concat`.**
  Fewer generations where safe; manifest records the strategy.
- **Reuse revalidates before hitting**: manifest match + file exists +
  re-probe within tolerance; corruption re-renders. Identity excludes
  wall-clock (`generated_at`/`cached` never hashed).
- **Start-time/sync fields added to `MediaInfo`** (`video_start_time`,
  `video_duration`, per-stream `start_time`) — additive, suite green.
- **Audio-only sources refused explicitly** (no video stream to encode);
  no silent behavior anywhere in the render path.

## 2026-09-17 — Phase 10 intelligence choices
- **Refinement only ever KEEPs more by default** (UNSAFE revert; strict adds
  CAUTION). Repetition removal is opt-in and re-tiles + re-validates; any
  re-validation failure raises instead of shipping a broken EDL.
- **SAFE verdicts still emit a `safety_summary` evidence entry.** Added
  after tests showed clean removals carried zero evidence — traceability
  applies to every non-trivial decision, not just flagged ones.
- **`validate_edl`/`edl_hash` imported from Phase 9 execution** (validation
  only — the render path is untouched and uncalled). No duplication, no
  behavior change to Phase 9.
- **Sentence inference limitation recorded, not solved.** Word tokens rarely
  carry punctuation (`sentence_signals.coverage`); placement prefers gaps,
  silence, and boundaries. Repetition is exact-match only (no fuzzy).
- **Three test-data assumptions refuted by execution and corrected**:
  speech inside a "clean" removal is UNSAFE (safety net working, not a bug);
  2-word repeats don't meet min_words=4; cache comparisons must exclude the
  `cached` flag. Fixtures were fixed, never the engine.

## 2026-09-17 — Phase 11 visual choices
- **No vision models downloaded, none required.** Audit: no Haar XMLs, no
  weights, no torch/mediapipe; faces/objects/embeddings report `unavailable`
  with reasons. User-supplied paths are the only activation route.
- **Frame-exact sampling (quantized, EOF-safe).** A `%.3f` seek rounding
  dropped boundary frames (found live: blue sampled inside a red scene);
  gateway `extract_frame`/`trim`/`extract_audio` now format seeks at full
  float precision (identical output for all existing round inputs — full
  suite green), and the sampler quantizes to frame starts + avoids the
  final 2-frame window.
- **Static spans need hash AND histogram agreement.** Flat red vs flat blue
  share dHash 0; correlation separates them (verified live).
- **Flat-field luminance honesty:** pure red vs CSS green are ~identical in
  grayscale (76 vs 75) — reported as measured, not "fixed".
- **Farneback has a ~0.02 noise floor** on identical frames (asserted, not
  zero-clamped); absdiff is exact.
- **Framing without faces is `unknown`** (heuristic cutoffs documented for
  when a detector exists); detection is geometry-only by architecture —
  no identity/attributes possible.
- **Agent worker shells have flaky ffmpeg PATH** (parent env frozen at spawn);
  always prepend the ffmpeg `bin` dir in tool commands needing it.

## 2026-09-17 — Phase 12 editor-brain choices
- **Refinement of scope, not of EDLs.** The brain validates base REMOVEs,
  plans mitigations/B-roll, and cross-checks the refined EDL — it mutates
  no timeline and renders nothing. Disagreements become conflicts, never
  silent overrides.
- **Wordless segments are `unknown`, never positional labels.** An early
  version labeled a silent opening `hook`; corrected with the reasoning
  recorded — position without words is not understanding.
- **`evidence_type` (not `metric`) carries the factor category.** A filter
  bug comparing the wrong field silently disabled conflict detection;
  caught by tests asserting conflicts exist, not just verdicts.
- **Cache keys include a source-code hash.** Mid-session engine edits were
  served stale plans from a policy-identical cache; code hash now
  auto-invalidates (applies to this stage going forward).
- **Safety vetoes are absolute** (UNSAFE reject, CAUTION downgrade) and
  `--aggressive` is documented to never override them — it only shifts
  tolerances and density styles.
- **B-roll topics are word frequency, not semantics** (stated in every
  topic field's provenance); music/noise are `later_phase` with explicit
  "unmeasured" evidence rather than guesses.
- **No combined scores.** Plan-level summaries are counts; every number on
  a recommendation is a labeled component with its evidence.

## 2026-09-18 — Phase 13 execution choices
- **Cutaway overlays keep base dialogue; replacement honors audio_mode.**
  Overlay = fitted muted video muxed under the source's own audio span
  (dialogue can never be gapped by a cover shot). Replace + mute fills
  generated silence explicitly; replace + original carries asset audio.
  `mix`/`duck` are rejected at approval (unsupported, never faked).
- **One uniform concat re-encode** (correctness first); `direct` shortcut
  kept only on the untouched Phase 9 path. Temp workdirs are removed on
  success and retained with their path in the error on failure.
- **Assignment spans are request spans, not opportunity spans** (partial
  windows allowed via containment matching; executed span always explicit).
  Found live: recording the opportunity span rendered 12 s from a 4 s map.
- **Placement proof compares asset AND base** (dhash + hist): match-asset
  only → pass; both → accepted-with-warning; neither → fail. Ambiguity is
  data, not an error.
- **Approval loads intel/visual from their real locations** (`edit/`,
  `visual/`). The brain previously looked only under `analysis/`, silently
  running without safety/visual inputs — caught by the Phase 13 real chain,
  fixed at the source with a regression test.
- **`-preset` only reaches software encoders.** `h264_qsv` rejects
  `ultrafast` (verified failure); HW uses its own defaults. Existing
  callers unaffected (full suite green).
- **mjpeg single-threaded in `extract_frame`.** The frame-threaded encoder
  init races intermittently in this build (exit 4294967274); output pixels
  unchanged, visual/QC callers stabilized.

## 2026-09-18 — Phase 14 caption choices
- **Transcript ≠ Caption Plan ≠ Approved Caption Execution.** Three
  artifacts, two explicit approvals (plan + captions); base approval never
  mutated by caption work.
- **Stale Phase 1 template style names fixed at the source**
  (`clean_bottom`→`clean`, `karaoke_center`→`social`); unknown styles fail
  loudly, never silently remapped. Karaoke stays out of scope.
- **Burn is a post-render ASS pass** (audio stream-copied, one extra
  generation, QC-gated) — not a filter woven into base rendering.
- **Visibility QC is calibrated, not asserted**: band top-5% diff 28.8 vs
  ~0.2 re-encode noise floor, measured live on real frames.
- **Arabic STT explicitly unverified** (no ar TTS voice on this box);
  Arabic plan/render tests use labeled synthetic transcripts + real glyphs
  through libass shaping — never presented as transcription proof.
- **Font coverage is tiered honesty** (valid/uncertain/invalid) without
  fontTools; uncertain proceeds with a recorded warning, invalid fails.

## 2026-09-19 — Phase 15 visual-polish choices
- **Band sampling re-decodes via gateway** (`extract_frame` to temp) instead
  of trusting Phase 11 frame filenames (skips would misalign indices).
- **Caption anchor derived from position** (`CaptionPlacement.__post_init__`)
  so model objects can never disagree with themselves.
- **Adaptation renders**: outline via inline `\bord`, box via a second
  `DefaultBox` style; recorded patches are the contract, per-event ASS the
  proof. Unadaptable states record instead of changing.
- **Emphasis is inline color/bold overrides** (no timing change, no
  animation); >30% capped with the earliest kept; fake-face tests cover the
  face path the real adapter cannot (UNAVAILABLE, nothing downloaded).
- **Input mutation caused phantom approval drift**: `build_visual_plan`
  stamped `cue["_visual"]` onto caller dicts, poisoning the stored plan
  hash vs the pristine file. Removed + regression test; hashes now cover
  only file-persisted content.
- **Cache keys carry code hashes** (same Phase 12 lesson, applied to the
  visual-caption stage) so engine edits auto-invalidate.
- **Visibility metric calibrated live**: band top-5% diff 28.8 vs ~0.2
  re-encode noise floor; whole-frame means dilute the signal 140A- and are
  not used.

## 2026-09-19 — Phase 16 caption-pacing choices
- **Informational scene defaults yield to specific actions** in ranking:
  a whole-scene KEEP default must never veto an EDL-grounded TRIM or an
  evidence-backed SPLIT/CHANGE on a sub-span (recorded as rejection, not
  silent drop).
- **Case-A pair coexists**: CHANGE_VISUAL + ADD_CUTAWAY_OPPORTUNITY on the
  same span are complementary by design, kept side by side; exact-duplicate
  overlaps merge, genuine conflicts keep the safest action, exact ties keep
  the first (deterministic).
- **Safety breaks action-rank ties**: UNSAFE TRIM vs SAFE TRIM on the same
  span keeps SAFE (action rank alone could not distinguish them).
- **Partial cue overlap is an invalid mapping**: an EDL REMOVE cutting
  through a cue boundary downgrades to REVIEW (would split a rendered cue).
- **Declared-but-unemitted signals were a grounding hole**:
  SCENE_BOUNDARY_OPPORTUNITY and LOW_CAPTION_DENSITY are now emitted by
  their own extractor so every recommendation cites ≥1 emitted signal.
- **Zero is not "no run"**: `run_start or run_prev` treated a 0.0 run start
  as falsy and suppressed LONG_SPEECH_BLOCK; explicit None checks.
- **Cache-hit path no longer stamps `cached` into the artifact**: the flag
  lives only on the result object, so stored plans stay canonical and
  hit-vs-miss payloads compare equal.
- **Approval drift checks bind all 8 inputs + style + plan hash**; wall-clock
  (`approved_at`) lives only in the approval file, never in hashed content.

## 2026-09-19 — Phase 17 pacing-execution choices
- **Two approvals, never merged**: intelligence approval and execution
  approval are separate artifacts with separate CLIs; only explicitly
  selected recommendations execute, nothing is approved implicitly.
- **Derived EDL by interval subtraction** (KEEP-all except approved TRIMs,
  `px_NNNN` ids, provenance in `metadata`): the base EDL is never mutated
  and unrelated base REMOVEs are not carried into this execution.
- **EDL containment + base-approval exclusion**: a TRIM outside any base
  REMOVE is rejected, not reinterpreted; when `approved_edit_plan.json`
  exists, removals it left unapproved stay unapproved.
- **Partial cue overlap blocks loudly** (`PARTIAL_CAPTION_OVERLAP`): Phase 14
  drops straddling words by design, so the adapter refuses the op instead of
  silently deleting part of a cue. Fully contained cues drop explicitly with
  `SOURCE_RANGE_REMOVED` word evidence.
- **SPLIT is boundary metadata** (no media delta); visual actions are NOOP
  metadata. Explicitly selecting a planning-only action fails instead of
  downgrading silently.
- **Visual plan present-but-unapproved fails** (no silent standard-caption
  fallback); preview runs the existing `_visual_qc_checks`, failures block
  as `VISUAL_CAPTION_REVIEW_REQUIRED`; split sub-cues inherit placements via
  the existing base-id lookup.
- **Caption mode follows the caption approval** (no second caption config);
  `approval_state`/`approved_at` are excluded from all execution hashes so
  `APPROVED -> EXECUTED` never invalidates the cache.
- **Render reuse is manifest-scanned with re-probed duration** (never
  filename trust); preflight reports `AVAILABLE / MISSING` and missing
  binaries fail before any render with no `EXECUTED` state.
