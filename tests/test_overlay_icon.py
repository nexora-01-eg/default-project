"""Overlay icon path: contract, discovery, raster, execute, pixels, manifest."""
import hashlib
import json
from pathlib import Path

import pytest

from engine.graphics import icons as _icons
from engine.rendering.ffmpeg import color_clip, probe as _probe

TMP = Path("C:/Users/NOURSO~1/AppData/Local/Temp/opencode/overlay_icon")
EYE = _icons.LUCIDE_ROOT / "eye.svg"


@pytest.fixture(scope="module", autouse=True)
def workdir():
    TMP.mkdir(parents=True, exist_ok=True)
    if not EYE.is_file():
        pytest.skip("lucide eye.svg absent")


def _cand():
    cands = _icons.search_icons(
        "test intent",
        ["attention", "focus", "scroll", "watch", "view", "reveal"], top_k=5)
    assert cands and cands[0]["name"] == "eye"
    assert cands[0]["tags"], "top pick must carry tag evidence"
    return cands[0]


def _op(extra=None):
    op = _icons.build_overlay_op(
        _cand(), x=390, y=810, size=300, start=1.0, duration=4.0,
        reason="test overlay", decided_by="planner", approved_by="director")
    if extra:
        op.update(extra)
    return op


def test_discovery_semantic_not_filename():
    cands = _icons.search_icons("attention watch", ["watch", "reveal"])
    names = [c["name"] for c in cands]
    assert names[0] == "eye"  # tag evidence: view/watch/reveal/preview
    focus = _icons.search_icons("focus", ["focus"], top_k=50)
    assert "scan-eye" in [c["name"] for c in focus]
    assert all(c["tags"] or c["categories"] for c in focus)
    for c in cands:
        assert c["score"] > 0 and (c["tags"] or c["categories"])
        assert Path(c["source_path"]).is_file()
        assert len(c["sha256"]) == 64


def test_contract_valid_and_serializable():
    op = _op()
    assert _icons.validate_overlay_op(op, media_duration=6.0) == []
    assert _icons.validate_overlay_op(json.loads(json.dumps(op)),
                                       media_duration=6.0) == []


def test_contract_rejections():
    bad_color = _op()
    bad_color["style"]["color"] = "gold"
    assert _icons.validate_overlay_op(bad_color)

    oob = _op()
    oob["placement"]["x"] = 900
    assert _icons.validate_overlay_op(oob)

    no_reason = _op()
    no_reason["reason"] = ""
    assert _icons.validate_overlay_op(no_reason)

    no_approver = _op()
    no_approver["approved_by"] = ""
    assert _icons.validate_overlay_op(no_approver)

    overrun = _op()
    assert _icons.validate_overlay_op(overrun, media_duration=2.0)

    with pytest.raises(_icons.IconCapabilityError) as exc:
        _icons.execute_overlay("nope.mp4", "nope.png", no_reason,
                               TMP / "x.mp4")
    assert exc.value.stage == "contract"


def test_asset_rejections():
    op = _op()
    op["asset"]["source_path"] = str(TMP / "ghost.svg")
    assert _icons.validate_overlay_op(op)

    op2 = _op()
    op2["asset"]["source_path"] = str(EYE).replace(".svg", ".json")
    assert _icons.validate_overlay_op(op2)

    op3 = _op()
    op3["asset"]["sha256"] = "0" * 64
    assert _icons.validate_overlay_op(op3)


def test_missing_capability_structured():
    # chrome discovery failure path (PATH scrubbed, no fallback allowed)
    import engine.graphics.icons as m
    real = m._CHROME_CANDIDATES
    m._CHROME_CANDIDATES = ("Z:/definitely/not/here/chrome.exe",)
    try:
        with pytest.raises(_icons.IconCapabilityError) as exc2:
            m.find_chrome()
        assert exc2.value.stage == "raster"
    finally:
        m._CHROME_CANDIDATES = real


def test_raster_deterministic_and_faithful():
    c = _cand()
    a = _icons.rasterize_icon(c, TMP / "r1.png", size=120, color="#FFD98A")
    b = _icons.rasterize_icon(c, TMP / "r2.png", size=120, color="#FFD98A")
    assert a["png_sha256"] == b["png_sha256"]
    assert a["source_sha256"] == c["sha256"]
    # inner SVG bytes preserved verbatim in the wrapper (no redrawn icon)
    raw = EYE.read_text(encoding="utf-8")
    wrapped = _icons._wrap_svg(EYE, 120, "#FFD98A")
    for line in [ln for ln in raw.splitlines() if "<path" in ln or "<circle" in ln]:
        assert line.strip() in wrapped


def test_execute_mini_render_pixel_presence():
    c = _cand()
    base = TMP / "mini_base.mp4"
    color_clip("0x0B102E", 1080, 1920, 2.0, base, fps=30)
    op = _icons.build_overlay_op(
        c, x=390, y=810, size=300, start=0.5, duration=1.0,
        reason="mini proof", decided_by="planner", approved_by="director")
    assert _icons.validate_overlay_op(op, media_duration=2.0) == []
    png = _icons.rasterize_icon(c, TMP / "mini.png", size=300)["png"]
    out = TMP / "mini_out.mp4"
    if out.is_file():
        out.unlink()
    _icons.execute_overlay(base, png, op, out, encoder="libx264")
    info = _probe(out)
    assert abs(info.duration - 2.0) < 0.3
    # pixel presence: same-timestamp differential in the overlay box
    from engine.rendering.ffmpeg import run_ffmpeg
    fa, fb = TMP / "fa.png", TMP / "fb.png"
    run_ffmpeg(["-loglevel", "error", "-ss", "1.0", "-i", str(out),
                "-frames:v", "1", "-y", str(fa)], op="t")
    run_ffmpeg(["-loglevel", "error", "-ss", "1.0", "-i", str(base),
                "-frames:v", "1", "-y", str(fb)], op="t")
    from PIL import Image
    box = (390, 810, 690, 1110)
    ia = Image.open(fa).convert("RGB").crop(box)
    ib = Image.open(fb).convert("RGB").crop(box)
    pa, pb = ia.load(), ib.load()
    n = sum(1 for yy in range(ia.height) for xx in range(ia.width)
            if abs(pa[xx, yy][0] - pb[xx, yy][0])
            + abs(pa[xx, yy][1] - pb[xx, yy][1])
            + abs(pa[xx, yy][2] - pb[xx, yy][2]) > 40)
    assert n >= 2000, f"overlay absent in pixels (diff={n})"


def test_proof_manifest_answers_nine_questions():
    m = json.loads((Path("projects/overlay_proof_v1/manifest.json"))
                   .read_text(encoding="utf-8"))
    for q in ("q1_asset", "q2_why", "q3_planner", "q4_director",
              "q5_renderer", "q6_timing", "q7_placement", "q8_hashes",
              "q9_original_untouched"):
        assert q in m, f"manifest missing {q}"
    assert m["q9_original_untouched"] is True
    assert m["pixel_verification"]["verdict"] == "PASS"
    assert hashlib.sha256(
        Path(m["q1_asset"]["source_path"]).read_bytes()).hexdigest() == \
        m["q1_asset"]["sha256"]
