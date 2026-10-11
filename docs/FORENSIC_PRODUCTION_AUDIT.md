# FORENSIC_PRODUCTION_AUDIT — hook_second_v1_20260924 (master `...022940.mp4`)

**Status**: FORENSIC_AUDIT_COMPLETE. Read-only; nothing modified, installed, or
downloaded. Evidence: project dir, `scripts/produce_hook_second_v1.py`,
engine code, `F:/Arsenal` + `catalog.json`, docs/voice reports, ffprobe meters,
30 viewed frames, Whisper coverage. Detail docs: VOICE_SELECTION_FORENSICS,
ARSENAL_UTILIZATION_AUDIT, MOTION_GRAPHICS_FORENSICS, PRODUCTION_TIME_FORENSICS,
CREATIVE_GAP_MATRIX.

## 1. ROOT CAUSES (ranked)

1. **R6/R3 — director/planner ignore smoke-proven capabilities** (camera push,
   stat cards, fades, beat-snapping, loudnorm — demonstrated 2026-09-24, unused
   2026-09-24/25). Motion names assigned as unexecuted strings (HOLD ×8).
2. **R5 — renderer has no overlay/xfade ops** → constructed graphics, icons,
   UI, Lottie, advanced transitions structurally impossible.
3. **R2 — no discovery/requirement/search layer** for icons, motion assets,
   SFX, fonts, LUTs, music; MH footage catalog-invisible; SFX shelf genuinely
   empty (0 WAVs, incomplete zips).
4. **R1 — missing modules**: voice selection, icon→video path, Egyptian
   production voice, compositor.
5. **R10 — silent narrowing** (motion strings, fileless SFX kinds, unrouted
   TTS) with no decision records.
6. **R7 — full re-encode per repair** (315 s/run, no segment cache).
7. **R8 — correct license/hardware gates** (remotion, VoiceTut rights,
   Chatterbox RTF 37.6, provenance unknown) that narrow options.
8. **R9 — safety defaults** (Arial, hard cuts). 9. **R4 — manual tag matching**.

## 2. EVIDENCE (each claim anchored)

- Zero icon/SVG/Lottie/LUT/3D/template references in production script (grep).
- `ffmpeg.py`: no overlay/xfade/lut3d/zoompan defs; `camera_push` executor
  exists only in `adapters/providers.py:39-46`, never called by production.
- `motion_grammar` roles → FADE_IN/HOLD×8/SLIDE_RIGHT/SPRING_IN/PUSH_IN stored,
  never executed; render uses trim+fit+concat+ASS only.
- `director.plan_production` emits only BROLL + CAPTION_FONT requirement kinds.
- `SFX_RULES` 4 kinds; only `sting` resolves to a file (from Music folder).
- Voice: no `engine/tts`, one `PiperAdapter`; Mohamed `error/data:null`
  (`audition_log.json`); Chatterbox RTF 37.6 in its own report.
- Smoke test report (2026-09-24) proves the unused capabilities ran 24 h prior.
- Times: `build.json elapsed_s=315`; masters 02:15:53/02:26:54/02:29:54; narr
  WAVs in seconds; `mh_index.json` 02:00:24.

## 3. WHAT WAS ACTUALLY USED

18 B-roll clips + 3 navy cards + 50 ASS caption cues + Aitech bed + 1 sting
sample ×3 + hard cuts + cover reframes. Constructed motion-graphic objects: 0.
Found-footage metaphors: 3 (brain, traffic light, spiral). Camera moves: 0.
Overlays: 0. SFX kinds: 1 of 4. Voices: 1 of 1 producible. Music searched: 0 of 1441.

## 4. WHAT WAS AVAILABLE BUT UNUSED (and would have mattered)

zoompan camera push, Pillow stat cards, fades, librosa beat-snapping,
pyloudnorm, 5000+ SVG icons, Lottie files, `.cube` LUTs, Cairo/Plex Arabic
fonts, graphics_kit counters/bars/timelines, ~1441 music tracks, OTIO export.

## 5. WHY IT WAS UNUSED

No code path connects story→requirement→search→candidate→render for any of
them; the director's recipe only connects files-on-disk + trim + concat + ASS.
Partly structural (no compositor), mostly orchestration (never requested).

## 6. WHY PRODUCTION WAS SLOW (~50 min wall)

~13 min re-encoding identical pixels ×3 masters (no cache) + ~12 min
from-scratch arsenal indexing + ~10 min debug-fix cycles + ~10 min manual frame
review (which found all 4 real defects) + ~5 min STT/QC + ~5 min reports.
TTS/STT compute <1 min. Nothing blocked; everything was re-work or review.

## 7. WHY 79.06 s

69.24 narration + 1.5 lead + 4.5 gaps + 3.6 tail = 78.85 + 0.21 concat
tolerance. Narration alone exceeds 60 s; <60 s requires cutting ≥3 script
lines. No duration budget was ever set (assert-only gate).

## 8. TOP 5 GAPS / 9. CLASSES / 10. NEXT TASK

See CREATIVE_GAP_MATRIX §5–6: (1) overlay op, (2) unused proven capabilities,
(3) discovery layer, (4) voice selection, (5) segment cache. Classes:
integration-heavy with rendering (compositor) and planning (silent narrowing)
components; intelligence (matching) is manual but functional.
**ONE next task**: implement one timed `overlay` gateway op + render one lucide
icon through planner→director→render — unlocks the whole constructed-graphics
category in a single cut.

**FINAL STATUS: FORENSIC_AUDIT_COMPLETE**
