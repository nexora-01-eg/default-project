# DEVELOPMENT.md

## Environment

- Windows 10, PowerShell 5.1. All paths may contain spaces — always use arg-lists, never shell strings.
- Python 3.11 in `.venv` (created by `setup.ps1`). Never commit `.venv/`, `projects/`, `output/`, `.cache/`.

## Workflow

1. Pick a phase from `DEPENDENCIES.md`.
2. Implement + add/extend tests in `tests/`.
3. Run `pytest` — a phase is done only when tests pass on this machine or a dated blocker note exists.
4. Update docs (`ARCHITECTURE.md`, `PIPELINE.md`, `docs/DECISIONS.md` for major changes).

## Conventions

- Every stage: JSON in, JSON out. Never modify sources.
- Log every run to `projects/<id>/logs/*.jsonl` via `engine.core.logging_utils`.
- Encoder probing order: `h264_nvenc` → `h264_qsv` → `h264_amf` → `libx264`
  (smoke-verified, never list-only; see `docs/RENDERING.md`).
- PowerShell scripts must stay ASCII-only (PS 5.1 misdecodes UTF-8 without BOM).
- Stale shells: agent/tool sessions inherit a frozen PATH. Tests that need
  ffmpeg must not assume PATH — `scripts/make_test_media.py` uses
  `shutil.which`, and local runs may need the ffmpeg `bin` dir prepended.

## Test fixtures

- `python scripts\make_test_media.py --all` builds `tests/fixtures/` (idempotent,
  skips existing). WAV = sample-exact, MP4/AAC = ±50 ms tolerance in asserts.
- Cache-persistence across runs is BY DESIGN (`.cache/`). Tests needing a cold
  cache must copy the fixture to `tmp_path` (unique mtime/size → unique key).
- Never commit `tests/fixtures/` output, `projects/`, `.cache/`, `.venv/`.
- Speech tests: `test_speech_unit.py` runs offline with zero downloads;
  `test_speech_real.py` needs the tiny model (`video-engine download-model tiny`,
  one-time ~75 MB) and Windows SAPI voices (built-in) to synthesize fixtures.
- HF model cache lives outside the repo (`~/.cache/huggingface`); never commit it.
- Scene fixtures: `scenes_3x2s.mp4` (exact `[0,2,4,6]` cuts), `static_3s.mp4`,
  `short_05s.mp4`, `fade_3s.mp4`. ThresholdDetector does NOT fire on
  bright-to-bright cuts — write fade asserts against measured behavior.
- Project ids carry microseconds (same-second creates no longer collide).
  Tests asserting cold caches must still salt content-derived keys
  (`time.time_ns()`), since `.cache/` persists across runs by design.
- Render tests must assert on probed output characteristics (duration,
  streams, manifest fields) — never byte-identity of MP4s. Corrupt-output
  reuse tests may truncate files inside `tmp_path` or project `renders/`
  (both disposable); never touch `input/` or fixtures.
- Intelligence tests must exclude wall-clock `processing_s` from determinism
  comparisons. SAFE verdicts carry a `safety_summary` evidence entry by
  design — assert its presence, not its absence.
- Visual tests: synthetic numpy images give exact metric expectations;
  checker period is 2 (roll by odd counts); Farneback has a noise floor
  (~0.02) on identical frames; `ffmpeg` on PATH is flaky in agent worker
  shells — always prepend the ffmpeg `bin` dir in commands needing it, and
  keep the `shutil.which` skip-guards.
- Brain tests assert verdict vocabularies exactly; wordless segments are
  `unknown` (never positional labels); cache comparisons exclude `cached`;
  engine source hash auto-invalidates the `editor_plan` cache on code edits.
- Plan execution tests use hand-written approvals with REAL asset hashes
  (`file_pin`); fake `"h"` hashes fail validation by design. Approval tests
  never render; B-roll/render tests assert probed output, never byte-identity.
- Caption tests: plan/ar batteries are ffmpeg-free; render tests need the
  SAPI fixture (built on demand). Arabic STT has no local voice — Arabic
  tests use labeled synthetic transcripts + real glyphs, never STT claims.
- Inline `python -c` breaks under PowerShell quoting: use script files.
- Visual-caption tests exclude wall-clock `processing_s` from determinism
  comparisons; warmed caches need unique-key materials (`tmp_path` copies);
  cross-test file dependencies are forbidden (each render test builds or
  reuses idempotently); metric thresholds are calibrated live, never guessed.
