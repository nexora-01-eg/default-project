"""Phase 11 — visual intelligence: deterministic sampling + OpenCV signals +
optional detector adapters. INFORMATION ONLY: no rendering, no EDL changes,
no downloads, no network.

Capability policy: every capability reports available | unavailable |
skipped | failed. Optional failures never crash the pipeline; absence of
detections is data (empty lists), never an error.
"""
from __future__ import annotations

import time
from dataclasses import asdict
from pathlib import Path

from engine.core import config as config_mod
from engine.core.logging_utils import log_event
from engine.core.models import (
    FaceDetection,
    ObjectDetection,
    SceneVisualSummary,
    VisualAnalysisResult,
    VisualFrame,
)
from engine.core.pipeline import cache_key, cached, store
from engine.core.project_store import (
    load_project,
    mark_stage,
    project_dir,
    write_artifact,
)
from engine.rendering.ffmpeg import extract_frame

VISUAL_VERSION = "1.0.0"
SCHEMA_VERSION = "visual-1.0"
VISUAL_KEYS = ("visual_mode", "visual_samples_per_scene", "visual_fps",
               "visual_max_frames", "visual_dark_thr", "visual_bright_thr",
               "visual_contrast_thr", "visual_sharpness_thr",
               "visual_dup_hamming_thr", "visual_hist_thr", "visual_change_thr",
               "visual_enable_face", "visual_enable_object",
               "visual_enable_embeddings", "visual_face_cascade_path",
               "visual_object_weights", "visual_embedding_model",
               "visual_timeout")


class VisualError(RuntimeError):
    pass


def _r4(x: float) -> float:
    return round(float(x), 4)


def resolve_visual_config(overrides: dict | None = None) -> dict:
    cfg = config_mod.resolve(overrides=overrides)
    out = {k: cfg[k] for k in VISUAL_KEYS}
    if out["visual_mode"] not in ("middle", "bme", "per_scene", "fps"):
        raise VisualError("visual_mode must be middle|bme|per_scene|fps")
    for key in ("visual_samples_per_scene", "visual_max_frames",
                "visual_dup_hamming_thr"):
        try:
            out[key] = int(out[key])
        except (TypeError, ValueError):
            raise VisualError(f"{key} must be an integer") from None
    for key in ("visual_fps", "visual_dark_thr", "visual_bright_thr",
                "visual_contrast_thr", "visual_sharpness_thr",
                "visual_hist_thr", "visual_change_thr", "visual_timeout"):
        try:
            out[key] = float(out[key])
        except (TypeError, ValueError):
            raise VisualError(f"{key} must be a number") from None
    if out["visual_samples_per_scene"] < 1 or out["visual_max_frames"] < 1:
        raise VisualError("samples_per_scene and max_frames must be >= 1")
    if out["visual_fps"] <= 0 or out["visual_timeout"] <= 0:
        raise VisualError("visual_fps and visual_timeout must be > 0")
    for key in ("visual_enable_face", "visual_enable_object",
                "visual_enable_embeddings"):
        out[key] = bool(out[key])
    return out


# ---------------- frame sampling (deterministic) ----------------

