"""From-scratch production gateway ops (fade_audio, color_clip, concat paths)."""
from pathlib import Path

import pytest

from engine.core.media import probe
from engine.rendering.ffmpeg import (
    color_clip,
    concat,
    fade_audio,
    trim,
)

TMP = Path("C:/Users/NOURSO~1/AppData/Local/Temp/opencode/fs_ops")
FIX = Path("tests/fixtures/tone_5s.mp4")


@pytest.fixture(scope="module", autouse=True)
def workdir():
    TMP.mkdir(parents=True, exist_ok=True)


def test_color_clip():
    out = TMP / "card.mp4"
    if out.is_file():
        out.unlink()
    color_clip("0x0B102E", 1080, 1920, 2.5, out, fps=30)
    info = probe(out)
    assert (info.width, info.height) == (1080, 1920)
    assert abs(info.duration - 2.5) < 0.2
    with pytest.raises(ValueError):
        color_clip("blue", 1080, 1920, 1.0, TMP / "x.mp4")


def test_fade_audio():
    from engine.rendering.ffmpeg import extract_audio
    wav = Path("tests/fixtures/tone_5s.wav")
    if not wav.is_file():
        pytest.skip("needs tone wav fixture")
    src = TMP / "bed.m4a"
    extract_audio(str(wav), src, duration=3.0)
    out = TMP / "bed_fade.m4a"
    fade_audio(src, out, fade_in=0.5, fade_out=0.5)
    assert abs(probe(out).duration - probe(src).duration) < 0.15
    with pytest.raises(ValueError):
        fade_audio(src, TMP / "x.m4a")


def test_concat_relative_paths():
    a = TMP / "rel_a.mp4"
    b = TMP / "rel_b.mp4"
    trim(str(FIX), 0.0, 1.0, a, encoder="libx264")
    trim(str(FIX), 1.0, 2.0, b, encoder="libx264")
    out = TMP / "rel_joined.mp4"
    if out.is_file():
        out.unlink()
    # relative part paths (the historical failure mode)
    import os
    cwd = os.getcwd()
    os.chdir(TMP)
    try:
        concat(["rel_a.mp4", "rel_b.mp4"], "rel_joined.mp4",
               reencode=True, encoder="libx264")
    finally:
        os.chdir(cwd)
    assert abs(probe(out).duration - 2.0) < 0.2
