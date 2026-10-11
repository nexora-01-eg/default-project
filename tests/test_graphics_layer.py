"""Graphics composition layer: schema, order, timing, propagation, manifest."""
import json
from pathlib import Path

import pytest

from engine.graphics import composition as _gc
from engine.graphics import icons as _icons
from engine.rendering.ffmpeg import color_clip, probe as _probe

TMP = Path("C:/Users/NOURSO~1/AppData/Local/Temp/opencode/graphics_layer")
KW = ["attention", "focus", "scroll", "watch", "view", "reveal"]


@pytest.fixture(scope="module", autouse=True)
def workdir():
    TMP.mkdir(parents=True, exist_ok=True)


def _reqs(label="HOOK"):
    return [
        {"kind": "icon", "intent": "attention metaphor", "keywords": KW,
         "role": "visual metaphor",
         "placement": {"x": 240, "y": 900, "w": 260, "h": 260},
         "timing": {"start": 1.0, "duration": 4.0}},
        {"kind": "label", "text": label, "role": "context tag",
         "placement": {"x": 700, "y": 300},
         "timing": {"start": 0.5, "duration": 5.0}}]


def test_propose_two_types_with_reasons():
    props = _gc.propose_shot_graphics("sh1", _reqs())
    assert [p["type"] for p in props] == ["icon", "label"]
    assert [p["layer"] for p in props] == [0, 1]
    assert all(p["reason"] and p["decided_by"] == "planner" for p in props)
    assert props[0]["candidate"]["name"] == "eye"
    assert json.loads(json.dumps(props))  # serializable


def test_unsupported_types_fail_explicitly():
    for kind in ("stat_card", "callout", "headline", "svg_graphic"):
        with pytest.raises(_icons.IconCapabilityError) as exc:
            _gc.propose_shot_graphics("sh1", [{"kind": kind}])
        assert exc.value.stage == "contract"
    with pytest.raises(_icons.IconCapabilityError):
        _gc.propose_shot_graphics("sh1", [{"kind": "hologram"}])


def test_director_rejections_recorded():
    dup = _reqs() + [dict(_reqs()[0])]
    rev = _gc.review_shot_graphics(_gc.propose_shot_graphics("sh1", dup[:2])
                                   + _gc.propose_shot_graphics("sh1", [dup[2]]))
    assert any("already used" in r["reason"] for r in rev["rejected"])

    clash = _reqs()
    clash[1]["placement"] = {"x": 250, "y": 910}  # overlaps icon in time
    rev2 = _gc.review_shot_graphics(_gc.propose_shot_graphics("sh1", clash))
    assert any("overlaps" in r["reason"] for r in rev2["rejected"])

    many = _reqs() + _reqs()
    rev3 = _gc.review_shot_graphics(_gc.propose_shot_graphics("sh1", many),
                                    max_per_shot=3)
    assert not rev3["approved"] and len(rev3["rejected"]) == 4

    arabic = _reqs()
    arabic[1]["text"] = "عنوان"
    with pytest.raises(_icons.IconCapabilityError):
        _gc.propose_shot_graphics("sh1", arabic)


def test_ordering_z_index_pixel():
    # two overlapping labels: later layer must win visibly
    base = TMP / "zbase.mp4"
    color_clip("0x0B102E", 1080, 1920, 2.0, base, fps=30)
    approved = [
        {"type": "label", "layer": 0, "shot_id": "z", "text": "AAAA",
         "placement": {"x": 400, "y": 900, "w": 1, "h": 1},
         "timing": {"start": 0.2, "duration": 1.6},
         "style": {"fg": "#FF0000", "size": 54, "pad": 28},
         "reason": "t", "decided_by": "planner", "approved_by": "director",
         "semantic_role": "t"},
        {"type": "label", "layer": 1, "shot_id": "z", "text": "B",
         "placement": {"x": 400, "y": 900, "w": 1, "h": 1},
         "timing": {"start": 0.2, "duration": 1.6},
         "style": {"fg": "#00FF00", "size": 54, "pad": 28},
         "reason": "t", "decided_by": "planner", "approved_by": "director",
         "semantic_role": "t"}]
    # measure real boxes then align exactly
    from engine.graphics.composition import _measure_label
    w0, h0, _ = _measure_label("AAAA", 54, 28)
    w1, h1, _ = _measure_label("B", 54, 28)
    approved[0]["placement"].update(w=w0, h=h0)
    approved[1]["placement"].update(w=w1, h=h1)
    out = TMP / "zout.mp4"
    if out.is_file():
        out.unlink()
    rec = _gc.compose_shot(base, approved, out, TMP / "zcache",
                           encoder="libx264")
    assert [ly["layer"] for ly in rec["layers"]] == [0, 1]
    from engine.rendering.ffmpeg import run_ffmpeg
    run_ffmpeg(["-loglevel", "error", "-ss", "1.0", "-i", str(out),
                "-frames:v", "1", "-vf", "crop=120:120:440:940",
                "-y", str(TMP / "zpx.png")], op="t")
    from PIL import Image
    px = Image.open(TMP / "zpx.png").convert("RGB").load()
    green = sum(1 for yy in range(120) for xx in range(120)
                if px[xx, yy][1] > 150 and px[xx, yy][0] < 150)
    assert green > 200, "top layer (green B) must cover bottom layer"


def test_propagation_and_determinism():
    import shutil
    base = TMP / "pbase.mp4"
    color_clip("0x0B102E", 1080, 1920, 6.0, base, fps=30)
    shutil.rmtree(TMP / "pcache", ignore_errors=True)
    rev = _gc.review_shot_graphics(_gc.propose_shot_graphics("sh1", _reqs()))
    assert len(rev["approved"]) == 2 and not rev["rejected"]
    outs = []
    for i in (1, 2):
        out = TMP / f"pout{i}.mp4"
        if out.is_file():
            out.unlink()
        rec = _gc.compose_shot(base, rev["approved"], out, TMP / "pcache",
                               encoder="libx264")
        outs.append((out, rec))
    assert outs[0][1]["cache_hits"] == 0
    assert outs[1][1]["cache_hits"] == 2  # identical rerun reuses rasters
    assert _probe(outs[0][0]).duration == pytest.approx(
        _probe(outs[1][0]).duration, abs=0.05)


def test_manifest_provenance_and_identity():
    m = json.loads((Path("projects/graphics_layer_v1/manifest.json"))
                   .read_text(encoding="utf-8"))
    assert m["verdict"] == "PASS"
    assert len(m["layers"]) == 2
    assert {ly["type"] for ly in m["layers"]} == {"icon", "label"}
    assert m["provenance"]["icon_eye_untouched"] is True
    assert m["provenance"]["background"]["untouched"] is True
    import hashlib
    eye = Path("F:/Arsenal/02_Icons/lucide/icons/eye.svg")
    assert hashlib.sha256(eye.read_bytes()).hexdigest() == \
        m["layers"][0]["asset"]["sha256"]