def plan_sampling(scenes: list[dict], duration: float, fps: float, config: dict) -> list[dict]:
    """Sampling plan on the scene timeline. Same VIDEO+CONFIG -> same plan."""
    if not scenes:
        raise VisualError("frame sampling needs at least one scene")
    if fps <= 0 or duration <= 0:
        raise VisualError(f"cannot sample: fps={fps} duration={duration}")
    mode = config["visual_mode"]
    plan: list[dict] = []

    def _add(t: float, scene_id: int, kind: str):
        t = max(0.0, min(float(t), duration - 1e-3))
        plan.append({"timestamp": _r4(t), "frame_index": int(round(t * fps)),
                     "scene_id": int(scene_id), "kind": kind})

    bounds = sorted(scenes, key=lambda s: (s["start"], s["end"]))
    # Never seek into the final ~2-frame window: input seeking at/beyond EOF
    # makes the image encoder fail (no packets before encoder init).
    t_max = max(0.0, duration - 2.0 / fps)

    def _add(t: float, scene_id: int, kind: str):
        t = max(0.0, min(float(t), duration - 1e-3, t_max))
        # Snap to exact frame starts: 3-decimal rounding once pushed a sample
        # 0.3 ms past its frame's pts, and accurate seeking dropped the frame
        # (off-by-one at boundaries). Full precision, frame-quantized.
        t = round(t * fps) / fps
        plan.append({"timestamp": t, "frame_index": int(round(t * fps)),
                     "scene_id": int(scene_id), "kind": kind})

    if mode == "fps":
        step = 1.0 / float(config["visual_fps"])
        t, n = 0.0, 0
        while t < duration - 1e-6 and n < config["visual_max_frames"] * 4:
            sid = next((s.get("scene_id", -1) for s in bounds
                        if float(s["start"]) - 1e-6 <= t < float(s["end"]) - 1e-6),
                       bounds[-1].get("scene_id", -1))
            _add(t, sid, "fps")
            t += step
            n += 1
    else:
        for sc in bounds:
            s, e = float(sc["start"]), min(float(sc["end"]), duration)
            sid = int(sc.get("scene_id", -1))
            if e <= s:
                continue  # empty/degenerate scene: sampled as nothing (recorded by count 0)
            if mode == "middle":
                _add((s + e) / 2.0, sid, "middle")
            elif mode == "bme":
                _add(s, sid, "begin")
                _add((s + e) / 2.0, sid, "middle")
                _add(e - 1.0 / fps, sid, "end")
            else:  # per_scene: N evenly spaced
                count = int(config["visual_samples_per_scene"])
                span = max(e - 1.0 / fps, s)
                for i in range(count):
                    frac = i / max(count - 1, 1)
                    _add(s + frac * (span - s), sid, "fixed")
    plan.sort(key=lambda p: (p["timestamp"], p["scene_id"]))
    seen_ts: set[float] = set()  # degenerate clips: collapse duplicate seeks
    deduped = []
    for p in plan:
        if p["timestamp"] not in seen_ts:
            seen_ts.add(p["timestamp"])
            deduped.append(p)
    plan = deduped
    plan.sort(key=lambda p: (p["timestamp"], p["scene_id"]))
    if len(plan) > config["visual_max_frames"]:
        stride = len(plan) / config["visual_max_frames"]
        plan = [plan[int(i * stride)] for i in range(config["visual_max_frames"])]
    return plan


# ---------------- OpenCV signals (no deep learning) ----------------

def _cv2():
    import cv2
    return cv2


def frame_metrics(bgr) -> dict:
    """Brightness/contrast/sharpness on one BGR frame. Pure + deterministic."""
    import numpy as np
    cv2 = _cv2()
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape[:2]
    flat = gray.reshape(-1)
    lap_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    return {"width": int(w), "height": int(h),
            "brightness": _r4(float(flat.mean())),
            "brightness_p5": _r4(float(np.percentile(flat, 5))),
            "brightness_p95": _r4(float(np.percentile(flat, 95))),
            "contrast": _r4(float(flat.std())),
            "sharpness": _r4(lap_var)}


def motion_scores(prev_gray, gray):
    """(absdiff_mean 0..1, farneback_mean_px). First frame -> (0.0, 0.0)."""
    import numpy as np
    cv2 = _cv2()
    if prev_gray is None:
        return 0.0, 0.0
    diff = cv2.absdiff(prev_gray, gray)
    abs_mean = _r4(float(diff.mean()) / 255.0)
    small_prev = cv2.resize(prev_gray, (160, 90), interpolation=cv2.INTER_AREA)
    small_cur = cv2.resize(gray, (160, 90), interpolation=cv2.INTER_AREA)
    flow = cv2.calcOpticalFlowFarneback(small_prev, small_cur, None,
                                        0.5, 3, 15, 3, 5, 1.2, 0)
    mag = np.sqrt(flow[..., 0] ** 2 + flow[..., 1] ** 2)
    return abs_mean, _r4(float(mag.mean()))


