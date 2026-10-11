# Visual Production Architecture (code-first, capability-routed)

## Layers

1. **Production contract** (`engine/tools/contract_schema.py`): machine-readable plan {project, canvas 1080×1920@30, voice, narration segments, shots[{shot_id,start,end,asset,motion,graphics,text}], audio, review}. Validated by jsonschema (structural fallback inside). Director authors it; router executes it; reviewer checks the artifact, never the plan.
2. **Capability router** (`engine/tools/router.py`): capability → scored provider → recorded decision. No silent fallback.
3. **Provider adapters** (`engine/tools/adapters/`): 18 adapters, each one provider, provenance-recorded artifacts.
4. **Render executor**: FFmpeg gateway (`engine/rendering/ffmpeg.py`) remains the only process that touches pixels; new providers feed it (segments, PNG cards, ASS, WAVs) or analyze for it (beats, words, scenes, faces, OCR).
5. **QC → creative review → bounded repair** (existing modules + `engine/tools/visual_review.py` additive checks emitting router-ready repair capabilities).

## Data flow (smoke-proven)

narration WAV → faster-whisper WORD_TIMING → words.json → kinetic ASS (+Pillow stat card, +svgwrite SVG sidecar) → B-roll trims + CAMERA_PUSH + fades → concat → ducked music + sting + narration → mix → loudness → mux → burn → QC → review → (repair ≤3) → manifest with routing log.

## Production contract ↔ existing controller

`engine/montier_controller.py` phases (analyze/plan/storyboard/assets/voice/captions/motion/render/qc/review) are unchanged. The contract schema is additive: `validate_contract()` gates new router-driven productions; legacy paths untouched. OTIO adapter bridges contracts to NLE interchange when needed.
