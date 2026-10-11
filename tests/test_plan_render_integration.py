# -*- coding: utf-8 -*-
"""Plan -> render integration: planner motion/camera drives assembly."""
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, ".")
import pytest

from engine.core.media import probe
from engine.rendering.ffmpeg import color_clip
from engine.tools import assemble as A
from engine.tools import contract_schema as CS
from engine.tools import visual_plan as VP
from engine.tools.adapters.base import ToolUnavailable

TMP = Path(r"C:\Users\NOURSO~1\AppData\Local\Temp\opencode\tooltest\integration")
TMP.mkdir(parents=True, exist_ok=True)


@pytest.fixture(scope="module")
def src():
    p = TMP / "src.mp4"
    color_clip("0x0B102E", 320, 240, 2.0, p, fps=15)
    return p


def _seg(motion, camera, **kw):
    d = {"shot_id": "t", "kind": "clip", "file": "src.mp4", "span": [0.0, 1.0],
         "motion": {"type": motion, "parameters": {}, "reason": "test",
                    "source": "planner"},
         "camera": {"type": camera, "parameters": {}, "reason": "test",
                    "source": "planner"}}
    d.update(kw)
    return d


def _render(seg, enc="libx264"):
    return A.render_shot(seg, TMP, TMP / "out", encoder=enc)


def test_01_push_renders_push(src):
    m = _render(_seg("push", "static"))
    assert m["manifest"]["op"] == "zoompan"
    assert m["manifest"]["requested_motion"] == "push"
    info = probe(m["part"])
    assert (info.width, info.height) == (1080, 1920)
    assert info.duration > 0.3


def test_02_hold_renders_cover(src):
    m = _render(_seg("hold", "static"))
    assert m["manifest"]["op"] == "cover"


def test_03_slide_renders_drift(src):
    m = _render(_seg("slide", "static"))
    assert m["manifest"]["op"] == "zoompan-x"


def test_04_static_stays_static(src):
    m = _render(_seg("none", "static"))
    assert m["manifest"]["op"] == "cover"
    assert m["manifest"]["effective_source"] in ("motion", "camera")


def test_05_pan_renders_pan(src):
    m = _render(_seg("hold", "pan"))
    assert m["manifest"]["op"] == "zoompan-x"
    assert m["manifest"]["effective_source"] == "camera"


def test_06_camera_static_no_invention(src):
    m = _render(_seg("push", "static"))
    assert m["manifest"]["requested_camera"] == "static"
    assert m["manifest"]["op"] == "zoompan"  # from motion, declared


def test_07_unsupported_motion_structured_error(src):
    with pytest.raises(ToolUnavailable) as e:
        _render(_seg("orbit", "static"))
    assert "CAPABILITY_MISSING" in str(e.value)
    assert getattr(e.value, "subsystem", "") == "motion"


def test_08_unsupported_camera_structured_error(src):
    with pytest.raises(ToolUnavailable) as e:
        _render(_seg("hold", "split"))
    assert getattr(e.value, "subsystem", "") == "camera"


def test_09_serialization_roundtrip():
    pool = [{"file": "a.mp4", "w": 1280, "h": 720, "dur": 30.0,
             "tags": ["neon"]}]
    narr = [{"id": "s1", "span": [0, 6], "text": "neon", "need": "neon"}]
    plan = VP.plan_shots_diverse(narr, pool, seed=7)
    safe = VP.to_json_safe(plan)
    text = json.dumps(safe, ensure_ascii=False)
    assert json.loads(text)["seed"] == 7


def test_10_contract_with_motion_camera_valid():
    c = {"project": "p", "canvas": {"w": 1080, "h": 1920, "fps": 30},
         "narration": {"segments": [{"id": "n1", "text": "hi",
                                     "start": 0.0}]},
         "shots": [{"shot_id": "sh_001", "start": 0.0, "end": 2.0,
                    "motion": {"type": "push", "parameters": {},
                               "reason": "r", "source": "planner"},
                    "camera": {"type": "static", "parameters": {},
                               "reason": "r", "source": "planner"}}]}
    assert CS.validate_contract(c)["valid"] is True


def test_11_manifest_records_execution(src):
    m = _render(_seg("pull", "static"))
    mf = m["manifest"]
    assert {"requested_motion", "requested_camera", "effective_source",
            "op", "params", "result"} <= set(mf)
    assert Path(mf["result"]).is_file()


def test_12_mismatch_detection():
    bad = {"requested_motion": "push", "requested_camera": "static",
           "op": "cover", "effective_source": "motion"}
    hit = A.detect_mismatch(bad)
    assert hit and hit["mismatch"] == "EXECUTION_MISMATCH"
    ok = {"requested_motion": "push", "requested_camera": "static",
          "op": "zoompan", "effective_source": "motion"}
    assert A.detect_mismatch(ok) is None


def test_13_deterministic_assembly(src):
    a = _render(_seg("hold", "static"), enc="libx264")["part"]
    h1 = hashlib.sha256(a.read_bytes()).hexdigest()
    a.unlink()
    b = _render(_seg("hold", "static"), enc="libx264")["part"]
    h2 = hashlib.sha256(b.read_bytes()).hexdigest()
    assert h1 == h2


def test_14_old_api_compatible():
    pool = [{"file": "a.mp4", "w": 1280, "h": 720, "dur": 30.0,
             "tags": ["neon"]}]
    shots = VP.storyboard([{"id": "s1", "span": [0, 8], "text": "neon",
                            "need": "neon"}], pool)
    assert shots and shots[0]["shot_id"] == "sh_001"


def test_15_diversity_regression_guarded():
    from engine.tools import visual_plan as _vp
    pool = [{"file": f, "w": 1280, "h": 720, "dur": 30.0, "tags": [t]}
            for f, t in [("n.mp4", "neon"), ("c.mp4", "code")]]
    narr = [{"id": "s1", "span": [0, 12], "text": "neon code",
             "need": "neon code"}]
    r = _vp.plan_shots_diverse(narr, pool, seed=7)
    assert r["planner_version"] == "visual_plan/3.0"
    assert r["seed"] == 7 and r["log"]
