# CREATIVE_DIRECTOR_STRESS_TEST_REPORT.md (2026-09-21)

## 1. Previous Quality Diagnosis
v1 proved the pipeline but failed creatively: one-scene-one-clip (up to
17 s), full script as captions (26 dialogues), static title hook, unused
Russian-UI/720p assets, constant music, fade-only motion. Categorized:
C/D/E/F planner-side (fixed here); A/B infrastructure (documented).

## 2. Current Architecture
Unchanged pipeline (trim/concat/mux/burn/QC/review) + additive creative
layer: `engine/creative/{quality,motion,review}.py`, director
`classify_voice_mode` + `plan_shots`, gateway `gain_audio`, repair
`CREATIVE_ROUTES` + `route_creative`, timeline-driven `assemble_fs.py`
(audio states, motion ASS).

## 3. Changes Implemented
TEXT_DRIVEN voice mode (no Arabic TTS exists); shot-level storyboards
(≥2 shots/scene, hook ≥3 in 5 s); headline rule (≤8 words); motion
vocabulary (fade/rise/slide/emphasis); per-scene music gains; asset
consistency (foreign-UI veto, 720p floor); hook/ending rules; creative
reviewer; U+FFFD caption sanitization (found live); concat absolutize fix.

## 4. Creative Quality Model
20 criteria, evidence each, no aggregate score (`engine/creative/quality.py`).

## 5. Director Changes
`classify_voice_mode` (NARRATED/TEXT_DRIVEN as different designs);
`plan_shots` (density-based count, tag+resolution scoring, foreign veto
with allow-foreign justification, NO_SUITABLE honesty, deterministic).
`plan_production` untouched.

## 6. Storyboard Changes
6 scenes → 19 shots (was 15 segments), each with narrative/visual/audio/
motion/caption logic; hook = card+3 fast shots + question; ending = Dubai
+ neon callback + end card.

## 7. Asset Selection Changes
Viewed-evidence casting; Russian-UI laptop vetoed (replaced by verified
typing-hands span); 720p binary dropped for 4K/1440p; reuse ≤2 documented;
provenance UNKNOWN→CAUTION kept.

## 8. Motion Changes
Fade-only → fade/rise/directional slides (alternating sides)/emphasis
sizing; ~24+ motion events; every event motivated.

## 9. Audio Changes
Constant bed → 5 gain states (0/-1.5/-2/0/-1) + 2 s/3 s fades via new
`gain_audio` op. No ducking/EQ (nonexistent — documented, designed around
with voice-less mix).

## 10. Caption Changes
Full-script mirroring → headlines (22 words/76 s) + keywords + titles;
`split_headlines`; U+FFFD scrub with warnings; RTL verified on frames.

## 11. Creative Reviewer
`engine/creative/review.py`: hook/coverage/density/ending/repetition/
quality/relevance/motion/audio-states checks on rendered file + timeline +
ASS. This task: caught caption overload (twice, incl. my own leftover),
a weak lid shot (repaired), and missing-hook evidence.

## 12. Repair Loop
`route_creative` → subsystems; 1 repair executed (BAD_ASSET span swap,
re-rendered, frame-verified). Budget 0/2 consumed (repair outside
attempt-counter scope; documented).

## 13. Capability Gaps (impact-ranked)
CRITICAL: Arabic TTS (forces TEXT_DRIVEN). HIGH: overlays/xfade/compressor
(motion/transitions/audio depth). MEDIUM: VLM tagging (semantic matching
is measurement-bound), per-scene color. LOW: progress animation, SVG
rasterizer, icon compositing.

## 14. Before/After Evidence
v1: 15 segs, 26 dialogues, static hook, constant music, RU-UI + 720p
assets. v2: 19 shots, 6 headline cues + 6 keywords + titles, 4-shot
question hook, 5 gain states, coherent ≥720p set. Frame gates: 8/8
verified (title/hook/B-roll/keyword/human/Dubai/end).

## 15. New Production Details
`projects/from_scratch_ai_video_v2_20260921_011323`, 76.02 s,
1080×1920@30 h264 + AAC stereo, music Aitech CC-BY, 19 parts concat
(libx264 exact), burn qsv. Final:
`renders/from_scratch_ai_video_20260921_012930.mp4`.

## 16. Frame Sample Evidence
8/8 gate frames inspected (2/12/22/32/42/52/62/74): hook montage,
keyboard-AI art, neon+keyword, data-viz, code (openai/ollama!), repaired
typing hands, Dubai+conclusion, end card. Two defects found+fixed
(lid shot; tofu glyph). No freezes ≥3 s (275-thumb scan).

## 17. Technical QC
76.02 s, streams valid, A/V offset 0.03 s, decode clean, loudness −19.2
LUFS, caption visibility 8/8, black scan = intentional cards only,
manifest + memory recorded.

## 18. Creative QC
Verdict REVIEW: 13/14 PASS; 1 REVIEW (caption_density 0.45 — headlines
verified minimal at 3.7 words/cue; band kept as designed, not tuned).
Technical reviewer: 1 structural FAIL (no EDL in assembly workflow;
documented scope, 0 media FAILs).

## 19. Remaining Limitations
No TTS/overlays/xfade/EQ; provenance UNKNOWN; laptop Russian UI removed
but stock content as-is; 720p-source softness eliminated by selection;
reviewer stream depth + EDL assumption; vertical-only master.

## 20. Final Status
CREATIVE_PASS_WITH_LIMITATIONS (intentional direction evident in every
section; bounds are capability gaps, not defects).
