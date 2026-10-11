"""Phase 11 tests — visual intelligence (synthetic-image units + real fixture).

Metric units use numpy-generated images (exact expectations, no ffmpeg).
Adapter tests use a labeled FakeDetector for LOGIC (never claimed as real
detection). Real detection absence is asserted honestly (unavailable).
"""
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests" / "fixtures"

from engine.analysis.visual import (
    VisualError,
    discover_capabilities,
    dhash,
    estimate_framing,
    frame_metrics,
    hamming,
    hist_corr,
    motion_scores,
    plan_sampling,
    quality_flags,
    resolve_visual_config,
    run_visual_for_project,
)
from engine.analysis import visual as visual_mod


@pytest.fixture()
def cv2np():
    cv2 = pytest.importorskip("cv2")
    np = pytest.importorskip("numpy")
    return cv2, np


def _img(cv2, np, kind, w=64, h=48):
    if kind == "black":
        return np.zeros((h, w, 3), np.uint8)
    if kind == "white":
        return np.full((h, w, 3), 255, np.uint8)
    if kind == "gradient":
        row = (np.arange(w) * 255 / (w - 1)).astype(np.uint8)
        g = np.tile(row, (h, 1))
        return cv2.merge([g, g, g])
    if kind == "checker":
        c = (np.indices((h, w)).sum(axis=0) % 2 * 255).astype(np.uint8)
        return cv2.merge([c, c, c])
    raise ValueError(kind)


def _cfg(**over):
    base = resolve_visual_config(None)
    base.update(over)
    return base


# ---------- frame sampling ----------

def test_sampling_deterministic_and_scene_ids():
    scenes = [{"scene_id": 0, "start": 0.0, "end": 2.0},
              {"scene_id": 1, "start": 2.0, "end": 6.0}]
    cfg = _cfg(visual_mode="bme")
    a = plan_sampling(scenes, 6.0, 30.0, cfg)
    b = plan_sampling(scenes, 6.0, 30.0, cfg)
    assert a == b  # deterministic
    assert [p["scene_id"] for p in a] == [0, 0, 0, 1, 1, 1]
    assert [p["kind"] for p in a] == ["begin", "middle", "end"] * 2
    assert a[0]["timestamp"] == 0.0 and a[0]["frame_index"] == 0


def test_sampling_frame_exactness():
    # Regression: 3-decimal rounding once pushed t=1.9667 past frame 59's
    # pts and dropped the frame. Timestamps must be frame-quantized.
    cfg = _cfg(visual_mode="bme")
    plan = plan_sampling([{"scene_id": 0, "start": 0.0, "end": 2.0}], 2.0, 30.0, cfg)
    for p in plan:
        assert abs(p["timestamp"] * 30.0 - round(p["timestamp"] * 30.0)) < 1e-6
        assert p["frame_index"] == round(p["timestamp"] * 30.0)


def test_sampling_modes_and_bounds():
    scenes = [{"scene_id": 0, "start": 0.0, "end": 4.0}]
    mid = plan_sampling(scenes, 4.0, 30.0, _cfg(visual_mode="middle"))
    assert len(mid) == 1 and mid[0]["timestamp"] == 2.0
    per = plan_sampling(scenes, 4.0, 30.0, _cfg(visual_mode="per_scene",
                                                visual_samples_per_scene=4))
    assert len(per) == 4 and per[0]["timestamp"] == 0.0
    fps = plan_sampling(scenes, 4.0, 30.0, _cfg(visual_mode="fps", visual_fps=2.0))
    assert [p["timestamp"] for p in fps] == [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5]
    assert all(sid == 0 for sid in [p["scene_id"] for p in fps])
    big = plan_sampling(scenes, 100.0, 30.0, _cfg(visual_mode="fps", visual_fps=30.0,
                                                  visual_max_frames=10))
    assert len(big) == 10  # bounded
    with pytest.raises(VisualError):
        plan_sampling([], 4.0, 30.0, _cfg())
    with pytest.raises(VisualError):
        plan_sampling(scenes, 4.0, 0.0, _cfg())
    tiny = plan_sampling([{"scene_id": 0, "start": 0.0, "end": 0.05}], 0.05, 30.0,
                         _cfg(visual_mode="bme"))
    assert len(tiny) >= 1  # degenerate clip collapses, never empties


def test_sampling_config_validation():
    with pytest.raises(VisualError):
        resolve_visual_config({"visual_mode": "every"})
    with pytest.raises(VisualError):
        resolve_visual_config({"visual_max_frames": 0})


# ---------- visual metrics (synthetic images) ----------

def test_brightness_contrast(cv2np):
    cv2, np = cv2np
    black, white = frame_metrics(_img(cv2, np, "black")), frame_metrics(_img(cv2, np, "white"))
    assert (black["brightness"], black["contrast"], black["sharpness"]) == (0.0, 0.0, 0.0)
    assert (white["brightness"], white["contrast"]) == (255.0, 0.0)
    grad = frame_metrics(_img(cv2, np, "gradient"))
    assert grad["brightness"] == pytest.approx(127.5, abs=1.0)
    assert grad["contrast"] > 50.0  # spread-out gradient


