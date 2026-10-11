"""Phase 7 tests — scene/shot detection (real PySceneDetect + real ffmpeg fallback).

No faked detector results: boundary asserts run against truly detected cuts
on synthetic fixtures with known structure.
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests" / "fixtures"

from engine.analysis.scenes import (
    SceneError,
    detect_scenes,
    detect_scenes_project,
    detector_version,
    resolve_threshold,
    validate_scenes,
)
from engine.core.models import Scene


@pytest.fixture(scope="module", autouse=True)
def fixtures():
    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg not on PATH")
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "make_test_media.py"), "--all"],
                       capture_output=True, text=True, timeout=600)
    assert r.returncode == 0, f"fixture build failed: {r.stderr[-1500:]}"
    for name in ("scenes_3x2s.mp4", "static_3s.mp4", "short_05s.mp4", "fade_3s.mp4"):
        assert (FIX / name).is_file(), f"missing fixture {name}"


# ---------- config / validation units (no detector) ----------

def test_resolve_threshold_defaults_and_errors():
    assert resolve_threshold("content", None) == 27.0
    assert resolve_threshold("threshold", None) == 12.0
    assert resolve_threshold("ffmpeg", None) == 0.4
    assert resolve_threshold("content", 10.0) == 10.0
    with pytest.raises(SceneError):
        resolve_threshold("bogus", None)
    with pytest.raises(SceneError):
        resolve_threshold("content", -1.0)


def test_validate_scenes_catches_bad_timelines():
    good = [Scene(0, 0.0, 2.0, start_frame=0, end_frame=60),
            Scene(1, 2.0, 4.0, start_frame=60, end_frame=120)]
    assert validate_scenes(good, 4.0, 30.0) == []
    bad = [Scene(0, -0.5, 2.0, start_frame=0, end_frame=60),
           Scene(1, 1.5, 1.0, start_frame=45, end_frame=30),   # overlap + inverted
           Scene(2, 3.0, 99.0, start_frame=90, end_frame=999)]  # overshoot
    assert len(validate_scenes(bad, 4.0, 30.0)) >= 3
    assert validate_scenes([], 4.0, 30.0) == ["no scenes"]


def test_detector_version_known():
    assert detector_version() not in ("", "missing")


# ---------- 1-4: known structures ----------

def test_known_boundaries_3x2s():
    r = detect_scenes(FIX / "scenes_3x2s.mp4")
    assert r.scene_count == 3
    bounds = [(s.start, s.end) for s in r.scenes]
    assert bounds == [(0.0, 2.0), (2.0, 4.0), (4.0, 6.0)]
    assert r.timeline_issues == []
    assert r.method == "content" and r.fallback_from == ""


def test_single_scene_static():
    r = detect_scenes(FIX / "static_3s.mp4")
    assert r.scene_count == 1
    assert (r.scenes[0].start, r.scenes[0].end) == (0.0, 3.0)
    assert r.note == "no cuts detected"  # zero cuts is data, not error


def test_very_short_video():
    r = detect_scenes(FIX / "short_05s.mp4")
    assert r.scene_count >= 1
    assert r.timeline_issues == []
    assert r.scenes[-1].end == pytest.approx(0.5, abs=0.1)


def test_threshold_method_and_fade_clip():
    # ThresholdDetector finds fades to/from black, NOT general hard cuts:
    # bright red/blue/green never drop below threshold -> single scene.
    r = detect_scenes(FIX / "scenes_3x2s.mp4", method="threshold")
    assert r.scene_count == 1 and r.timeline_issues == []
    assert r.method == "threshold"
    # Fade-in from black IS caught with a sensitive threshold + short min length.
    f = detect_scenes(FIX / "fade_3s.mp4", method="threshold",
                      threshold=30.0, min_scene_len_s=0.1)
    assert f.scene_count == 2
    assert f.scenes[0].end < 0.5  # fade-in boundary near the start
    assert f.timeline_issues == []


# ---------- 5: invalid input ----------

def test_invalid_input():
    with pytest.raises(SceneError, match="not found"):
        detect_scenes(FIX / "missing_123.mp4")
    with pytest.raises(SceneError, match="not found"):
        detect_scenes(FIX / "missing_123.mp4", method="ffmpeg")


# ---------- 6-8: timeline correctness ----------

def test_ordering_no_overlap_duration():
    r = detect_scenes(FIX / "scenes_3x2s.mp4")
    starts = [s.start for s in r.scenes]
    assert starts == sorted(starts)
    for a, b in zip(r.scenes, r.scenes[1:]):
        assert b.start >= a.end - 1e-6
    total = sum(s.duration for s in r.scenes)
    assert total == pytest.approx(r.duration, abs=1e-6)
    assert r.scenes[-1].end == pytest.approx(r.duration, abs=0.05)
    assert r.scenes[0].start == pytest.approx(0.0)


def test_frame_time_consistency():
    r = detect_scenes(FIX / "scenes_3x2s.mp4")
    assert r.fps == pytest.approx(30.0)
    for s in r.scenes:
        assert s.end_frame - s.start_frame == pytest.approx(s.duration * r.fps, abs=2.0)
    assert r.frame_count == pytest.approx(r.duration * r.fps, abs=2.0)


# ---------- ffmpeg fallback ----------

def test_ffmpeg_fallback_method():
    r = detect_scenes(FIX / "scenes_3x2s.mp4", method="ffmpeg")
    assert r.method == "ffmpeg" and r.detector == "ffmpeg"
    assert r.scene_count == 3
    assert [(s.start, s.end) for s in r.scenes] == [(0.0, 2.0), (2.0, 4.0), (4.0, 6.0)]
    assert r.timeline_issues == []


def test_auto_fallback_recorded(monkeypatch):
    import engine.analysis.scenes as mod
    monkeypatch.setattr(mod, "detect_pyscenedetect",
                        lambda *a, **k: (_ for _ in ()).throw(SceneError("boom")))
    r = mod.detect_scenes(FIX / "static_3s.mp4", method="content")
    assert r.method == "ffmpeg" and r.fallback_from == "content"
    assert "boom" in r.note


# ---------- 9-11: cache ----------

def test_cache_hit_and_invalidation(tmp_path):
    target = tmp_path / "scenes_cache.mp4"
    target.write_bytes((FIX / "scenes_3x2s.mp4").read_bytes())
    first = detect_scenes_project(str(target))
    assert first["cached"] is False and first["result"]["scene_count"] == 3
    second = detect_scenes_project(str(target))
    assert second["cached"] is True
    assert {k: v for k, v in second["result"].items() if k != "cached"} == \
           {k: v for k, v in first["result"].items() if k != "cached"}
    # Threshold change -> different entry (fresh detect, same count).
    other_t = detect_scenes_project(str(target), threshold=10.0)
    assert other_t["cached"] is False
    assert other_t["result"]["threshold"] == 10.0
    # Min-length change -> different entry AND merged scenes (2 s < 2.5 s).
    other_m = detect_scenes_project(str(target), min_scene_len_s=2.5)
    assert other_m["cached"] is False
    assert other_m["result"]["scene_count"] == 1
    artifact = ROOT / "projects" / second["project"] / "analysis" / "scenes.json"
    assert artifact.is_file()


# ---------- 12-13: CLI + serialization ----------

def test_cli_exit_behavior(capsys):
    from engine.cli import main
    assert main(["scenes", str(FIX / "scenes_3x2s.mp4")]) == 0
    out = capsys.readouterr().out
    assert "scenes  : 3" in out
    assert main(["scenes", str(FIX / "missing_123.mp4")]) == 2
    assert main(["scenes", str(FIX / "static_3s.mp4"), "--method", "bogus"]) == 2


def test_cli_json_and_artifact(capsys):
    import json as _json
    from engine.cli import main
    assert main(["scenes", str(FIX / "static_3s.mp4"), "--json"]) == 0
    out = capsys.readouterr().out
    payload = _json.loads(out[out.index("{"):])
    assert payload["scene_count"] == 1
    assert set(payload["scenes"][0]) >= {"scene_id", "start", "end", "duration",
                                         "start_frame", "end_frame"}


def test_performance_recorded():
    r = detect_scenes(FIX / "scenes_3x2s.mp4")
    assert r.processing_s > 0 and r.realtime_factor > 1.0
