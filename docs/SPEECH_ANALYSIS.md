# SPEECH_ANALYSIS.md — Phase 5/6 local Whisper STT (`engine/analysis/speech.py`)

Local-first transcription on the installed `faster-whisper 1.2.1`
(CTranslate2). No cloud, no paid API. Offline whenever the model is cached.

## Pipeline

```
probe -> Phase 3 audio/silence profile -> explicit model check -> load
-> transcribe -> Transcript -> analysis/transcript.json
```

- **Audio prep reuses the FFmpeg gateway** (`extract_audio` → 16 kHz mono WAV;
  span extraction uses output seeking for sample-accurate offsets).
- **No-audio / fully-silent short-circuit** before any model touch: no load,
  no download attempt, `skipped_reason` set (`no_audio` / `fully_silent`).
- **Spans modes:** `full` (whole timeline, native timestamps) is the default;
  `non_silent` transcribes each Phase 3 span separately and shifts word/
  segment timestamps back by the span start (verified by alignment test).

## Models (explicit download only)

Source: Hugging Face Hub `Systran/faster-whisper-*`, fetched on demand.
Weights derive from OpenAI Whisper (MIT); converted CTranslate2 checkpoints —
see each HF repo for current terms.

| Model | Size | Note |
|---|---|---|
| tiny | ~75 MB | tests / draft |
| base | ~145 MB | fast CPU |
| small | ~466 MB | **default** (spec example) |
| medium | ~1.5 GB | needs patience on 4C CPU |
| large-v3 | ~3 GB | VRAM/RAM heavy; CPU-only untested here |

`video-engine download-model <name>` fetches + verifies (`model.bin`
present). `transcribe` refuses uncached models unless `--allow-download`.
`analyze` never downloads models (stays lightweight by design).

## CPU/GPU behavior (verified 2026-09-17, 940MX CC 5.0)

`device=auto` uses CUDA only if `cuda_usable()`: device count > 0 **and**
`nvidia-smi` compute capability ≥ 6.0. This box reports a CUDA device but
rejects every CUDA compute type (float16/int8…) — so auto resolves to
**cpu/int8** (~7x realtime on tiny: 8 s audio in ~1.1 s; load ~1.6 s).
Explicit `cuda` that fails falls back to cpu with a logged `fallback` note;
unknown devices/compute types raise `SpeechError` before any load.

## Transcript schema (`Transcript` model)

`language, language_probability, language_mode (auto|forced), duration,
segments[{id,text,start,end,duration,words[{word,start,end,probability}]}],
segment_count, word_count, fillers[{word,start,end,segment_id}],
non_silent_spans, non_silent_coverage, timestamp_issues,
skipped_reason, engine{model,device,compute_type,fallback},
performance{media_duration_s,processing_s,realtime_factor}, config_used`.
All floats rounded to 3 decimals (deterministic JSON).

## Fillers (`engine/analysis/fillers.py`)

Annotation only — never deletion (Phase 8+). `FILLER_WORDS` maps ISO-639-1
codes (`en`, `ar`, …), prefix-matched, case-insensitive, punctuation-stripped.
Unknown language → `[]`.

## Caching

Stage key `transcribe` covers file identity + model + language + device +
compute + word-timestamps + spans + silence thresholds. Same params →
`cached: true`; any change → fresh entry. Reuses the shared `analyze_audio`
cache entry when `analyze` ran first (no recompute).

## Timestamps

Validated per segment (`start >= 0`, `end > start`) and per word (inside
segment ±0.5 s tolerance); overshoot >1 s past duration reported. Issues are
stored in `timestamp_issues`, never silently dropped.

## Testing

- `tests/test_speech_unit.py` (13): fillers, validation, gating, key
  sensitivity, no-audio/silent fast paths, FAKE-model plumbing (labeled).
- `tests/test_speech_real.py` (7): REAL tiny inference on Windows-SAPI
  synthesized speech (offline, built-in Zira voice), word validity, cache
  flags, span alignment, CLI. No faked recognition anywhere.

## Limitations

- No speaker diarization (future phase); no translation (source language kept).
- `large-v3` not exercised on this box (download + RAM cost).
- SAPI fixture voice is machine-specific; tests assert recognition loosely
  enough (`hello`/`fox` keywords, counts, bounds) to survive voice variance.
