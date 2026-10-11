# Al-Montier — Integrated Production Stack

**Date**: 2026-09-24 · **Rule**: a tool is listed as integrated ONLY if installed, validated by a real test, adapter-backed, and reproducible. Everything else is a contract/doc entry, not an integration.

## CORE (installed + tested + adapter-backed)

| Provider | Version | Capability | Test | Notes |
|----------|---------|------------|------|-------|
| FFmpeg/FFprobe 9.0.1 | Gyan full build | CUT/TRIM/CONCAT/MIX/CAMERA_PUSH/SCOPES | existing suite + test_tool_adapters (camera_push) | Pre-existing backbone; GPL build noted |
| faster-whisper (tiny cached) | 1.2.1 | STT + WORD_TIMING | test_tool_adapters (words≥10, lang en) | Word timings feed kinetic captions |
| Piper + ar_JO kareem | 2023.11.14-2 | AR TTS | test_tool_adapters (decode+duration) | ~2.4 s/char; sparse narration only |
| OpenCV | 5.0.0 | frames/flow/classic tracking | existing suite | — |
| PyAV | 18.1.0 | frame-exact IO | existing suite | — |
| Pillow | 12.3.0 | cards/thumbs/raster | test (stat card render) | Kept at 12.3 (see moviepy note) |
| scenedetect | 0.7.1 | scene/shot detect | test_tool_adapters | Pre-existing dep, now adapter-backed |
| onnxruntime | 1.30.0 | CPU inference | existing | rembg/whisper-adjacent |
| librosa | 0.11.0 | beats/onsets/analysis | test (tempo>40 on Aitech) | +soundfile/scipy/numba stack |
| pydub | 0.25.1 | slice/fade | test (2000 ms slice) | Needs system ffmpeg (present) |
| pyloudnorm | 0.2.0 | BS.1770 normalize | test (wav out) | Clips at 0 dBFS possible → follow with −1.5 dB safety |
| opentimelineio | 0.18.1 | OTIO export/read | test (2-clip roundtrip) | Interchange layer |
| svgwrite | 1.4.3 | SVG cards/callouts | test (valid XML) | Vector sidecars; raster via Chromium (pending) |
| webrtcvad-wheels | 2.0.14 | VAD | test (spans≥1 on 16 kHz mono) | Source webrtcvad needs MSVC — wheels fork used |
| jsonschema | 4.26.0 | contract validation | test (valid/invalid) | Production-contract gate |
| rembg | 2.0.85 | bg removal | test (u2net, Arsenal models, no download) | U2NET_HOME=F:/Arsenal/07_AI_Models/rembg |
| colour-science | 0.4.7 | colorimetry | test (self-match Δ=0) | No matplotlib (plotting only) |
| mediapipe | 1.0.1 | face landmarks | test (pinned .task DL, count≥0) | Model: face_landmarker float16 rev1, recorded |
| scikit-image | 0.26.0 | image filters | via rembg dep; direct use pending | Came with rembg |
| rapidocr_onnxruntime | 1.4.4 | OCR | test (synthetic "AI 87%" recovered) | onnx CPU, matches stack |
| pycaption | 2.3.10 | SRT→VTT | test (WEBVTT + 1 cue) | — |
| PyOpenColorIO | 2.5.2 | color transforms | test (2× exposure ⇒ 2× mean) | Config-free Matrix path |
| OpenImageIO | 3.1.17.0 | image IO | import-verified | Adapter pending (import test only) |
| blend-modes | 2.2.0 | blend math | import-verified | Adapter pending |
| colormath | 3.0.0 | delta-E | import-verified | Adapter pending |
| pillow-heif | 1.8.0 | HEIF read | import-verified | iPhone media |
| fonttools | 4.66.0 | font QC | import-verified | Caption font audits |
| noisereduce | 3.0.3 | spectral gate | import-verified | Adapter pending |
| libass (via FFmpeg) | burn-in | captions/kinetic | smoke test (karaoke + span cues) | ASS motion vocab extended |

## OPTIONAL (present, documented, partially wired)

moviepy (dropped: pillow<12 pin breaks rembg≥12.1; FFmpeg gateway covers it) · Chromium/Playwright (not downloaded; HTML/SVG runtime needs it) · resvg (portable binary candidate for SVG raster) · Blender portable-detect (TIER 3) · Natron portable-detect (TIER 3) · Vosk (alt STT) · vtracer/scour (with svgwrite path) · piexif · MOSAIC of CJK pkgs (installed as deps, unused).

## EXPERIMENTAL

Moondream-size VLMs on CPU · Real-CUGAN ONNX path · DeepFilterNet ONNX path · Butterflow slow-mo · Rive/rlottie headless render · Fish/Chatterbox TTS (validated separately, GPU-gated).

## RESEARCH (blocked: hardware or license)

All torch/GPU models (WhisperX, pyannote, Demucs, GFPGAN, Real-ESRGAN, SAM CC-BY-NC, YOLO AGPL, XTTS CPML, F5/Fish-Egyptian NC, ComfyUI GPL, SD RAIL, Flux non-commercial) · pedalboard/aubio (GPL viral — use ffmpeg DSP) · Remotion (company-license gate; contract-only) · cloud/proprietary (TIER 5 list in arsenal doc).

## Rejected integrations (with reason)

- moviepy: dependency conflict (pillow) + redundant with FFmpeg gateway (which is also faster).
- pedalboard/aubio: GPL-3.0 viral; equivalent capability via ffmpeg filters + librosa + scipy.
- webrtcvad source build: no MSVC; wheels fork used instead.
- base whisper-model download for smoke QC: engine policy requires explicit provisioning; tiny sufficed for mechanism proof.
