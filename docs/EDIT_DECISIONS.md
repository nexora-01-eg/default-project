# EDIT_DECISIONS.md — Phase 8 EDL (`engine/editing/decisions.py`)

ANALYSIS → DECISIONS → EDL. Plan only: sources untouched, nothing rendered.
Pure timeline math (stdlib); no FFmpeg, no model, no network in this module.

## Schema

`EditDecision{decision_id,start,end,action,reason,confidence,scene_id,
word_refs,metadata}` — actions `KEEP`/`REMOVE` on ORIGINAL source seconds
(never renumbered; rendering transforms the timeline later).
`EditDecisionList{source,duration,decisions,kept/removed_duration,
removal_ratio,policy,analysis_refs,warnings,generated_at,cached}`.

## Policy (config `edit_*`, CLI-overridable)

| Key | Default | Meaning |
|---|---|---|
| `edit_min_silence_s` | 0.8 | silences shorter than this are kept |
| `edit_silence_pad_before/after` | 0.15 | breathing room preserved around removals |
| `edit_remove_fillers` | true | RULE B on/off (`--no-fillers`) |
| `edit_filler_pad_s` | 0.08 | padding around filler removals |
| `edit_min_removal_s` | 0.2 | removals shorter than this are never emitted |

## Rules & precedence

1. INVALID/UNSAFE → KEEP + warning (bad timestamps, vanished spans)
2. SPEECH overlap → KEEP + warning (padded filler touching a real word)
3. FILLER removal (existing annotations only; confidence = word probability)
4. LONG SILENCE removal (interior after padding; confidence grows with margin)
5. default → KEEP

Filler spans are subtracted from silence spans (only two removal rules, so no
general sweep needed). Removals split at scene boundaries (`scene_id` traced,
never straddling); adjacent same-reason/same-scene pieces merge.

## Safety

Missing/corrupt audio, transcript, or scenes → `EditError` naming the gap
(no invented decisions). Exception: audio-only sources (no video stream in
`media_info.json`) synthesize the degenerate single `[0, duration]` scene
with a recorded warning — the truthful normalization, cf. Phase 7 zero-cut
rule. Timestamps round to 6 decimals for stable merging/JSON.

## Caching

Stage `edit`: policy + sha256 of the three analysis payloads. Same inputs →
`cached: true` (byte-equal artifact); any policy/analysis change → fresh EDL.

## CLI

`video-engine edit <project> [--min-silence] [--silence-pad-before/after]
[--no-fillers] [--filler-pad] [--json]` → `edit/edit_decision.json`.
Exits 0 (plan printed) / 2 (missing analysis etc.).

## Tests

`tests/test_editing.py` (19): hand-built spec-example coordinates, padding,
tiny-silence keep, filler ± speech-overlap safety, scene splits, filler-wins
priority, silence merging, invalid/missing inputs, policy validation,
determinism, cache + policy invalidation, CLI, plus REAL artifacts
(SAPI speech → valid tiled EDL; 5 s real silence → exact REMOVE [0.15, 4.85];
audio-less video → all KEEP).
