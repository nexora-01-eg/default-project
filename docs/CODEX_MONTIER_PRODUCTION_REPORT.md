# CODEX / Al-Montier production report

## Status

`CREATIVE_CAPABILITY_BLOCKED`

This is not a claim that no historical video exists. An 82.64-second 1080×1920/30 MP4 exists at `projects/narrated_tech_v1_20260923/renders/narrated_tech_hot_20260923_211705.mp4`, but a fresh independent review and technical verification could not run because local FFprobe is absent at its configured path. More importantly, the only available voice produced two spoken lines over 77 seconds, so the completed artifact does not satisfy the requested full voice-first narration standard.

## Production evidence

- Topic: `إزاي الذكاء الاصطناعي بيغيّر صناعة الفيديو؟`
- Historical render: 82.64 s, 1080×1920, 30 FPS, H.264/AAC, 18 planned shots.
- Voice: Piper `ar_JO-kareem-medium`; `TEMPORARY_ARABIC_TTS`, `NOT_EGYPTIAN`. VoiceTut Mohamed remains `SPACE_STILL_BLOCKED`, not retried.
- Captions: RTL ASS, burned-in, four narration cue fragments and six keyword overlays. They are segment/midpoint approximations, not verified word timing.
- Motion: rise/fade/slide ASS events plus static punch-ins. No general animation engine.
- Transitions: purposefully hard cuts only. No claimed fade/wipe/zoom system.
- B-roll: nine locally selected Arsenal clips; originals untouched; provenance remains `UNKNOWN/CAUTION`; foreign UI assets were rejected.
- Music: Aitech, CC-BY; documented -6 dB music bed under narration. No SFX was inserted because no verified purpose-matched timed source was available.
- Historical audio result: -21.2 dB mean, -2.0 dB peak. Fresh measurement is blocked by FFprobe.

## Review, QC, and repair

The historical manifest reports a 14/14 rules-based creative review and one audio-gain repair. The current independent reviewer rerun is blocked, documented in `qc/independent_review_rerun.json`; this supersedes any fresh-pass claim. Repair routing attempted the render/QC infrastructure path and found no local `ffprobe.exe`, recorded in `repair_history.json`. A human listener/reviewer is still required for voice intelligibility and caption/visual quality.

## Tests

The existing test suite was invoked, but this host's command capture returned no suite summary. The newly added controller tests are syntactic/unit-level and should be rerun once the local Python/FFmpeg environment is healthy. No test result is represented as a successful regression run without output evidence.

## Exact next action

Restore an approved local FFmpeg/FFprobe installation or set `FFPROBE_PATH` to an existing executable; run `python -m engine.cli doctor`; run the existing suite and a short render smoke test; then rerun the independent reviewer. Separately, supply an approved Egyptian local voice or recorded narration before attempting a true full-script voice-first production.
