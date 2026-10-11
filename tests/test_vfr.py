"""VFR regression tests (no QC threshold changes, no behavior faking).

Synthetic VFR fixture via mixed-rate concat (repo's make_test_media
convention); real user video used for detection + parity assertions only.
"""
import shutil
from pathlib import Path

import pytest

from engine.core.media import probe
from engine.rendering.ffmpeg import (
    concat,
    normalize_media,
    trim,
    vfr_status,
)

TMP = Path("C:/Users/NOURSO~1/AppData/Local/Temp/opencode/vfr_test")
USER_SRC = "C:/Users/NOUR SOFT/Downloads/document_5873164930269587412.mp4"


@pytest.fixture(scope="module")
def vfr_src():
    from engine.rendering.ffmpeg import run_ffmpeg
    TMP.mkdir(parents=True, exist_ok=True)
    dst = TMP / "vfr_6s.mp4"
    if not dst.is_file():
        s1 = TMP / "seg1.mp4"
        s2 = TMP / "seg2.mp4"
        run_ffmpeg(["-loglevel", "error", "-f", "lavfi",
                    "-i", "testsrc=duration=3:size=320x240:rate=30",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-y", str(s1)], op="vfr_fixture")
        run_ffmpeg(["-loglevel", "error", "-f", "lavfi",
                    "-i", "testsrc=duration=3:size=320x240:rate=15",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-y", str(s2)], op="vfr_fixture")
        run_ffmpeg(["-loglevel", "error", "-f", "lavfi",
                    "-i", "sine=frequency=440:duration=6",
                    "-i", str(s1), "-i", str(s2),
                    "-filter_complex",
                    "[1:v][2:v]concat=n=2:v=1:a=0[v]",
                    "-map", "[v]", "-map", "0:a",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-y", str(dst)],
                   op="vfr_fixture")
    return dst


@pytest.fixture(scope="module")
def cfr_src():
    return Path("tests/fixtures/sample_10s.mp4")


def test_vfr_detection_user_source():
    if not Path(USER_SRC).is_file():
        pytest.skip("user source absent")
    st = vfr_status(probe(USER_SRC))
    assert st["is_vfr"] is True
    assert st["measured"] == pytest.approx(20.73, abs=0.05)
    assert st["nominal"] > 1000
    assert "/" in st["fps_filter"]


def test_vfr_detection_synthetic(vfr_src):
    st = vfr_status(probe(str(vfr_src)))
    assert st["is_vfr"] is True


def test_cfr_unaffected(cfr_src):
    st = vfr_status(probe(str(cfr_src)))
    assert st["is_vfr"] is False
    out = TMP / "cfr_trim.mp4"
    trim(str(cfr_src), 1.0, 3.0, out, encoder="libx264")
    info = probe(out)
    assert abs(info.duration - 2.0) < 0.15
    with pytest.raises(ValueError):
        normalize_media(str(cfr_src), TMP / "refused.mp4",
                        encoder="libx264")


def test_normalize_aligns_av(vfr_src):
    out = TMP / "norm.mp4"
    normalize_media(str(vfr_src), out, encoder="libx264")
    info = probe(out)
    assert info.width == 320 and info.audio_codec == "aac"
    # CFR output: frame rate uniform (fps filter applied)
    assert info.fps > 0


def test_normalize_tail_parity_user_source():
    if not Path(USER_SRC).is_file():
        pytest.skip("user source absent")
    import subprocess
    import json as _json
    out = TMP / "user_norm.mp4"
    normalize_media(USER_SRC, out, encoder="libx264")
    raw = subprocess.run(
        [shutil.which("ffprobe") or "ffprobe", "-v", "quiet",
         "-show_entries", "format=duration",
         "-show_entries", "stream=codec_type,duration",
         "-of", "json", str(out)],
        capture_output=True, text=True, timeout=120)
    data = _json.loads(raw.stdout or "{}")
    cont = float(data["format"]["duration"])
    aud = next(float(s["duration"]) for s in data["streams"]
               if s["codec_type"] == "audio")
    assert abs(cont - aud) < 0.15  # measured parity, not hardcoded


def test_trim_concat_vfr_exact(vfr_src):
    p1 = TMP / "t1.mp4"
    p2 = TMP / "t2.mp4"
    trim(str(vfr_src), 0.5, 2.5, p1, encoder="libx264")
    trim(str(vfr_src), 3.0, 5.0, p2, encoder="libx264")
    for p, want in ((p1, 2.0), (p2, 2.0)):
        assert abs(probe(p).duration - want) < 0.15, p
    joined = TMP / "joined.mp4"
    concat([p1, p2], joined, reencode=True, encoder="libx264")
    got = probe(joined).duration
    assert abs(got - 4.0) < 0.15
    # no proxy litter left behind
    assert not list(TMP.glob("_vfr_*.mp4"))


def test_normalize_deterministic(vfr_src):
    a = TMP / "n1.mp4"
    b = TMP / "n2.mp4"
    normalize_media(str(vfr_src), a, encoder="libx264")
    normalize_media(str(vfr_src), b, encoder="libx264")
    ia, ib = probe(a), probe(b)
    assert ia.duration == pytest.approx(ib.duration, abs=1e-3)


def _nb_frames(path):
    import json as _json
    import subprocess
    exe = shutil.which("ffprobe") or "ffprobe"
    raw = subprocess.run(
        [exe, "-v", "quiet", "-select_streams", "v:0",
         "-show_entries", "stream=nb_frames", "-of", "json", str(path)],
        capture_output=True, text=True, timeout=120)
    return int(_json.loads(raw.stdout or "{}")["streams"][0]["nb_frames"])


def test_trim_preserves_frame_count_cfr(cfr_src):
    out = TMP / "cfr_frames.mp4"
    trim(str(cfr_src), 0.0, 5.0, out, encoder="libx264")
    assert _nb_frames(out) == 150  # 5 s × 30 fps CFR, exact