def dhash(gray) -> str:
    """64-bit difference hash, hex. Same pixels -> same hash."""
    cv2 = _cv2()
    small = cv2.resize(gray, (9, 8), interpolation=cv2.INTER_AREA)
    diff = small[:, 1:] > small[:, :-1]
    bits = "".join("1" if v else "0" for v in diff.reshape(-1))
    return f"{int(bits, 2):016x}"


def hamming(a: str, b: str) -> int:
    return bin(int(a, 16) ^ int(b, 16)).count("1")


def hist_corr(gray_a, gray_b) -> float:
    """Grayscale histogram correlation -1..1 (1 = identical distribution)."""
    import numpy as np
    cv2 = _cv2()
    ha = cv2.calcHist([gray_a], [0], None, [32], [0, 256]).reshape(-1).astype(float)
    hb = cv2.calcHist([gray_b], [0], None, [32], [0, 256]).reshape(-1).astype(float)
    if ha.sum() == 0 or hb.sum() == 0:
        return 0.0
    ha, hb = ha / ha.sum(), hb / hb.sum()
    ma, mb = ha.mean(), hb.mean()
    denom = float(((((ha - ma) ** 2).sum()) * (((hb - mb) ** 2).sum())) ** 0.5)
    if denom == 0:
        return 1.0 if float(((ha - hb) ** 2).sum()) == 0 else 0.0
    return _r4(float(((ha - ma) * (hb - mb)).sum() / denom))


def quality_flags(metrics: dict, config: dict) -> list[str]:
    """Neutral measurable labels only — never subjective quality claims."""
    flags = []
    if metrics["brightness"] < config["visual_dark_thr"]:
        flags.append("dark_frame")
    if metrics["brightness"] > config["visual_bright_thr"]:
        flags.append("bright_frame")
    if metrics["contrast"] < config["visual_contrast_thr"]:
        flags.append("low_contrast")
    if metrics["sharpness"] < config["visual_sharpness_thr"]:
        flags.append("blurry")
    return flags


def center_of_mass(gray):
    """Grayscale centroid, normalized 0..1. Explainable, no semantics."""
    import numpy as np
    total = float(gray.astype(float).sum())
    if total == 0:
        return (0.5, 0.5)
    ys, xs = np.mgrid[0:gray.shape[0], 0:gray.shape[1]]
    cx = float((xs * gray).sum()) / total / gray.shape[1]
    cy = float((ys * gray).sum()) / total / gray.shape[0]
    return (_r4(cx), _r4(cy))


# ---------------- detector adapters ----------------

class VisualDetector:
    """Adapter contract for current AND future detectors.

    is_available() -> (ok, backend, reason). detect() runs only when ok.
    capability() never raises: failures become status=failed with reason.
    """

    name = "base"
    kind = "unknown"

    def is_available(self) -> tuple[bool, str, str]:
        return False, "none", "base adapter is abstract"

    def detect(self, bgr, timestamp: float, scene_id: int,
               width: int, height: int) -> list[dict]:
        raise NotImplementedError

    def capability(self, enabled: bool) -> dict:
        if not enabled:
            return {"status": "skipped", "backend": "none",
                    "reason": "disabled by configuration"}
        try:
            ok, backend, reason = self.is_available()
        except Exception as exc:
            return {"status": "failed", "backend": "none",
                    "reason": f"availability check failed: {exc}"}
        return {"status": "available" if ok else "unavailable",
                "backend": backend, "reason": reason}


