# SCENE_DETECTION.md — Phase 7 (`engine/analysis/scenes.py`)

## Implementation plan (written before code, 2026-09-17)

1. **Models** (`engine/core/models.py`, additive): `Scene`, `SceneDetectionResult`.
   Full float precision for timestamps (no rounding); frame numbers kept.
2. **Primary detector: PySceneDetect 0.7.1** (`content` default, `threshold`
   for fades/brightness cuts). Verified API notes:
   - `VideoManager` is GONE in 0.7.x → use `open_video` + `SceneManager`.
   - Use `.seconds` / `.frame_num` properties (`get_seconds()` deprecated).
   - **Empty `get_scene_list()` with zero cuts is normal** → normalize to a
     single `[0, duration]` scene from OUR probe (single source of truth).
3. **FFmpeg fallback via gateway only** (`select=gt(scene,T)` + `showinfo`
   through `run_ffmpeg`): explicit `--method ffmpeg`, plus one automatic
   attempt (recorded in `fallback_from` + log) if PySceneDetect raises.
4. **Timeline validation** (`validate_scenes`, same pattern as speech
   timestamp validation): ordered, non-overlapping, in-bounds, first≈0.
5. **Cache stage `scenes`**: file identity + method + detector version +
   resolved threshold + min length. Param change → new entry.
6. **CLI `scenes`** mirroring `transcribe` (new or `--project`-attach
   project, `--json`, exit 0/2). `analyze` untouched (stays lightweight).
7. **Fixtures via `make_test_media --all`**: 3×2 s hard cuts (known
   boundaries), static (single scene), 0.5 s (very short), fade clip.
8. **Tests** cover the 14 required items; full suite must stay green.

## Detector architecture

`engine/analysis/scenes.py`, three methods (`content` default, `threshold`,
`ffmpeg`), one gateway rule: ffmpeg only via `engine.rendering.ffmpeg`.

- **content** — `ContentDetector(threshold, min_scene_len_frames)`: HSV-change
  score per cut. Default threshold **27.0**. Catches hard cuts.
- **threshold** — `ThresholdDetector(threshold, min_scene_len_frames)`:
  average-brightness fade detector. Default threshold **12.0** (0–255 luma),
  `fade_bias=0.0`, `add_final_scene=False`. Finds fades to/from black with
  sufficient dwell; does NOT fire on bright hard cuts (verified: red/blue/
  green cuts → 1 scene). Trailing below-threshold runs are dropped by the
  `add_final_scene=False` default (documented, not changed).
- **ffmpeg** — `select='gt(scene,T)',showinfo` through `run_ffmpeg`,
  threshold **0.4** (0–1 scale, different semantics from the other two).
  Explicit `--method ffmpeg`, or one automatic attempt when PySceneDetect
  raises (recorded in `fallback_from` + `note` + JSONL log — never silent).

## Timestamp conventions

- Source of truth is OUR probe (`fps`, `duration`), never the detector's.
- `start`/`end` are full-precision float seconds (frame ÷ fps, never rounded).
- `start_frame`/`end_frame` are the detector's frame numbers (PySceneDetect)
  or `round(t × fps)` (ffmpeg fallback).
- Zero cuts ⇒ single `[0, duration]` scene with `note: "no cuts detected"`.
- `validate_scenes()`: ordered, non-overlapping, `start ≥ 0`, `end > start`,
  first near 0, last within duration. Issues stored, never dropped.

## Threshold semantics

| Method | Scale | Default | Meaning |
|---|---|---|---|
| content | ~0–100 change score | 27.0 | lower = more cuts |
| threshold | 0–255 luma | 12.0 | lower = only deeper blacks |
| ffmpeg | 0–1 scene score | 0.4 | lower = more cuts |

`scene_threshold: null` in config resolves to the method default; the
RESOLVED value scopes the cache key. `scene_min_len_s` (default 0.6 s) is
converted to frames; cuts yielding shorter scenes are merged by the detector.

## Cache behavior

Stage `scenes`: file identity + method + detector (pyscenedetect version
0.7.1, or ffmpeg version for method=ffmpeg) + resolved threshold +
min length. Any change → fresh entry. Hit returns `cached: true` with
equivalent structure (only the `cached` flag differs). Reuses the shared
`.cache/` + `analysis/scenes.json` + stage-marking + JSONL conventions.

## Fallback behavior

Primary failure (open/decode/detect error, missing lib) → exactly one
ffmpeg attempt → success recorded (`fallback_from`, note, log) or the
fallback error raised. `analyze` never runs detection (stays lightweight);
`scenes` is the dedicated operation.

## Limitations

- PySceneDetect 0.7.x: `VideoManager` removed (`open_video` used);
  `get_scene_list()` is `[]` on zero cuts (normalized, see above).
- No flash/gradual-transition handling beyond ContentDetector's merge filter.
- `detect_scenes()` has no timeout (library API); `timeout` applies to the
  ffmpeg fallback path only.
- ThresholdDetector will not segment bright-to-bright cuts; tune per content.

## Test strategy

`tests/test_scenes.py` (16): deterministic parser/validator units; REAL
detection on synthetic fixtures (3×2 s hard cuts → exact `[0,2,4,6]`;
static → 1 scene; 0.5 s short; fade clip); invalid input; ordering/overlap/
duration/frame-consistency; explicit + auto (monkeypatched) fallback; cache
hit + threshold/min-length invalidation; CLI exits; JSON schema; perf fields.

## Examples

```
video-engine scenes input.mp4
video-engine scenes input.mp4 --method threshold --threshold 30 --min-scene-length 0.1 --json
video-engine scenes input.mp4 --method ffmpeg --project <existing_id>
```
