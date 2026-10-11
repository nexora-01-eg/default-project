# CREATIVE_GAP_MATRIX — hook_second_v1_20260924

## 1. Capability matrix (measured 2026-09-24/25)

| CAPABILITY | AVAILABLE? | INTEGRATED? | PLANNER-AWARE? | DIRECTOR-AWARE? | ASSET-AWARE? | RENDERABLE? | USED? |
|---|---|---|---|---|---|---|---|
| Arabic TTS | YES (Piper) | YES (adapter) | opaque string only | hardcoded | n/a | YES | YES |
| Egyptian TTS | NO producible (Chatterbox bounded-only RTF 37.6; Mohamed blocked ×3) | NO adapter | NO | NO | n/a | would be | NO |
| Voice selection | NO (no module, no registry) | NO | NO | NO | n/a | n/a | NO |
| Icons (5000+ SVG) | YES files | NO | NO | NO | NO index | NO (no overlay) | NO |
| Motion assets (Lottie) | YES files | NO | NO | NO | NO index | NO (no path; chrome undetected) | NO |
| SFX | NO (0 WAVs) | vocab-only | 4 kinds, 3 fileless | sting only | n/a (empty) | YES if files existed | 1 kind ×3 |
| Music (1441) | YES | path-only | NO search | hardcoded | NO index | YES | 2 files |
| LUTs (.cube) | YES | NO | NO | NO | NO | NO (no lut3d op) | NO |
| Fonts (Arabic: Cairo, Plex-Ar) | YES | NO (unvalidated fontconfig path) | CAPTION_FONT kind emitted, never resolved | Arial default | NO | YES (Arial proven) | system font |
| Procedural graphics (graphics_kit+svgwrite+pillow) | YES | generator-only | NO | NO | n/a | full-frame cards only | 3 navy cards |
| UI graphics (constructed) | NO generator calls | NO | NO | NO | n/a | NO (no overlay) | 0 (1 found clip) |
| Motion graphics (constructed) | NO objects | NO | NO | NO | n/a | NO (no overlay) | 0 |
| Camera motion | YES (zoompan executor, smoke-proven) | YES (adapter) | NO | assigned-as-strings, never executed | n/a | YES | NO |
| Transitions | NO op (no xfade) | NO | "hard cut" strings | hard cuts | n/a | cuts only | cuts only |
| 3D | files only, no Blender | NO | NO | NO | NO | NO | NO |
| Templates (video) | NO (web templates only) | n/a | NO | NO | n/a | n/a | correctly unused |
| Visual metaphors (found) | YES (in footage) | via B-roll tags | YES (tags) | YES (selected) | hand-index | YES | YES (brain/traffic/spiral) |
| Visual metaphors (constructed) | NO | NO | NO | NO | n/a | NO | NO |
| Kinetic typography | YES (ASS) | YES | YES | YES | n/a | YES | YES (50 cues) |
| Captions | YES (libass) | YES | YES | YES | n/a | YES | YES |
| Asset diversity | YES (memory+budget+validator) | YES | YES | YES (+guard) | hand-index | n/a | YES (0 repeats, 0 overrides) |
| Semantic asset matching | manual tag lists | partial | tags only, no embeddings | director wrote tags | hand-index | n/a | worked, by hand |

## 2. Director decision audit (21 shots, condensed)

Story role → asset (category) → executed motion → graphics → SFX/music →
basis. Executed motion for ALL clip shots: static cover-crop hold + hard cut;
typography: alternating rise/fade/slide cues + gold keywords; graphics: none
beyond 3 navy cards; SFX: stings at sh_01/sh_14/sh_18 only; music: state gains.

- card/title, sh_01–sh_03 HOOK (tap/pink/neon phones+keys): 3 cuts in 5.5 s ✓
- sh_04–sh_06 PROBLEM (blank/blue phones, brain): holds, keyword boxes ✓
- sh_07–sh_08 EXPLANATION (neon, gold spiral): holds ✓
- sh_09–sh_10 PROCESS (edit timeline, dev desk): holds (no punch/zoom despite "demo" role)
- sh_11–sh_13 EXAMPLE (code, startup, planning): holds (code clip carries English terminal text — domain-normal, precedent-accepted)
- sh_14 TRANSITION (navy rupture card): hard cut + sting ✓ (after R1)
- sh_15–sh_17 PAYOFF (traffic, spiral slide, dashboard): holds (no counter/chart built for the numbers beat)
- sh_18 PAYOFF (handshake): hold ✓ · sh_19 ENDING (Dubai): hold ✓ · end card CTA ✓

The director had information for richer decisions (camera_push executor,
stat-card generator, fade/beat tools — all smoke-proven 24 h earlier) and did
not use it: the production script's recipe predates/is narrower than the proven
stack. **R6 with an R3 planner that never asks.**

## 3. Root causes (ranked by creative impact, no invented scores)

1. **R6/R3 — Proven capabilities never requested**: camera push, stat cards,
   fades, beat-snapping, loudness-normalize demonstrated 2026-09-24, absent
   from the autonomous recipe. Single biggest quality delta.
2. **R5 — No compositor**: zero overlay/xfade ops → icons, UI graphics,
   constructed metaphors, Lottie, advanced transitions structurally impossible.
3. **R2 — No discovery layer for 6+ categories**: icons, motion assets, SFX,
   fonts, LUTs, music have no search/index/adapter; MH footage itself is
   catalog-invisible. SFX shelf is additionally genuinely empty (0 WAVs).
4. **R1 — Missing modules**: voice selection, icon raster→video path,
   Egyptian production voice, overlay op.
5. **R10 — Silent narrowing**: motion names without execution, SFX kinds
   without files, TTS never routed — narrowing happens without decision
   records.
6. **R7 — Re-encode-per-repair** (315 s/run, no segment cache).
7. **R8 — Correct gates that narrow options**: remotion license, VoiceTut
   rights, Chatterbox quality/RAM, B-roll provenance unknown.
8. **R9 — Safety defaults**: Arial over Arabic fonts; hard cuts over unwired
   transitions.
9. **R4 — Hand-written tag matching** (works, but manual; no embeddings).

## 4. The two questions

**Why B-roll + captions?** ~70% orchestration failure, ~30% missing renderer
capability. The arsenal is large but disconnected: no index, no requirement
kinds, no search, no overlay op. The director cooked with the only connected
ingredients (files on disk + trim + concat + ASS text). What connects, renders.

**Why slow relative to complexity?** Compute re-encoded identical pixels 3×
with no cache; discovery rebuilt an index from zero; 4 debug cycles; and the
manual review that actually secured quality. Time bought correctness of a
simple video, not richness.

## 5. Top 5 highest-impact gaps

1. No overlay/composite op (blocks all constructed graphics).
2. Director recipe ignores smoke-proven capabilities (camera, cards, fades, beats, loudnorm).
3. No icon/motion-asset/SFX/font/LUT discovery or requirement kinds.
4. No voice-selection module (hardcoded single voice; future voices unwirable).
5. No segment-cache (every repair = full re-encode).

## 6. Gap classes + ONE next task

Integration: 1(partly),3,4 · Planning: 2,5(silent narrowing) · Rendering: 1
(compositor), transitions · Intelligence: semantic matching is manual.

**ONE recommended next engineering task**: add a single `overlay` (PNG/SVG-
raster over video, timed, positioned) gateway op to `engine/rendering/ffmpeg.py`
with a test, then route ONE lucide icon through planner→director→render on a
scratch timeline. It unlocks icons, UI graphics, stat cards, Lottie frames and
lower-thirds in one cut — the entire constructed-graphics category.
