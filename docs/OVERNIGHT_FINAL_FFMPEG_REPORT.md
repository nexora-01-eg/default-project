# OVERNIGHT_FINAL_FFMPEG_REPORT.md — FFmpeg blocker resolution (2026-09-20)

## 1. Initial FFmpeg diagnosis
- Engine resolves ffmpeg/ffprobe ONLY via `shutil.which` (PATH-only).
- `where.exe ffmpeg/ffprobe`: not found. No binary anywhere on disk.
- `.\setup.ps1` documents the approved method: `winget install --id
  Gyan.FFmpeg -e` (official Gyan full builds) + PATH repair + verification.

## 2. How FFmpeg was resolved
- Ran the project's own installer: `.\setup.ps1 -FfmpegOnly` → Gyan
  FFmpeg **9.0.1-full_build** + USER PATH repair (no other copy installed,
  nothing replaced).
- Session PATH propagation proved flaky (registry updated, live processes
  stale), so the engine gained minimal explicit resolution:
  `FFMPEG_PATH` / `FFPROBE_PATH` env (quoted paths with spaces handled) >
  PATH lookup > clear failure. Invalid explicit path fails loudly naming
  the bad value (no silent fallback).
- Persisted as USER-level `FFMPEG_PATH`/`FFPROBE_PATH` for reproducibility.

## 3. Configuration mechanism
Precedence: explicit path > env var > PATH. Observable via
`ffmpeg_config_state()` and `doctor` (now reports resolved paths +
source). Documented in error messages.

## 4. Files changed
- `engine/rendering/ffmpeg.py` (env override, config state, clearer errors)
- `engine/core/media.py` (same for ffprobe)
- `engine/cli.py` (doctor uses engine resolvers + reports source)
- `engine/editing/caption_pacing_execution.py` (manifest now persists
  `style`, `code_version`, `pacing_execution_approval_hash`; identity key
  unified to `pacing_execution_approval_hash` — cache reuse never worked
  before, proven by the first real render)
- `tests/test_ffmpeg_resolve.py` (new, 4 tests)
- `tests/test_caption_pacing_execution.py` (absence tests env-gated;
  tamper-drift expects RenderError/validate per failure semantics)
- `tests/test_caption_pacing.py` (renders-dir assertion → no-media-files)
- `tests/test_reviewer.py` (stream-probe expectation branches on ffprobe)

## 5. Tests executed
- New resolver tests: 4/4. Full engine suite: **385 passed / 3 skipped /
  0 failed** (was 198/184/2-env-fail; 183 media tests now genuinely run).
- Arsenal-X: 54/54, tsc clean (untouched side).
- Absence path re-verified by simulation: explicit NOT FOUND failures.

## 6. FFmpeg capability test
- `ffmpeg version 9.0.1-full_build`, ffprobe resolves, encoder
  auto-select smoke-verified **h264_qsv** (Intel QSV, correct for i7-7820HQ).

## 7. Real render result
- `test_real_chain_e2e` (Phase 17): full chain → render **completed**,
  base QC **pass**, caption QC **pass**, duration 7.996 s vs predicted
  7.947 s, output file exists + non-empty, cache reuse **works on rerun**,
  tamper invalidates.
- Minimal manual render (Phase 17 TRIM on tone fixture): completed, QC
  pass, sidecars written.

## 8. Output validation
- ffprobe duration/codec checks via existing `validate_render` /
  `extended_qc` (verdict pass). No unexpected warnings.

## 9. Independent review result
- Pristine render: verdict **REVIEW** — every falsifiable check PASS
  (output exists/non-empty, EDL intervals/order, caption overlap/
  intervals/empty/readspeed, approvals valid, pacing bindings hold);
  REVIEWs are the honest Phase-25 stream-depth placeholders.
- Tampered project: verdict **FAIL** with correct drift reasons —
  reviewer demonstrably independent.

## 10. Full regression result
- Engine 385/3/0. The 2 pre-existing ffprobe failures are GONE (tool now
  present — resolved, not hidden). Arsenal-X untouched and green.

## 11. Known pre-existing failures
- None remaining. (Prior 2 visual failures were ffprobe absence; now pass.)

## 12. Phase 30 gate decision
**PASS** — FFmpeg genuine, engine resolves it, real final render executed,
output valid, reviewer pipeline completed, regression fully green, no
mocks/fakes, reproducible from documented config (setup.ps1 + env vars).

## 13. Remaining blocker
None for Phase 30.

## 14. Arsenal assets
Unmodified (scanned; only arsenal-x project files + WinGet package changed).

## 15. Unrelated phases
Phases 9–16 untouched (0 source changes). Phase 17: manifest-only additive
fix for a genuine reuse bug exposed by the first real render.