class FaceDetectorAdapter(VisualDetector):
    name, kind = "face_detection", "face"

    def __init__(self, cascade_path: str | None = None):
        self.cascade_path = cascade_path
        self._clf = None
        self._backend = "none"

    def is_available(self):
        if self.cascade_path:
            from pathlib import Path as _P
            if _P(self.cascade_path).is_file():
                return True, "haar", f"user cascade {self.cascade_path}"
            return False, "none", f"configured cascade missing: {self.cascade_path}"
        try:
            import cv2
            base = getattr(cv2, "data", None)
            d = getattr(base, "haarcascades", "") if base else ""
            import os
            for fname in ("haarcascade_frontalface_default.xml",
                          "haarcascade_frontalface_alt.xml"):
                if d and os.path.isfile(os.path.join(d, fname)):
                    return True, "haar", f"packaged cascade {fname}"
        except Exception:
            pass
        return False, "none", ("no Haar cascade XML ships with this opencv build "
                               "and no DNN weights configured; no model downloaded")

    def _clf_or_raise(self):
        import cv2
        import os
        if self._clf is not None:
            return self._clf
        paths = [self.cascade_path] if self.cascade_path else []
        d = getattr(getattr(cv2, "data", None), "haarcascades", "")
        if d:
            paths += [os.path.join(d, f) for f in
                      ("haarcascade_frontalface_default.xml",
                       "haarcascade_frontalface_alt.xml")]
        for p in paths:
            if p and os.path.isfile(p):
                clf = cv2.CascadeClassifier(p)
                if not clf.empty():
                    self._clf, self._backend = clf, f"haar:{os.path.basename(p)}"
                    return clf
        raise VisualError("face backend became unavailable at detect time")

    def detect(self, bgr, timestamp, scene_id, width, height):
        import cv2
        clf = self._clf_or_raise()
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        out = []
        for (x, y, w, h) in clf.detectMultiScale(gray, 1.1, 4):
            out.append(asdict(FaceDetection(
                bbox=[int(x), int(y), int(w), int(h)], confidence=0.5,
                timestamp=timestamp, scene_id=scene_id,
                size_ratio=round(float(w * h) / max(width * height, 1), 4),
                backend=self._backend)))
        return out  # confidence 0.5 = heuristic detector, labeled as such


class ObjectDetectorAdapter(VisualDetector):
    name, kind = "object_detection", "object"

    def __init__(self, weights_path: str | None = None):
        self.weights_path = weights_path

    def is_available(self):
        if not self.weights_path:
            try:
                import importlib.util as _u
                ort = "onnxruntime present (CPU); " if _u.find_spec("onnxruntime") else ""
            except Exception:
                ort = ""
            return False, "none", (f"{ort}no detector weights configured "
                                   f"(visual_object_weights); no model downloaded")
        from pathlib import Path as _P
        if _P(self.weights_path).is_file():
            return True, "weights", f"user weights {self.weights_path}"
        return False, "none", f"configured weights missing: {self.weights_path}"

    def detect(self, bgr, timestamp, scene_id, width, height):
        raise VisualError("object backend has no runnable model in this build; "
                          "plug weights via visual_object_weights")


class EmbeddingAdapter(VisualDetector):
    """Extension point: references/hashes only, never giant vectors in JSON."""
    name, kind = "embeddings", "embedding"

    def __init__(self, model_ref: str | None = None):
        self.model_ref = model_ref

    def is_available(self):
        if not self.model_ref:
            return False, "none", ("no embedding model configured "
                                   "(visual_embedding_model); no model downloaded")
        return False, "none", (f"embedding model {self.model_ref} has no "
                               "registered runner in this build")

    def detect(self, bgr, timestamp, scene_id, width, height):
        raise VisualError("embedding runner not implemented; configure a model "
                          "and register a runner first")


def discover_capabilities(config: dict) -> dict:
    import cv2
    caps = {"opencv_metrics": {"status": "available", "backend": f"opencv-{cv2.__version__}",
                               "reason": "local computation, no model"}}
    face = FaceDetectorAdapter(config.get("visual_face_cascade_path"))
    obj = ObjectDetectorAdapter(config.get("visual_object_weights"))
    emb = EmbeddingAdapter(config.get("visual_embedding_model"))
    caps["face_detection"] = face.capability(bool(config.get("visual_enable_face")))
    caps["object_detection"] = obj.capability(bool(config.get("visual_enable_object")))
    caps["embeddings"] = emb.capability(bool(config.get("visual_enable_embeddings")))
    return caps


