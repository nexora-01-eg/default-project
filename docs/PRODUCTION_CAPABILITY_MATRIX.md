# Production Capability Matrix (wired capabilities only)

Columns: CAPABILITY → PROVIDERS (registered) → CURRENT (router top pick) → FALLBACKS → HARDWARE → TEST → QUALITY → LIMITATIONS. Anything not listed here is TIER 2+ (see arsenal doc), not wired.

| Capability | Providers | Current | Fallbacks | Hardware | Test | Quality | Limitations |
|------------|-----------|---------|-----------|----------|------|---------|-------------|
| CUT/TRIM/CONCAT | ffmpeg | ffmpeg | — | CPU | existing suite | exact | — |
| CAMERA_PUSH | ffmpeg | ffmpeg | — | CPU | test_tool_adapters | smooth zoompan | fixed 1080×1920 out |
| SCENE_DETECTION | ffmpeg, scenedetect | scenedetect | ffmpeg | CPU | test_tool_adapters | content-detector | threshold-tuned |
| SPEECH_TO_TEXT | faster-whisper | faster-whisper | — | CPU | existing + adapter test | tiny: fast, weak on slow speech | base/small need explicit provisioning |
| WORD_TIMING | faster-whisper | faster-whisper | — | CPU | adapter test (≥10 words) | tiny hallucinates on pathological input | see smoke findings |
| TEXT_TO_SPEECH_AR | piper | piper | — | CPU | adapter test + validation report | ~2.4 s/char; sparse narration only | NOT_EGYPTIAN; no word timing |
| BEAT_DETECTION | librosa | librosa | — | CPU | adapter test (tempo>40) | good on music bed | — |
| LOUDNESS_NORMALIZATION | pyloudnorm, ffmpeg | pyloudnorm | ffmpeg loudnorm | CPU | adapter test | clips at 0 dBFS → follow −1.5 dB | BS.1770 only |
| VOICE_ACTIVITY | webrtcvad | webrtcvad | silence analysis | CPU | adapter test (16 kHz mono) | aggressive-2 default | needs 8/16/32/48 kHz s16 mono |
| TIMELINE_IO/EDL/OTIO | opentimelineio | opentimelineio | — | CPU | 2-clip roundtrip | exact | — |
| CONTRACT_VALIDATION | jsonschema | jsonschema | structural fallback | CPU | valid/invalid test | — | — |
| SVG_AUTHORING | svgwrite | svgwrite | — | CPU | valid-XML test | vector only | raster needs Chromium/resvg (pending) |
| BACKGROUND_REMOVE | rembg | rembg | — | CPU | u2net real test, no DL | good | per-model license verify |
| COLOR_MATCH/ANALYSIS | colour-science | colour-science | — | CPU | self-match test | stats only (no auto-grade) | plotting needs matplotlib |
| COLOR_TRANSFORM | opencolorio | opencolorio | ffmpeg eq | CPU | 2× exposure test | config-free path | full ACES needs config |
| FACE_LANDMARKS | mediapipe | mediapipe | — | CPU | pinned-model pipeline test | count-schema | model DL recorded |
| OCR | rapidocr | rapidocr | tesseract (pending) | CPU | synthetic text test | Latin-strong | Arabic OCR unverified |
| SUBTITLE_CONVERT | pycaption | pycaption | — | CPU | SRT→VTT test | exact | — |
| AUDIO_SEGMENTS | pydub | pydub | ffmpeg trim | CPU | slice test | exact | needs ffmpeg |
| IMAGE_GEN/COMPOSITE | pillow | pillow | — | CPU | stat-card render | exact | Arabic shaping needs reshaper/bidi (TIER 2) |
| FRAME_EXACT_IO | pyav | pyav | opencv | CPU | existing suite | exact | — |
| KINETIC_CAPTIONS | ass-libass + faster-whisper | ass-libass | — | CPU | smoke (karaoke + span) | mechanism proven; STT-bound | word karaoke needs better-than-tiny STT |
| PROGRAMMATIC_EDIT | ffmpeg (moviepy dropped) | ffmpeg | — | CPU | existing suite | exact | — |
| CAPTIONS (burn) | ass-libass | ass-libass | — | CPU | smoke + v1/v2 frames | RTL correct, no tofu | Arial path (validated) |
| AUDIO_DSP (EQ/comp/limit) | ffmpeg filters | ffmpeg | — | CPU | narrated v1 gain states | deterministic | pedalboard GPL — not used |
| MODEL_INFERENCE_CPU | onnxruntime | onnxruntime | — | CPU | existing | — | — |

