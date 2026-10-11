# AUDIO_ANALYSIS.md — Phase 3 module (`engine/analysis/audio.py`)

Non-destructive audio/media analysis. Reads the source only; writes
`projects/<id>/analysis/audio_analysis.json` (stage `analyze_audio`).

## What it extracts

| Field | Source |
|---|---|
| `audio_present`, `num_audio_streams` | ffprobe stream list (via `core.media.probe`, reused — never re-parsed here) |
| `channels`, `sample_rate`, `codec`, `bitrate`, `audio_duration` | first audio stream (stream duration, else container duration) |
| `mean_volume_db`, `max_volume_db` | `ffmpeg -af volumedetect` (`None` when ffmpeg reports `n/a`) |
| `loudness` (`input_i/tp/lra/thresh`…) | `ffmpeg -af loudnorm=print_format=json` (first pass only — measurement, no filtering of the source) |
| `silence[]` (`{start,end,duration}`) | `ffmpeg -af silencedetect=noise={db}dB:d={min_s}` |
| `non_silent[]` | exact complement of silence over `[0, audio_duration]` |
| `silence_total_s`, `config_used` | derived / echo of thresholds |

## Behavior notes

- **No audio stream is a valid result** (`audio_present: false`, empty lists), never an error. Missing file / missing ffmpeg binary raise `AudioAnalysisError` loudly.
- **Trailing silence:** silencedetect emits no `silence_end` at EOF; a dangling `silence_start` is closed at `audio_duration`.
- **Thresholds** come from config (`silence_db`, `min_silence_s`), overridable per run (`analyze --silence-db / --min-silence`) and recorded in `config_used`, which also scopes the stage cache key.
- **Caching:** stage key `analyze_audio` = file hash + thresholds. Different thresholds → different cache entries (correct: results differ).

## Deterministic fixtures (`python scripts/make_test_media.py --all`)

WAV fixtures are PCM (`pcm_s16le`, no codec padding → sample-exact boundaries).
MP4 fixtures use AAC (expect ~50 ms priming tolerance in boundary asserts).

| Fixture | Content | Used for |
|---|---|---|
| `tone_5s.wav` | 5 s 440 Hz sine | audio-present, no-silence |
| `silence_5s.wav` | 5 s digital silence | full-silence |
| `mixed_6s.wav` | 2 s tone + 2 s silence + 2 s tone | boundary accuracy (silence ≈ [2, 4]) |
| `tone_5s.mp4` | 640×360 + tone | video+audio case, cache test |
| `silent_video.mp4` | 640×360, no audio | no-audio-stream case |
| `mixed_6s.mp4` | 640×360 + mixed audio | render-pipeline case (Phase 4) |
