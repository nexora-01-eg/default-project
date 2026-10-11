# Production License Audit (code/model/voice/dataset/asset split)

Verified in-session (2026-09-24) unless noted. "Open source" is never used as proof of commercial clearance.

## CODE licenses (installed/registered)

MIT: faster-whisper, PyAV, pydub, pyloudnorm, jsonschema, rembg, webrtcvad-wheels, blend-modes, pycaption, onnxruntime, tokenizers · Apache-2.0: OpenCV, opentimelineio, svgwrite, mediapipe, rapidocr, OCIO, OpenImageIO, scikit-image, diffusers(dep), transformers(dep) · HPND: Pillow · ISC: librosa, soundfile(dep chain) · BSD-3/2: scipy, numpy, numba, librosa-deps, colour-science, OpenColorIO(dep), safetensors · LGPL-2.1: VapourSynth(n/a), python-bidi(TIER 2) · GPL (present but contained): FFmpeg Gyan full build (invoked as subprocess — the standard GPL boundary; never linked), espeak-ng (Piper runtime dep).

## MODEL / WEIGHT licenses

Whisper tiny (MIT, OpenAI) · Piper ar_JO kareem (NEEDS VERIFICATION — dataset URL only) · rembg u2net/isnet (verify per-model before commercial use) · MediaPipe face_landmarker (bundled task model — verify per-model) · RapidOCR onnx (verify per-model) · Chatterbox EG (Apache-2.0 stated; voice/dataset unknown — separate validation track).

## VOICE / DATASET / ASSET licenses

No TTS voice cleared for commercial use (Piper kareem unverified; VoiceTut data/voices unknown). Music: Incompetech CC-BY (attribution required on publication — Aitech, MJS Stings). B-roll: Pexels-sourced MH clips, provenance UNKNOWN (used under caution; no ownership claimed). Fonts: Arial (system); Arsenal Arabic fonts available, unused in renders.

## COMMERCIAL RESTRICTIONS (kept out)

GPL-3.0 viral: pedalboard, aubio (documented, NOT integrated) · AGPL: Essentia, Aeneas (TIER 4) · CPML (non-commercial models): Coqui XTTS family · CC BY-NC(-SA): Fish weights, SAM models, F5/Fish-Egyptian checkpoints, Denoiser-fb · Company-license gate: Remotion (free ≤3-person; paid 4+) · AGPL-3.0: YOLO/Ultralytics · Custom NC: CodeFormer(?), ComfyUI GPL-3.0, SD Open RAIL-M, Flux Dev NC · Cloud/SaaS: excluded from core path by policy.

## Attribution requirements

Incompetech CC-BY music (credit Kevin MacLeod on any publication) · Whisper/FFmpeg customary notices · Remotion evaluation use only (no production renders made).