# ---------------- framing (explicit heuristics) ----------------

def estimate_framing(faces: list[dict], width: int, height: int,
                     gray=None) -> dict:
    """Heuristic shot estimate. Without faces the answer is honestly unknown.

    Cutoffs (largest face bbox/frame area): >0.25 close_up, >0.08 medium,
    else wide. Confidence 0.5 = heuristic, stated in `basis`.
    """
    com = center_of_mass(gray) if gray is not None else (0.5, 0.5)
    if not faces:
        return {"classification": "unknown", "confidence": 0.0,
                "basis": "no faces detected; framing requires a subject",
                "face_count": 0, "max_face_ratio": 0.0,
                "occupancy": 0.0, "center_of_mass": list(com)}
    ratios = [float(f.get("size_ratio", 0.0)) for f in faces]
    biggest = max(ratios)
    label = "close_up" if biggest > 0.25 else ("medium" if biggest > 0.08 else "wide")
    return {"classification": label, "confidence": 0.5,
            "basis": (f"heuristic: largest face covers {biggest:.3f} of frame "
                      f"(>0.25 close_up, >0.08 medium, else wide)"),
            "face_count": len(faces), "max_face_ratio": round(biggest, 4),
            "occupancy": round(sum(ratios), 4), "center_of_mass": list(com)}


# ---------------- analysis ----------------

def _versions() -> dict:
    import platform
    return {"python": platform.python_version(), "engine": "0.1.0"}


def _media_hash(source: str) -> str:
    return cache_key(source, "visual-source", {})


def analyze_visual(source: str, scenes_payload: dict, media: dict,
                   config: dict, frames_dir: str | Path | None = None,
                   log_file: Path | None = None) -> VisualAnalysisResult:
    """Sample frames, compute signals, aggregate per scene. Raises VisualError."""
    import time as _time
    t0 = _time.perf_counter()
    src = Path(source)
    if not src.is_file():
        raise VisualError(f"input not found: {src}")
    if not media.get("video_codec"):
        raise VisualError(f"no video stream in {src}: visual analysis needs video")
    scenes = sorted(scenes_payload.get("scenes", []) or [],
                    key=lambda s: (s["start"], s["end"]))
    if not scenes:
        raise VisualError("frame sampling needs at least one scene")
    duration = float(scenes_payload.get("duration") or media.get("duration", 0) or 0)
    fps = float(media.get("fps", 0) or 0)
    if duration <= 0 or fps <= 0:
        raise VisualError(f"cannot sample: fps={fps} duration={duration}")

    plan = plan_sampling(scenes, duration, fps, config)
    caps = discover_capabilities(config)
    warnings: list[str] = []
    for key in ("face_detection", "object_detection", "embeddings"):
        if caps[key]["status"] in ("unavailable", "failed"):
            warnings.append(f"{key}: {caps[key]['status']} ({caps[key]['reason']})")

    frames: list[VisualFrame] = []
    prev_gray = None
    frames_dir = Path(frames_dir) if frames_dir else Path(f"_visual_{time.time_ns()}")
    frames_dir.mkdir(parents=True, exist_ok=True)
    face_ad = FaceDetectorAdapter(config.get("visual_face_cascade_path"))
    obj_ad = ObjectDetectorAdapter(config.get("visual_object_weights"))
    face_on = caps["face_detection"]["status"] == "available"
    obj_on = caps["object_detection"]["status"] == "available"
    grays: list = []
    for i, sample in enumerate(plan):
        dest = frames_dir / f"f{i:04d}.jpg"
        try:
            from engine.rendering.ffmpeg import extract_frame as _ef
            _ef(src, sample["timestamp"], dest,
                timeout=120, log_file=log_file)
        except Exception as exc:
            warnings.append(f"frame @{sample['timestamp']}s skipped: {exc}")
            continue
        try:
            import cv2
            bgr = cv2.imread(str(dest))
            if bgr is None:
                raise VisualError(f"unreadable frame {dest.name}")
            gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
            m = frame_metrics(bgr)
            am, fm = motion_scores(prev_gray, gray)
            faces, objects = [], []
            if face_on:
                try:
                    faces = face_ad.detect(bgr, sample["timestamp"], sample["scene_id"],
                                           m["width"], m["height"])
                except Exception as exc:
                    warnings.append(f"face detect @{sample['timestamp']}s failed: {exc}")
                    face_on = False
                    caps["face_detection"] = {"status": "failed", "backend": "haar",
                                              "reason": str(exc)[:200]}
            if obj_on:
                try:
                    objects = obj_ad.detect(bgr, sample["timestamp"], sample["scene_id"],
                                            m["width"], m["height"])
                except Exception as exc:
                    warnings.append(f"object detect @{sample['timestamp']}s failed: {exc}")
                    obj_on = False
                    caps["object_detection"] = {"status": "failed", "backend": "weights",
                                                "reason": str(exc)[:200]}
            frames.append(VisualFrame(
                timestamp=sample["timestamp"], frame_index=sample["frame_index"],
                scene_id=sample["scene_id"], kind=sample["kind"],
                width=m["width"], height=m["height"], brightness=m["brightness"],
                brightness_p5=m["brightness_p5"], brightness_p95=m["brightness_p95"],
                contrast=m["contrast"], sharpness=m["sharpness"],
                motion_score=am, flow_score=fm, dhash=dhash(gray),
                quality_flags=quality_flags(m, config),
                faces=faces, objects=objects))
            grays.append(gray)
            prev_gray = gray
        except VisualError:
            raise
        except Exception as exc:
            warnings.append(f"frame @{sample['timestamp']}s failed: {exc}")
    if not frames:
        raise VisualError("no frames could be sampled/analyzed")

    summaries = _aggregate(frames, grays, scenes, config)
    continuity = _continuity(frames, grays, scenes, config)
    static_spans = _static_spans(frames, grays, config)
    return VisualAnalysisResult(
        source={"path": str(src), "media_hash": _media_hash(str(src))},
        configuration={k: config[k] for k in VISUAL_KEYS if k in config},
        capabilities=caps, scenes_analyzed=len(scenes),
        frame_samples=frames, scene_summaries=summaries,
        continuity=continuity, static_spans=static_spans,
        warnings=warnings, errors=[],
        processing_s=round(time.perf_counter() - t0, 3))


