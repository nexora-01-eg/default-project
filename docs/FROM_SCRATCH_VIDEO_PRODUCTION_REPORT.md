# FROM_SCRATCH_VIDEO_PRODUCTION_REPORT.md (2026-09-20)

## Executive Summary
First genuine from-scratch production: 76 s vertical Arabic tech explainer
built from a topic only — 6 scenes, 8 verified B-roll clips, 2 procedural
title cards, kinetic Arabic titles/keywords/captions burned in, CC-BY music
bed with fades, QC pass, reviewer 1 structural FAIL + 0 media FAILs.
No user video touched (forbidden file never opened). No downloads.

## Creative Brief
See `projects/from_scratch_ai_video_20260920_210038/timeline/brief.json`.
Core message: AI accelerates manual video work; human direction remains
essential. No statistics/studies/companies invented.

## Script
`timeline/script.json`: 6 scenes (~150 words, Egyptian-friendly Arabic),
HOOK→PROBLEM→TRANSFORMATION→EXAMPLES→HUMAN→CONCLUSION, each with visual/
audio/caption intent. Stored as artifact.

## Storyboard
6 scenes with per-scene duration/narration-text/visual/transition/audio;
drives `scripts/assemble_fs.py` + timeline.json (reproducible).

## Capability Matrix
- SCRIPT_GENERATION: manual craft (no LLM local) — LIMITATION.
- VOICE_GENERATION: UNAVAILABLE (SAPI English-only, no espeak, no TTS pkgs;
  no downloads) → kinetic-text format instead (documented, honest).
- VIDEO/IMAGE/ICON/MUSIC/SFX_SEARCH: SUPPORTED (arsenal-x + enrichment).
- MOTION: PARTIAL (ASS kinetic text + reframes; no animator).
- CAPTIONS: SUPPORTED (burned ASS, libass shaping).
- AUDIO_PROCESSING: PARTIAL (trim/fade/mux; no EQ/compressor/ducking).
- VIDEO_COMPOSITING: PARTIAL (concat/fit/crop; no overlays/xfade).
- TRANSITIONS: hard cuts only — LIMITATION. COLOR: none applied (mixed
  sources accepted as-is) — LIMITATION. RENDERING/QC/REVIEW/REPAIR: SUPPORTED.

## Asset Requirements
9 requirements via /api/plan (4 B-roll themes + music + transition +
font + intro/outro)+ director shapes.

## Arsenal-X Searches
/api/match + /api/verify + frame-index visual evidence (38 videos viewed
in audit). Filename-only matches rejected when evidence lacking
(e.g. NASA for "code screen" refused).

## Selected Assets
8 B-roll clips (all viewed or enrichment-verified): neon cube 107916,
code 15029082, data 45056, laptop 136268, vertical keys 251763, handshake
358512, equalizer 316712, Dubai vertical 296958. Music: Aitech (rms 0.082,
peak 0.95, CC-BY). SFX: none (no attenuation capability). Icons verified
but unused (no compositing). Fonts: Arial via libass (Arsenal Amiri/Cairo
noted for future).

## Asset Provenance
B-roll: Pexels-sourced, license UNKNOWN → CAUTION recorded per candidate.
Music: CC-BY Kevin MacLeod, attribution: "Music: Aitech by Kevin MacLeod
(incompetech.com), CC-BY". No downloads performed.

## Voice / Narration
UNAVAILABLE (see matrix). No voice fabricated; on-screen text carries the
script (timed per scene). Reported as the primary capability gap.

## Music
Aitech [2,78] → 76 s + 2 s/3 s fades; bed −19.2 LUFS/LRA 6.4; no ducking
needed (no voice); no other mixing (no capability).

## SFX
None (no attenuation path; hard-mixed SFX would blast).

## Motion Design
ASS kinetic events: title/keyword fades + positioned hierarchy; punch
reframes not needed (B-roll already moves); hard-cut transitions only.

## Timeline
15 segments, 76.0 s: 2 cards + 13 clips (timeline.json). Assembly:
trim → fit cover 1080×1920@30 → concat (libx264, exact) → music mux →
ASS burn (qsv). build.json recorded.

## Caption System
36 body cues + 6 keywords + title/end cards, all burned, RTL verified on
8 inspected frames. No tofu glyphs found in frame review.

## Render Configuration
1080×1920@30, h264_qsv base ops, libx264 assembly concat (measured-exact
after QSV multi-part drop finding), qsv burn, AAC audio.

## QC
76.00 s container, 1080×1920 h264 + AAC stereo; black-frame scan: only
intentional title/end cards; decode clean; loudness −19.2 LUFS; caption
visibility confirmed on all 8 gate frames; manifest (build.json) valid.

## Independent Review
FAIL (1): `editing:edl_present` — from-scratch assembly has timeline.json,
not an EDL; reviewer assumes edit workflow. 0 media FAILs. Rules frozen.
Recorded as structural scope limitation, non-critical to the artifact.

## Repair Attempts
Routed (editing subsystem note); no valid repair exists without
fabricating an EDL → left standing, budget untouched.

## Final Production Statistics
76.0 s · 6 scenes · 10 assets (8 video + 1 music + procedural cards) ·
8 video · 0 images · 0 icons in-video · 2 graphic cards · 42 caption
events · music 76 s · SFX 0 · transitions 14 hard cuts · motion events
~50 ASS events · narration 0 s (no voice) · ~24 MB file.

## LIMITATIONS
No Arabic TTS; no overlays/xfade/EQ/ducking/compressor; mixed-source
color accepted as-is; B-roll provenance UNKNOWN (CAUTION); reviewer EDL
assumption; laptop screen shows Russian UI (stock content as-is);
720p-source softness after 2.67x upscale; keyword overlay occasionally
busy; music title/genre from filename evidence only.

## Regression
Engine 406/0 · arsenal-x 54/54 · new gateway ops tested (fade_audio,
color_clip, concat-abs) · probe encoding fix tested · no TS changes.
User video + prior projects untouched; no downloads; no new deps.