def test_sharpness_ordering(cv2np):
    cv2, np = cv2np
    sharp = frame_metrics(_img(cv2, np, "checker"))["sharpness"]
    blurred = cv2.GaussianBlur(_img(cv2, np, "checker"), (9, 9), 0)
    soft = frame_metrics(blurred)["sharpness"]
    assert sharp > soft >= 0.0  # Laplacian variance: edges > blur (documented metric)


def test_motion_zero_and_nonzero(cv2np):
    cv2, np = cv2np
    a = cv2.cvtColor(_img(cv2, np, "checker"), cv2.COLOR_BGR2GRAY)
    am, fm = motion_scores(a, a.copy())
    assert am == 0.0 and fm < 0.1  # absdiff exact; Farneback has a noise floor
    shifted = np.roll(a, 7, axis=1)  # odd shift inverts the period-2 checker
    am2, fm2 = motion_scores(a, shifted)
    assert am2 > 0.9 and fm2 > fm + 0.4  # real displacement, well above floor


def test_quality_flags_neutral():
    m = {"brightness": 10.0, "contrast": 5.0, "sharpness": 3.0}
    assert quality_flags(m, _cfg()) == ["dark_frame", "low_contrast", "blurry"]
    m2 = {"brightness": 240.0, "contrast": 60.0, "sharpness": 500.0}
    assert quality_flags(m2, _cfg()) == ["bright_frame"]
    m3 = {"brightness": 120.0, "contrast": 60.0, "sharpness": 500.0}
    assert quality_flags(m3, _cfg()) == []
    assert "bad video" not in str(quality_flags(m, _cfg()))  # neutral labels only


def test_dhash_duplicates(cv2np):
    cv2, np = cv2np
    a = cv2.cvtColor(_img(cv2, np, "checker"), cv2.COLOR_BGR2GRAY)
    assert hamming(dhash(a), dhash(a.copy())) == 0
    b = cv2.cvtColor(_img(cv2, np, "gradient"), cv2.COLOR_BGR2GRAY)
    assert hamming(dhash(a), dhash(b)) > 5  # distinct content, distant hashes
    assert hist_corr(a, a.copy()) == pytest.approx(1.0)
    assert hist_corr(a, b) < 0.9


# ---------- capability handling ----------

def test_capabilities_honest_on_this_machine():
    caps = discover_capabilities(_cfg())
    assert caps["opencv_metrics"]["status"] == "available"
    assert caps["face_detection"]["status"] == "unavailable"
    assert caps["face_detection"]["reason"]  # why, not just what
    assert caps["object_detection"]["status"] == "unavailable"
    assert caps["embeddings"]["status"] == "skipped"  # disabled by default config
    on = discover_capabilities(_cfg(visual_enable_embeddings=True))
    assert on["embeddings"]["status"] == "unavailable"  # enabled, but no model
    assert on["embeddings"]["reason"]
    assert "download" in (caps["face_detection"]["reason"] +
                          caps["object_detection"]["reason"]).lower()


def test_capability_skipped_and_failed():
    from engine.analysis.visual import EmbeddingAdapter, VisualDetector
    assert EmbeddingAdapter(None).capability(False)["status"] == "skipped"

    class Boom(VisualDetector):
        name, kind = "boom", "test"

        def is_available(self):
            raise RuntimeError("init exploded")

    assert Boom().capability(True)["status"] == "failed"  # never raises


def test_fake_detector_adapter_logic():
    # Labeled LOGIC test (framing math + adapter plumbing), not detection.
    from engine.analysis.visual import FaceDetectorAdapter
    import cv2
    import numpy as np

    class FakeFace(FaceDetectorAdapter):
        def is_available(self):
            return True, "fake", "injected for logic test"

        def detect(self, bgr, timestamp, scene_id, width, height):
            return [{"bbox": [10, 10, 320, 320], "confidence": 0.5,
                     "timestamp": timestamp, "scene_id": scene_id,
                     "size_ratio": round(320 * 320 / (width * height), 4),
                     "backend": "fake"}]

    det = FakeFace()
    assert det.capability(True)["status"] == "available"
    bgr = np.zeros((360, 640, 3), np.uint8)
    found = det.detect(bgr, 1.0, 0, 640, 360)
    framing = estimate_framing(found, 640, 360)
    assert framing["classification"] == "close_up"  # 0.44 > 0.25
    assert framing["confidence"] == 0.5 and "heuristic" in framing["basis"]
    assert estimate_framing([], 640, 360)["classification"] == "unknown"


def test_framing_cutoffs():
    assert estimate_framing([{"size_ratio": 0.30}], 100, 100)["classification"] == "close_up"
    assert estimate_framing([{"size_ratio": 0.10}], 100, 100)["classification"] == "medium"
    assert estimate_framing([{"size_ratio": 0.02}], 100, 100)["classification"] == "wide"


