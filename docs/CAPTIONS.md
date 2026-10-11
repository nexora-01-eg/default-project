# CAPTIONS.md — Phase 14 (`engine/subtitles/`)

## Implementation plan (written before code, 2026-09-18)

Build on verified pieces only: Whisper transcript (source of truth),
gateway `subtitles`/`ass` filters (libass present), phase cache/log/store,
approval + manifest + QC patterns. No new models, no network, no fonts
downloaded, no translation/diarization/rewriting/karaoke.

1. **Models** (additive): `CaptionWord` (frozen copy + word_id),
   `CaptionCue` (event + metrics + warnings), `CaptionPlan` (deterministic
   JSON, the source of truth; SRT/VTT/ASS derived).
2. **Segmentation** (new logic, honest): word-gap / sentence-punct /
   pause / scene-boundary aware; prefers complete thoughts; caps (duration,
   chars, lines, words, reading speed) from config; split > extend >
   warn — never invent time over unrelated speech.
3. **Readability**: CPS + WPM per cue; deterministic balanced two-line
   wrapping (space breaks only, never hyphenate, no orphan second line);
   bidi-aware (logical order preserved, RTL runs never split internally).
4. **Arabic first-class**: ar-only / en-only / mixed / punctuation /
   numerals / Latin-in-Arabic tested; shaping/bidi delegated to libass
   (HarfBuzz+FriBidi in this build) for burn-in, logical-order Unicode for
   sidecars. No Arabic TTS voice exists on this box → Whisper-Arabic STT
   stays explicitly unverified; Arabic plan/render tests use hand-written
   (labeled synthetic) transcripts + real Arabic glyphs.
5. **Styles** (5 presets) + positioning (bottom/center/top, margins,
   safe-area) + font discovery (exists → PIL-opens → Arabic-coverage
   heuristic tiers, documented) + ASS styling for burn-in.
6. **Mapping**: cues → EDL keeps → output coords; removed speech trimmed /
   split / dropped-with-warning (never dangling captions).
7. **Approval**: `editing/approved_captions.json` (plan hash, mode, style,
   font id); render-plan `--captions` requires it; base approval untouched.
8. **Execution**: sidecar = derived files beside output; burned-in =
   post-render ASS pass via gateway `burn_subtitles` (one extra generation,
   documented). `mix`/`duck` precedent: only approved modes execute.
9. **QC**: plan checks (order/duration/overlap/words/unicode/arabic) +
   rendered checks (decode/duration/AV + visible-subtitle frame sampling).
10. **Cache**: plan key (source+transcript+style+config+version) and
    render key (output+font+style+mode); font/style/edit changes invalidate.
11. **Tests** (~30 incl. Arabic battery) + real SAPI e2e (both modes) +
    full suite must stay green.

## Architecture

```text
transcript.json (source of truth; words never rewritten)
  -> engine/subtitles/captions.py (segment -> wrap -> metrics -> validate)
  -> captions/caption_plan.json (+ .srt/.vtt derived sidecars)
  -> editing/approved_captions.json (EXPLICIT approval: mode/style/font)
  -> render-plan --captions
      -> map cues via execution keeps (source -> output)
      -> sidecar: files beside output (+ parse-back QC)
         burned_in: gateway burn_subtitles ASS pass (audio stream-copied)
      -> caption QC -> manifest caption_* section (+ reuse cache)
```

`engine/subtitles/` owns planning (`captions.py`), formats (`formats.py`),
fonts (`fonts.py`), execution (`render.py`). No Whisper/model/FFmpeg changes
outside one additive gateway function.

## Models

`CaptionWord` (frozen copy + word_id), `CaptionCue` (event + CPS/WPM +
warnings), `CaptionPlan` (deterministic JSON). Words keep transcript timing;
display text is stripped (timing untouched).

## Segmentation

Greedy word accumulation with breaks AFTER sentence punctuation / ≥0.5 s
pauses / scene changes, bounded by max words/chars/duration. Over-limit
cues: extend into following silence (≤0.4 s, never past next word) →
re-split at largest internal gap → warn (never invent time over speech).
Overlaps clamped; sub-minimum durations extended-or-warned. Prefers complete
thoughts; scene cuts inside speech are noted, not forced.

