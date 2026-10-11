# ARSENAL_UTILIZATION_AUDIT — hook_second_v1_20260924

Read-only. Counts measured 2026-09-24/25. "Searchable" = the production had a
code path that could find items by meaning; "Considered" = an item entered a
logged selection decision.

## 1. Utilization table

| CATEGORY | TOTAL AVAILABLE | SEARCHABLE | CONSIDERED | SELECTED | RENDERED | REASON FOR NON-USE |
|---|---|---|---|---|---|---|
| Video B-roll (MH folder) | 376 mp4 | 376 (director-built `.cache/mh_index.json`; folder itself is UNINDEXED in `catalog.json`) | 60 verticals thumbnailed → ~20 shortlisted by eye | 18 + pool of 19 | 18 clips | Used. Remainder: landscape or semantically off-topic |
| VideoAssets/Stock-Footage | 4 (+36 zips/blender elsewhere in cat.) | 4 (listed) | 4 (frame-sampled) | 1 (glitch) | 0 | 3 are synthetic test patterns, 1 all-black → all rejected by evidence |
| Icons (lucide/phosphor/tabler SVG) | ~5000+ | 0 | 0 | 0 | 0 | **Intelligence/integration failure**: no icon-search code, no SVG→video path, renderer has no overlay op (R2+R5) |
| SFX library (03_SFX) | 0 usable (3 zip parts, sets incomplete, 0 WAVs on disk) | 0 | 0 | 0 | 0 | **Asset shortage is REAL here**: nothing decodable exists without multi-GB extraction of incomplete archives |
| Music (04_Music, ~1441 mp3, ~all Incompetech) | ~1441 | 0 | 0 | 2 (hardcoded paths) | 2 (bed + sting source) | No search/comparison/beat analysis; `librosa` AVAILABLE but `snap_to_beats` never called (R6) |
| Fonts (1184; incl. Cairo, IBM Plex Sans Arabic) | 1184 | 0 | 0 | 0 (Arial/system used) | 0 (as files) | libass fontconfig path for custom TTF never validated; Arial was the validated-safe default (R9 safety default) |
| LUTs (`.cube` present in 08_3D_Assets) | present (exact count unlisted; `.cube` ext confirmed) | 0 | 0 | 0 | 0 | No `lut3d` op in renderer; no planner requirement kind (R5+R2) |
| Motion assets (lottie-library, lottie-mega, 5000 MotionDesign files) | 1000s | 0 | 0 | 0 | 0 | No Lottie→frames path wired; chromium probe MISS despite `chrome.exe` existing (detection gap); remotion LICENSE_BLOCKED (R2+R5+R8) |
| Templates (06_Templates) | 5000 | n/a | 0 | 0 | 0 | Category is **web templates** (HTML5UP/tailwind), not video templates — nothing applicable exists |
| 3D assets (825: ambientCG textures, 1 blend) | 825 | 0 | 0 | 0 | 0 | No Blender installed, no 3D→video path, textures unusable without compositor (R1+R5) |
| Procedural graphics (graphics_kit: counters/bars/timelines/cards + svgwrite AVAILABLE + pillow AVAILABLE) | ~10 generators | 0 | 0 | 0 | 0 (smoke test rendered 1 stat card 2026-09-24; director did not reuse) | Generator exists; director never requested; overlay path missing for composited use, full-frame-card path unused (R3+R6) |
| Voice/TTS | 1 producible (Piper) + 1 bounded (Chatterbox) + 0 producible Egyptian | 0 (hardcoded) | 1 (Kareem, by hand) | 1 | 1 | No selection module; alternatives blocked by physics/policy (see VOICE_SELECTION_FORENSICS) |

## 2. Critical distinction

- Icons / motion assets / LUTs / procedural graphics / fonts / music-beyond-2:
  **intelligence/integration failure, NOT shortage**. The files exist; no code
  path connects story → requirement → search → candidate → render.
- SFX: **genuine shortage** (0 decodable files). The SFX director's 4-kind
  vocabulary (`sting/tick/transition_tick/accent`) is unbacked — only `sting`
  resolves to a file, and that file lives in the Music folder.
- Templates/3D: category mismatch / no toolchain — correctly unused, but the
  planner should know that instead of being silent.
- MH video folder (the ONLY used source) is invisible to `catalog.json`
  (Arabic dirname unindexed) — the production succeeded only because the
  director hand-built an index, thumbnails, and contact sheets from scratch.
