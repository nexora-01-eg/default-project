# CAPTION_VISUAL_POLISH.md — Phase 15 (`engine/subtitles/visual_captions.py`)

## Implementation plan (written before code, 2026-09-18)

Visual polish as INFORMATION + approved rendering deltas on top of the
verified Phase 14 stack (transcript, caption plan, ASS, fonts, approval,
render, QC, cache all reused untouched). No motion graphics, no karaoke,
no per-character animation, no downloads, no identity.

1. **Models** (additive): `CaptionVisualContext`, `CaptionPlacement`,
   `CaptionEmphasis`, `VisualCaptionPlan`.
2. **Band sampling**: per-cue midpoint frame via gateway `extract_frame`
   to temp (never relies on Phase 11 filenames); top/center/bottom band
   mean+std in grayscale with cv2 (already a dependency). Deterministic.
3. **Placement**: style default → face-safe move (adapter-driven; faces
   UNAVAILABLE here so this path is tested with an injected fake) →
   contrast-seeking move → default. Safe-area fractions + margins.
4. **Contrast**: GOOD <150 / CAUTION 150–200 / POOR >200 band mean, with
   outline/box/shadow/position adaptation inside explicit permitted ranges;
   base style + adaptation + reason recorded, never silent.
5. **Emphasis**: numbers (Latin + Arabic-Indic), non-initial capitalized
   Latin, quoted spans; filler/low-confidence/punct-only rejected; >30%
   capped with warning; per-word transcript timing; types keyword /
   important_words (bold+color); speaker_highlight never emitted (no
   diarization — documented). Rendered as ASS inline overrides (no timing
   change); Arabic emphasis burn-tested explicitly, static fallback recorded
   if it ever destabilizes.
6. **Scene splits**: boundary-crossing cues keep one placement when sides
   compatible (|Δ|<40), else split into :a/:b visual events (text and
   timing preserved, treatment differs).
7. **Conflicts** → warnings only (never delete captions).
8. **Approval** `captions/approved_visual_caption_plan.json` binding six
   hashes/identities; render uses visual ASS only when plan+approval both
   valid, else standard ASS + recorded warning (never silent application).
9. **Cache/manifest/QC/CLI** per spec; render-plan --captions auto-detects.
10. **Tests** (~25) + fixtures A–D + real E2E + plain-vs-visual comparison;
    full suite must stay green.

## Architecture

```text
caption_plan.json + visual_analysis.json (+ editor plan signals via cues)
  -> engine/subtitles/visual_captions.py (pure analysis, no rendering)
  -> captions/visual_caption_plan.json (placements, emphasis, contexts,
     adaptations, conflicts, warnings)
  -> approve-caption-visual (six-way binding, immutable snapshot)
  -> render-plan --captions (visual ASS iff plan+approval both valid,
     else standard ASS + recorded warning)
  -> extended QC + manifest visual_* keys + cache
```

`engine/subtitles/render.py` decides per render; `formats.write_ass_visual`
renders per-event `\an` alignment + inline emphasis tags + box/outline
adaptations. Phase 14 `write_ass` frozen. No motion graphics, no karaoke,
no per-character animation, no downloads, no identity.

## Visual context

Per cue: nearest scene, band brightness/contrast from a real decoded frame
(gateway `extract_frame` to temp), face availability/regions (adapter;
UNAVAILABLE here → recorded, never invented), safe bands, frame timestamp.

## Safe areas

Normalized bounds from configured margins (1080p basis, height-scaled):
x/y min/max in 0..1. Placements snap to top(0.08)/center(0.5)/bottom(0.92)
anchors; coordinates validated in QC (fail outside 0..1).

## Contrast

Band mean vs white text: GOOD <150, CAUTION 150–200, POOR >200 (configurable
thresholds). Whole-frame fallback documented where band reads fail.

## Positioning

Style default → face-safe move (adapter-driven; tested with injected fakes
since the real adapter is unavailable) → contrast-seeking move (≥20 points
darker) → default. Every move records reason + 0.6 heuristic confidence.

## Style adaptation

Permitted ranges only: outline 1..`visual_caption_outline_max`,
box on/off, shadow 0/1, any of 3 positions. Family/size/alignment identity
never changes silently. Escalation: outline → box → shadow; ceiling reached
→ recorded, no change. Each adaptation stored per cue + rendered per event
(inline `\bord`/`\shad`, `DefaultBox` style when needed).

## Word emphasis

Candidates: numbers (Latin + Arabic-Indic), non-initial capitalized Latin,
quoted spans. Rejected: fillers, prob<0.5, punctuation-only. Capped at 30%
(earliest kept, extras dropped + warning). Types keyword (color) /
important_words (color+bold); speaker_highlight never emitted (no
diarization — documented). Timing always from transcript word_refs.
Rendered as ASS inline overrides (no timing change, no animation).

## Arabic handling

Logical-order tokens, space breaks only, tags surround whole tokens;
libass+HarfBuzz+FriBidi shape at burn. Arabic emphasis burn-tested
(`123` inside Arabic words: tags present, words intact, pixels visible).
Limitation recorded: no OCR-level glyph proof offline.

## Approval

`captions/approved_visual_caption_plan.json` binds source, caption plan,
visual analysis, style, font identity, visual plan hash. Any drift → re-plan
+ re-approve. Caption approval untouched. Render uses visual ASS only on
valid plan+approval, else standard ASS + warning (never silent).

## CLI

`caption-visual PROJECT [--style --force --json --dry-run]` (dry-run writes
nothing) · `approve-caption-visual PROJECT [--json]` ·
`render-plan --captions` auto-detects (dry-run shows visual block).

## QC

Placement bounds, emphasis-inside-cue timing, RTL word integrity, contrast
advisories (never fail), rendered decode/duration/AV/audio + frame-sampled
visibility (position-aware band metric, calibrated 28.8 vs ~0.2 noise).

## Cache

Plan key: source + caption/visual hashes + style + font family + config +
version + **code hash** (stale-logic protection, same lesson as Phase 12).
Render caption identity extended with visual hash/`none`. Font/style/visual
drift invalidates.

## Limitations

- Faces UNAVAILABLE on this machine (no Haar XML/weights; nothing downloaded).
- Static-scene motion is 0.0 by measurement (not a placeholder).
- Emphasis is keyword-level only; sentence semantics not modeled.
- `processing_s` excluded from determinism comparisons.
- Reuse re-probes duration/streams, not full QC, by design.