| VISUAL_DIRECTION | visual_director | visual_director | — | CPU | v2 tests (records/states/arc) | beats drive all downstream | planner diversity memory pending |
| STORY_GRAMMAR | visual_director | visual_director | — | CPU | v2 tests | 16 states + short arc | — |
| VISUAL_METAPHOR | visual_director | visual_director | — | CPU | v2 tests (15 cats) | strategies, no invented evidence | — |
| SHOT_VALIDATION | visual_plan | visual_plan | — | CPU | v2 tests (overlap/dead/pacing/text/motion/repetition) | — | — |
| MOTION_PRIMITIVES | motion_system | motion_system | — | CPU | v2 tests (supported + structured-missing) | 16 execute / 19 honest-missing | spring/shader/particle/mask/morph unwired |
| TYPOGRAPHY_RULES | typography | typography | — | CPU | v2 tests (isolate/layers/wrap) | bidi isolates verified by frame | emoji missing |
| PROCEDURAL_GRAPHICS | graphics_kit | graphics_kit | — | CPU | v2 tests (6 builders, determinism) | byte-identical SVG/PNG | in-video diagrams deferred |
| COMPOSITION_CHECK | composition | composition | — | CPU | v2 tests (safe/hierarchy/reject) | — | auto-reframe not wired |
| SFX_DECISIONS | audio_director | audio_director | — | CPU | v2 tests (sting/none/gains) | every decision has purpose/gain | library-only SFX |
| MUSIC_STATES | audio_director | audio_director | — | CPU | v2 tests (INTRO..ENDING, beat-snap) | ducking proven in renders | generative music TIER 4 |
| STYLE_CONTRACT | style_contract | style_contract | — | CPU | v2 tests (font/layers/motion) | benchmark PASS | — |
| SHOT_REVIEW | reviewer2 | reviewer2 | legacy reviewers | CPU | benchmark (hook/repetition/no_asset) | no scene bins | vision auto-checks need VLM (TIER 4) |
| QUALITY_SCORE | quality_score | quality_score | — | CPU | v2 tests (1.0 + critical override) | 20 criteria | — |
| CONFIDENCE_TIMING | kinetic_captions | kinetic_captions | span fallback | CPU | v2 tests (tiers + karaoke gate) | LOW-heavy forces phrase mode | needs better STT for karaoke |

| DIVERSITY_MEMORY | diversity | diversity | — | CPU | 23 v3 tests (memory/budget/rank) | recency+counts, seeded | keep-reason logging pending |
| PLAN_VALIDATION | diversity | diversity | — | CPU | v3 tests (structure + verdicts) | pre-render PASS/WARNING/FAIL | — |
| PLANNER_REPAIR | diversity | diversity | — | CPU | benchmark (hook split pre-render) | safe fixes only | structural splits live in driver |
| RHYTHM/RELATIONS/ESCALATION | diversity | diversity | — | CPU | v3 tests | reset advice, 15 relations, curve | advisory only (not enforced) |
| DIVERSE_SHOT_PLAN | visual_plan | visual_plan | base planner | CPU | benchmark (2→6 files) + determinism test | beat-needs routing | relative floor active since 3.1 |
| RELATIVE_FLOOR_RANK | diversity | diversity | strict gate (retired) | CPU | 19 ranking tests (cases A–H) | floor+utility+logged keep/swap | swaps fire only above floor |
| MOTION_SELECT | diversity | diversity | reviewer/fit workaround | CPU | benchmark run (cut/push/hold/slide, reasons) | story-first, no rotation | — |
| CAMERA_SELECT | diversity | diversity | reviewer/fit workaround | CPU | benchmark run (static/push/pan) | composition-aware + combo warn | — |

## Deliberately unwired (documented gates)

AUDIO_DSP via pedalboard/aubio (GPL viral) · GPU render/compute (no CUDA) · torch models (no torch in main env) · Remotion/GSAP/three (contract-only; npm+Chrome weight + Remotion company-license gate) · cloud STT/TTS/avatar/music (keys + SaaS; TIER 5).
