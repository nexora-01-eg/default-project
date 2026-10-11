# VISUAL_ANALYSIS.md — Phase 11 (`engine/analysis/visual.py`)

## Implementation plan (written before code, 2026-09-17)

Machine audit: cv2 5.0.0 + numpy ✅ · onnxruntime 1.30 CPU present (transitive,
no weights) · NO Haar XMLs · NO torch/mediapipe/YOLO/CLIP weights · HF cache
holds whisper-tiny only. Nothing will be downloaded.

1. **Models** (additive): `VisualFrame`, `FaceDetection`, `ObjectDetection`,
   `SceneVisualSummary`, `VisualAnalysisResult` (+ capability dicts).
2. **Sampling**: deterministic plan on Phase 7 scenes (middle / bme /
   per-scene-N / fps modes); extraction ONLY via gateway `extract_frame`;
   `visual_max_frames` bound; plan carries timestamp + frame_index + scene_id.
3. **OpenCV signals** (no DL): brightness mean (+p5/p95), contrast (std),
   sharpness (Laplacian variance, documented scale), motion (absdiff mean +
   Farneback flow mean), configurable quality flags (dark/bright/
   low-contrast/blurry — neutral labels, never "bad video").
4. **Adapters** `VisualDetector` → face / object / embedding. All resolve
   `unavailable` here (reasons recorded); enable-flags can force `skipped`;
   exceptions become `failed` without crashing the pipeline. Fake-detector
   tests cover adapter + framing logic honestly (labeled, never real).
5. **Framing heuristics** (explicit): largest-face ratio → close_up/medium/
   wide at documented cutoffs, confidence labeled heuristic; no faces →
   `unknown` + reason. Center-of-mass = grayscale centroid (explainable).
6. **Duplicates**: dHash (hamming ≤ thr) + histogram correlation for
   continuity; static-span runs reported, nothing removed.
7. **Aggregation + continuity** per scene; scene boundaries never modified.
8. **Project integration**: needs `media_info.json` (video stream required)
   + `scenes.json`; cache stage `visual` (source + version + sampling +
   caps + detector identity + thresholds); artifacts
   `visual/visual_analysis.json` (+ `visual/frames/` intermediates);
   JSONL logging; CLI `visual`.
9. **Tests**: synthetic-image metric units (exact numbers), motion/duplicate
   units, adapter available/unavailable/failed paths, cache, aggregation,
   CLI, real fixture chain. Full suite must stay green.

## Architecture

`engine/analysis/visual.py` (~700 lines). Sampling plan → gateway
`extract_frame` per sample → per-frame OpenCV signals → adapters (best
effort) → scene aggregation + continuity + static spans → `VisualAnalysisResult`
→ `visual/visual_analysis.json` (+ `visual/frames/` intermediates) via the
standard project/cache/log/store flow (stage `visual`).

```text
scenes.json + media_info.json
  -> plan_sampling (deterministic, frame-quantized, EOF-safe, max-bounded)
  -> extract_frame (gateway only) -> frame_metrics / motion / dhash / hist
  -> VisualDetector adapters (face/object/embeddings: honest statuses)
  -> estimate_framing + _aggregate + _continuity + _static_spans
  -> visual_analysis.json
```

## Frame sampling

Modes `middle | bme (default) | per_scene | fps`, all clamped into scenes,
quantized to exact frame starts (`round(t*fps)/fps`), never seeking into the
final 2-frame window, thinned deterministically past `visual_max_frames`,
degenerate clips collapse duplicate seeks (never empty).

## Supported capabilities (this machine, verified 2026-09-17)

| Capability | Status | Backend |
|---|---|---|
| opencv_metrics | AVAILABLE | opencv-5.0.0, local |
| face_detection | UNAVAILABLE | none — no Haar XML ships with this wheel, no DNN weights; nothing downloaded |
| object_detection | UNAVAILABLE | none — no weights configured (onnxruntime 1.30 CPU present, model-less) |
| embeddings | SKIPPED | none — disabled by default; no model configured |

## Capability discovery

`discover_capabilities()`: each adapter reports available | unavailable |
skipped (disabled) | failed (exception text, pipeline continues). Enable-flags
force `skipped`. Adapters expose `is_available()` + `detect()` + never-raising
`capability()`; future YOLO/ONNX/CLIP backends implement `VisualDetector`.

## OpenCV metrics

Brightness mean + p5/p95, contrast = grayscale std, sharpness = Laplacian
variance (resolution/content-scale-dependent — threshold is a starting point,
tune per content), motion = absdiff mean (0..1, exact) + Farneback flow mean
in px/frame (has a ~0.02 noise floor on identical frames), dHash 64-bit +
hamming distance, 32-bin grayscale histogram correlation. Quality flags are
neutral (`dark_frame`, `bright_frame`, `low_contrast`, `blurry`) with
configurable thresholds — never subjective claims.

## Optional detectors

`FaceDetectorAdapter` (Haar XML path or packaged cascade; confidence 0.5 =
heuristic, stated), `ObjectDetectorAdapter` (weights path + onnxruntime),
`EmbeddingAdapter` (model ref; vectors never embedded in JSON — references
only, by design). DETECTION ONLY: no identity, no attributes, by architecture
(fields are bbox geometry alone).

## Model loading policy

No downloads, ever, in this layer. User-supplied paths (`visual_face_*
cascade_path`, `visual_object_weights`, `visual_embedding_model`) are the
only way a detector becomes available. Lazy init; init failure at detect
time marks the capability `failed` with reason and continues.

## Configuration

`visual_mode bme`, `samples_per_scene 3`, `fps 1.0`, `max_frames 128`,
dark 25 / bright 230 / contrast 15 / sharpness 100.0, dHash hamming 5,
hist stable 0.9 / large-change 0.5, enables + model paths + timeout 900.
Conservative: bounded frames, no GPU requirement, CPU-only OpenCV.

## Cache behavior

Stage `visual`: source identity + `visual-1.0` + sampling config + enabled
caps + detector identity (backend + weights path or `none`) + thresholds.
`--force` bypasses the read (still writes). Deterministic reruns are
byte-equal modulo `processing_s`/`cached`.

## CLI

`video-engine visual <project> [--force] [--samples-per-scene N]
[--fps F] [--mode M] [--json]` → `visual/visual_analysis.json`. Reports
capabilities, scenes, frames, time, cache, warnings. Exits 0/2. Requires
`media_info.json` with a video stream + `scenes.json` (audio-only fails
clearly — visual analysis of audio is meaningless).

## Limitations

- Timestamp seeking is frame-quantized; gateway `extract_frame`/`trim` now
  format seeks at full float precision (a `%.3f` off-by-one dropped boundary
  frames — fixed Phase 11, full suite green).
- Flat same-luminance fields (e.g. pure red vs CSS green) are genuinely hard
  to tell apart in grayscale metrics — reported honestly, not papered over.
- Static-span detection requires hash proximity AND histogram similarity
  (flat fields of different colors share dHash 0).
- Framing without faces is `unknown` (no pretended shot classification).
- `timeout` bounds extraction; `detect_scenes`-style library timeouts don't
  exist for the (fast, bounded) OpenCV passes.

## Performance

9-frame 3-scene 360p analysis ≈ 1.6–1.9 s end-to-end (~10x realtime);
per-frame OpenCV cost is milliseconds (flow on 160×90). Bounded memory:
streaming per-frame, no full-video decode.

## Future extension points

`VisualDetector` subclasses (YOLO/ONNX/CLIP runners), embedding reference
store, face-track continuity, shot-scale refinement once faces exist.