## Readability

CPS (chars incl. spaces / s) + WPM per cue; caps from config; min gap
0.08 s enforced by clamping. Every cue carries its measurements.

## Arabic handling

Logical-order Unicode everywhere (sidecars byte-correct); line breaks at
spaces only (bidi-safe, never hyphenated, no orphan second line); Arabic/
mixed/punctuation/numeral/Latin-in-Arabic batteries green. Shaping + bidi
delegated to libass (HarfBuzz + FriBidi in this FFmpeg build) for burn-in.
No Arabic TTS voice exists on this machine, so Whisper Arabic STT is
EXPLICITLY UNVERIFIED; Arabic plan/render tests use hand-written (labeled
synthetic) transcripts with real glyphs — never claimed as STT proof.

## Styles

`default | clean | social | cinematic | minimal`, each with family/size/
weight/alignment/margins/box/outline/shadow. Positioning bottom/center/top
maps to ASS alignments 2/5/8 with height-scaled margins (safe-area aware).

## Font discovery

`discover_fonts()` lists Windows fonts; `resolve_font()` maps family/file;
three tiers: valid (exists + opens) / uncertain (Arabic unprovable without
fontTools — warning, proceeds) / invalid (fail). Known-Arabic filename map
(Arial/Times/Tahoma/Segoe/majalla/trado/…). No downloads, ever.

## SRT

`HH:MM:SS,mmm` numbered blocks from cue lines. WebVTT: header (+language)
with dot millis. Both derived from the JSON plan; writers reject empty
cues loudly.

## WebVTT

See SRT (same source, `WEBVTT [- lang]` header).

## Burned-in

`burn_subtitles()` in the gateway: `subtitles` filter (libass) with escaped
paths + `fontsdir=C:/Windows/Fonts`; video re-encoded (preset rules apply),
audio stream-copied (captions never touch audio); ASS generated from cues +
resolved style + validated family, PlayRes = frame size.

## Sidecar

`<stem>.srt` + `<stem>.vtt` beside the base output (which stays final);
QC re-parses the SRT (count + boundary roundtrip).

## Timeline mapping

`map_cues_to_output()`: words surviving inside keeps shift by keep offset;
cues split on output gaps ≥ 0.8 s (`edit_split`); empty cues dropped with
warnings; stats kept/dropped/split. Verified: source 0–2/4–6 → output 0–4
maps word 4.2 → 2.2; removed-speech cues vanish without dangling text.

## Approval

`editing/approved_captions.json` (plan hash, mode, style, validated font).
Base approval untouched; adding captions later needs only this artifact.
`render-plan --captions` refuses unapproved work; stale plan/font/mode
changes fail validation loudly.

## CLI

`captions PROJECT [--style] [--format all|srt|vtt] [--force] [--json]`
(plan + sidecars, video untouched) · `approve-captions PROJECT
[--mode sidecar|burned_in] [--style] [--font-family] [--font-file]` ·
`render-plan PROJECT --captions [--dry-run]`.

## QC

Plan: order/duration/overlap/word-bounds/unicode/arabic-integrity.
Rendered: decode, duration, AV preserved, plus per-cue visibility sampling
(caption-band top-5% diff > 12.0 vs ~0.2 re-encode noise floor, calibrated
live) and audio-unchanged check. Sidecars: parse-back roundtrip.

## Cache

Plan key: source + transcript hash + style + config + font family +
version. Render key: base output + plan hash + style + font id + mode.
Font/style/edit changes invalidate; reuse revalidates files.

## Limitations

- Whisper Arabic STT unverified here (no ar TTS voice); pipeline itself is
  language-agnostic UTF-8.
- No karaoke, no per-word styling, no repositioning around faces.
- Burn pass adds one encode generation (documented, QC-gated).
- Font Arabic coverage is heuristic without fontTools (warning tier).
- Reuse re-probes duration/streams, not full QC, by design.