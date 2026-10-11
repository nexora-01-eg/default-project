# PHASE 27–29 REPORT — Controller, Director, Memory (2026-09-20)

Status: **PASS**

## What was built (Al-Montier engine, new `engine/autonomy/` package)
- `director.py` (P28): `plan_production()` — deterministic 3-act story
  split, visual beats, topic B-roll packs, caption/audio/pacing strategies,
  asset requirements shaped like Arsenal-X requests, risk list. Pure,
  planning-only.
- `memory.py` (P29): per-project append-only `memory/events.jsonl`
  (`remember`/`recall`); kind allowlist; refuses secret-like payloads.
- `controller.py` (P27): injected-runner state machine, per-phase
  checkpoint (`autonomy/state.json`), resume skips OK phases, crash
  isolation per phase, stale-terminal recovery (2 real bugs found by the
  resume test during development), `recover()` for restart.
- No renders, no downloads, no engine modifications outside the new package.

## Verification
- 4 tests (director content/determinism/validation, memory roundtrip +
  secret refusal, controller stop/resume/recover, crash isolation).
- Development-time resume bugs fixed via tests (stale BLOCKED blocking
  progress; old entries shadowing latest status).

## Limitations
- Controller runners for render phases honestly report BLOCKED without
  FFmpeg; P30 wires real runners.
- Director packs are keyword-small (English); taste-level planning is future.