# ---------- cache ----------

def test_visual_cache_hit_and_invalidation():
    import time
    from engine.analysis.visual import run_visual_for_project as run
    from engine.core.project_store import create_project, write_artifact
    tag = f"vis_{time.time_ns()}.mp4"
    p = create_project(tag)
    media = {"path": tag, "video_codec": "h264", "duration": 6.0, "fps": 30.0,
             "width": 640, "height": 360}
    scenes = {"duration": 6.0, "scenes": [{"scene_id": 0, "start": 0.0, "end": 6.0,
                                           "duration": 6.0, "start_frame": 0,
                                           "end_frame": 180}]}
    write_artifact(p.id, "analysis", "media_info.json", media)
    write_artifact(p.id, "analysis", "scenes.json", scenes)
    import shutil as _sh
    _sh.copy(FIX / "scenes_3x2s.mp4", ROOT / "projects" / p.id / "input_copy.mp4")
    # Point the project at a real file with matching duration/fps.
    from engine.core.project_store import load_project, save_project
    proj = load_project(p.id)
    proj.input_path = str(ROOT / "projects" / p.id / "input_copy.mp4")
    save_project(proj)
    first = run(p.id)
    assert first["cached"] is False and first["result"]["scenes_analyzed"] == 1
    second = run(p.id)
    assert second["cached"] is True
    third = run(p.id, {"visual_dark_thr": 99.0})  # threshold change invalidates
    assert third["cached"] is False
    art = ROOT / "projects" / p.id / "visual" / "visual_analysis.json"
    assert art.is_file()


# ---------- CLI ----------

def test_cli_success_error(capsys):
    from engine.cli import main
    from engine.core.project_store import create_project, write_artifact
    p = create_project(str(FIX / "static_3s.mp4"))
    from engine.core.media import probe
    info = probe(FIX / "static_3s.mp4")
    from dataclasses import asdict
    write_artifact(p.id, "analysis", "media_info.json", asdict(info))
    write_artifact(p.id, "analysis", "scenes.json",
                   {"duration": info.duration,
                    "scenes": [{"scene_id": 0, "start": 0.0, "end": info.duration,
                                "duration": info.duration, "start_frame": 0,
                                "end_frame": 0}]})
    assert main(["visual", p.id, "--mode", "middle"]) == 0
    out = capsys.readouterr().out
    assert "opencv_metrics" in out and "frames: 1" in out
    assert main(["visual", "project_nope_123"]) == 2
    q = create_project(str(FIX / "static_3s.mp4"))  # no analysis artifacts
    assert main(["visual", q.id]) == 2


# ---------- real fixture verification ----------

@pytest.fixture(scope="module")
def real_visual():
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        pytest.skip("ffmpeg/ffprobe not on PATH")
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "make_test_media.py"), "--all"],
                       capture_output=True, text=True, timeout=600)
    assert r.returncode == 0
    from engine.core.orchestrator import run_inspect
    from engine.analysis.scenes import detect_scenes_project
    pid = run_inspect(str(FIX / "scenes_3x2s.mp4"))["project"]
    detect_scenes_project(str(FIX / "scenes_3x2s.mp4"), project_id=pid)
    return pid


def test_real_scene_aware_analysis(real_visual):
    res = run_visual_for_project(real_visual)
    r = res["result"]
    assert r["scenes_analyzed"] == 3
    assert len(r["frame_samples"]) == 9  # bme default x 3 scenes
    assert [s["scene_id"] for s in r["scene_summaries"]] == [0, 1, 2]
    assert all(s["sampled_frame_count"] == 3 for s in r["scene_summaries"])
    assert r["capabilities"]["face_detection"]["status"] == "unavailable"  # documented
    assert r["capabilities"]["object_detection"]["status"] == "unavailable"
    assert len(r["continuity"]) == 2
    assert {c["label"] for c in r["continuity"]} <= {"stable", "changed", "large_change"}
    assert r["processing_s"] > 0


def test_real_deterministic_and_cached(real_visual):
    from engine.analysis.visual import run_visual_for_project as run
    a = run(real_visual, force=True)
    assert a["cached"] is False
    b = run(real_visual)
    assert b["cached"] is True
    drop = lambda d: {k: v for k, v in d.items() if k not in ("cached",)}
    assert drop(b["result"]) == drop(a["result"])  # deterministic (processing_s equal here too)


def test_real_metrics_sane(real_visual):
    res = run_visual_for_project(real_visual)
    by_id = {s["scene_id"]: s for s in res["result"]["scene_summaries"]}
    assert by_id[0]["brightness_mean"] == pytest.approx(76.0, abs=1.0)   # red
    assert by_id[1]["brightness_mean"] == pytest.approx(29.0, abs=1.0)   # blue
    assert by_id[0]["sharpness_mean"] == 0.0  # flat fields: honestly zero
    assert all(s["framing"]["classification"] == "unknown" for s in by_id.values())