def _aggregate(frames: list[VisualFrame], grays: list,
               scenes: list[dict], config: dict) -> list[SceneVisualSummary]:
    import statistics as _st
    out: list[SceneVisualSummary] = []
    by_scene: dict[int, list[int]] = {}
    for i, f in enumerate(frames):
        by_scene.setdefault(f.scene_id, []).append(i)
    for sc in scenes:
        sid = int(sc.get("scene_id", -1))
        idxs = by_scene.get(sid, [])
        rep = frames[idxs[len(idxs) // 2]] if idxs else None
        sel = [frames[i] for i in idxs]
        bright = [f.brightness for f in sel]
        faces_n = [len(f.faces) for f in sel]
        labels: dict[str, int] = {}
        for f in sel:
            for o in f.objects:
                labels[o.get("label", "?")] = labels.get(o.get("label", "?"), 0) + 1
        quals: dict[str, int] = {}
        for f in sel:
            for q in f.quality_flags:
                quals[q] = quals.get(q, 0) + 1
        dup = 0
        for a, b in zip(idxs, idxs[1:]):
            if (hamming(frames[a].dhash, frames[b].dhash) <= config["visual_dup_hamming_thr"]
                    and hist_corr(grays[a], grays[b]) >= config["visual_hist_thr"]):
                dup += 1
        framing = estimate_framing(rep.faces if rep else [], rep.width if rep else 0,
                                   rep.height if rep else 0,
                                   grays[idxs[len(idxs) // 2]] if idxs else None)
        dur = float(sc["end"]) - float(sc["start"])
        out.append(SceneVisualSummary(
            scene_id=sid, start=float(sc["start"]), end=float(sc["end"]),
            duration=round(dur, 6), sampled_frame_count=len(idxs),
            brightness_mean=_r4(sum(bright) / len(bright)) if bright else 0.0,
            brightness_std=_r4(_st.pstdev(bright)) if len(bright) > 1 else 0.0,
            contrast_mean=_r4(sum(f.contrast for f in sel) / len(sel)) if sel else 0.0,
            sharpness_mean=_r4(sum(f.sharpness for f in sel) / len(sel)) if sel else 0.0,
            motion_mean=_r4(sum(f.motion_score for f in sel) / len(sel)) if sel else 0.0,
            motion_max=_r4(max((f.motion_score for f in sel), default=0.0)),
            face_count_mean=_r4(sum(faces_n) / len(faces_n)) if faces_n else 0.0,
            face_presence_ratio=_r4(sum(1 for n in faces_n if n > 0) / len(faces_n)) if faces_n else 0.0,
            object_labels=labels, duplicate_ratio=_r4(dup / max(len(idxs) - 1, 1)),
            quality_warnings=quals, framing=framing,
            representative_frame=({"timestamp": rep.timestamp,
                                   "frame_index": rep.frame_index,
                                   "kind": rep.kind} if rep else {})))
    return out


def _continuity(frames: list[VisualFrame], grays: list, scenes: list[dict],
                config: dict) -> list[dict]:
    out: list[dict] = []
    pos = {id(f): i for i, f in enumerate(frames)}
    by_scene: dict[int, list[VisualFrame]] = {}
    for f in frames:
        by_scene.setdefault(f.scene_id, []).append(f)
    ordered = sorted(scenes, key=lambda s: (s["start"], s["end"]))
    for left, right in zip(ordered, ordered[1:]):
        a_list, b_list = by_scene.get(int(left.get("scene_id", -1)), []), \
            by_scene.get(int(right.get("scene_id", -1)), [])
        if not a_list or not b_list:
            out.append({"boundary": float(right["start"]), "label": "unknown",
                        "reason": "a side has no samples", "metrics": {}})
            continue
        a, b = a_list[-1], b_list[0]
        corr = hist_corr(grays[pos[id(a)]], grays[pos[id(b)]])
        d_bright = _r4(abs(a.brightness - b.brightness))
        d_faces = len(b.faces) - len(a.faces)
        if corr >= config["visual_hist_thr"] and d_bright < 20:
            label = "stable"
        elif corr < config["visual_change_thr"] or d_bright > 60:
            label = "large_change"
        else:
            label = "changed"
        out.append({"boundary": float(right["start"]), "label": label,
                    "metrics": {"hist_corr": corr, "brightness_delta": d_bright,
                                "motion_at_entry": b.motion_score,
                                "face_count_delta": d_faces},
                    "reason": f"corr={corr} d_bright={d_bright} d_faces={d_faces}"})
    return out


def _static_spans(frames: list[VisualFrame], grays: list,
                  config: dict) -> list[dict]:
    """Runs of near-duplicate consecutive samples. Requires BOTH hash
    proximity AND histogram similarity: flat fields of different colors
    share dHash 0 but are not duplicates (verified 2026-09-17)."""
    spans = []
    run, run_grays = ([frames[0]], [grays[0]]) if frames else ([], [])
    for f, g in zip(frames[1:], grays[1:]):
        if (hamming(run[-1].dhash, f.dhash) <= config["visual_dup_hamming_thr"]
                and hist_corr(run_grays[-1], g) >= config["visual_hist_thr"]):
            run.append(f)
            run_grays.append(g)
        else:
            if len(run) > 1:
                spans.append({"start": run[0].timestamp, "end": run[-1].timestamp,
                              "frames": len(run), "scene_ids": sorted({x.scene_id for x in run})})
            run, run_grays = [f], [g]
    if len(run) > 1:
        spans.append({"start": run[0].timestamp, "end": run[-1].timestamp,
                      "frames": len(run), "scene_ids": sorted({x.scene_id for x in run})})
    return spans


def _detector_identity(config: dict) -> dict:
    return {"face": f"haar:{config.get('visual_face_cascade_path') or 'none'}",
            "object": f"weights:{config.get('visual_object_weights') or 'none'}",
            "embeddings": f"model:{config.get('visual_embedding_model') or 'none'}"}


def run_visual_for_project(project_id: str,
                           policy_overrides: dict | None = None,
                           force: bool = False) -> dict:
    """Project-scoped visual analysis with caching. No rendering, no EDL edits."""
    import json
    project = load_project(project_id)
    pid = project.id
    log_file = project_dir(pid) / "logs" / "run.jsonl"
    config = resolve_visual_config(policy_overrides)

    media_path = project_dir(pid) / "analysis" / "media_info.json"
    if not media_path.is_file():
        raise VisualError("missing analysis/media_info.json (run analyze first)")
    try:
        media = json.loads(media_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise VisualError(f"corrupt media_info.json: {exc}") from exc
    if not media.get("video_codec"):
        raise VisualError("no video stream: visual analysis needs video")
    scenes_path = project_dir(pid) / "analysis" / "scenes.json"
    if not scenes_path.is_file():
        raise VisualError("missing analysis/scenes.json (run scenes first)")
    try:
        scenes_payload = json.loads(scenes_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise VisualError(f"corrupt scenes.json: {exc}") from exc

    sampling = {"mode": config["visual_mode"],
                "samples_per_scene": config["visual_samples_per_scene"],
                "fps": config["visual_fps"], "max_frames": config["visual_max_frames"]}
    enabled = {"face": config["visual_enable_face"],
               "object": config["visual_enable_object"],
               "embeddings": config["visual_enable_embeddings"]}
    thresholds = {k: config[k] for k in
                  ("visual_dark_thr", "visual_bright_thr", "visual_contrast_thr",
                   "visual_sharpness_thr", "visual_dup_hamming_thr",
                   "visual_hist_thr", "visual_change_thr")}
    key = cache_key(project.input_path, "visual",
                    {"visual_version": VISUAL_VERSION, "sampling": sampling,
                     "enabled": enabled, "detectors": _detector_identity(config),
                     "thresholds": thresholds})
    t0 = time.perf_counter()
    hit = None if force else cached(key)
    if hit is not None:
        payload = json.loads(hit.read_text(encoding="utf-8"))
        payload["cached"] = True
        write_artifact(pid, "visual", "visual_analysis.json", payload)
        mark_stage(project, "visual", "cached", "visual/visual_analysis.json")
        log_event(log_file, "visual", "analyze", "cached",
                  time.perf_counter() - t0, "visual/visual_analysis.json",
                  _versions(), {"scenes": payload.get("scenes_analyzed", 0),
                                "frames": len(payload.get("frame_samples", []))})
        return {"project": pid, "cached": True, "result": payload}

    log_event(log_file, "visual", "sampling", "started", 0.0, "", _versions(),
              {"mode": sampling["mode"]})
    try:
        result = analyze_visual(project.input_path, scenes_payload, media, config,
                                frames_dir=project_dir(pid) / "visual" / "frames",
                                log_file=log_file)
    except VisualError as exc:
        mark_stage(project, "visual", "failed", str(exc)[:300])
        log_event(log_file, "visual", "analyze", "failed",
                  time.perf_counter() - t0, str(exc)[:300], _versions(), {})
        raise
    payload = asdict(result)
    write_artifact(pid, "visual", "visual_analysis.json", payload)
    store(key, payload)
    mark_stage(project, "visual", "done", "visual/visual_analysis.json")
    log_event(log_file, "visual", "analyze", "ok", time.perf_counter() - t0,
              "visual/visual_analysis.json", _versions(),
              {"scenes": result.scenes_analyzed,
               "frames": len(result.frame_samples),
               "capabilities": {k: v.get("status") for k, v in result.capabilities.items()}})
    return {"project": pid, "cached": False, "result": payload}
