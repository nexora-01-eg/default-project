"""Phase 4 tests — FFmpeg service layer, encoder detection, cut/concat.

Real ffmpeg on synthetic fixtures. Hardware-encoder tests SKIP gracefully
when the encoder is not smoke-verified on this machine (never fail).
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests" / "fixtures"

from engine.core.media import MediaProbeError, probe
from engine.rendering.ffmpeg import (
    FfmpegError,
    ValidateExpect,
    apply_vf,
    concat,
    detect_encoders,
    extract_audio,
    extract_frame,
    mix_audio,
    render_keep,
    select_encoder,
    trim,
    validate_output,
)


@pytest.fixture(scope="module", autouse=True)
def fixtures():
    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg not on PATH")
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "make_test_media.py"), "--all"],
                       capture_output=True, text=True, timeout=600)
    assert r.returncode == 0, f"fixture build failed: {r.stderr[-1500:]}"


def _verified(name: str) -> bool:
    return bool(detect_encoders()["encoders"].get(name, {}).get("verified"))


# ---------- 1-4: encoder detection ----------

def test_encoder_detection():
    det = detect_encoders()
    assert "ffmpeg" in det["ffmpeg_version"]
    enc = det["encoders"]
    assert enc["libx264"]["listed"] is True
    assert enc["libx264"]["verified"] is True
    sel = select_encoder()
    assert sel["selected_encoder"] in ("h264_nvenc", "h264_qsv", "h264_amf", "libx264")
    assert isinstance(sel["hardware_acceleration"], bool)
    assert sel["reason"]


def test_cpu_fallback_forced():
    sel = select_encoder(["libx264"])
    assert sel["selected_encoder"] == "libx264"
    assert sel["hardware_acceleration"] is False


def test_nvenc_if_available(tmp_path):
    if not _verified("h264_nvenc"):
        pytest.skip("h264_nvenc not verified on this machine")
    out = trim(FIX / "tone_5s.mp4", 0, 1, tmp_path / "nv.mp4", encoder="h264_nvenc")
    assert probe(out).video_codec == "h264"


def test_qsv_if_available(tmp_path):
    if not _verified("h264_qsv"):
        pytest.skip("h264_qsv not verified on this machine")
    out = trim(FIX / "tone_5s.mp4", 0, 1, tmp_path / "qsv.mp4", encoder="h264_qsv")
    assert probe(out).video_codec == "h264"


# ---------- 5-9: cut / concat / preservation ----------

def test_single_cut(tmp_path):
    out = trim(FIX / "tone_5s.mp4", 1, 3, tmp_path / "cut.mp4")
    assert probe(out).duration == pytest.approx(2.0, abs=0.3)


def test_multi_cut_render_keep(tmp_path):
    out = render_keep(FIX / "tone_5s.mp4", [(0, 1), (2, 3), (4, 5)], tmp_path / "keep.mp4")
    assert probe(out).duration == pytest.approx(3.0, abs=0.4)


def test_concat_copy(tmp_path):
    a = trim(FIX / "tone_5s.mp4", 0, 1, tmp_path / "a.mp4", accurate=False)
    b = trim(FIX / "tone_5s.mp4", 1, 2, tmp_path / "b.mp4", accurate=False)
    out = concat([a, b], tmp_path / "joined.mp4")
    assert probe(out).duration == pytest.approx(2.0, abs=0.5)


def test_audio_preserved(tmp_path):
    out = render_keep(FIX / "tone_5s.mp4", [(0, 2)], tmp_path / "ap.mp4")
    info = probe(out)
    assert info.audio_codec == "aac"
    assert info.audio_channels == 1
    assert info.sample_rate == 44100


def test_video_preserved(tmp_path):
    out = render_keep(FIX / "tone_5s.mp4", [(0, 2)], tmp_path / "vp.mp4")
    info = probe(out)
    assert (info.width, info.height) == (640, 360)
    assert info.fps == pytest.approx(30.0, abs=1.0)
    assert info.video_codec == "h264"


# ---------- 10-12: errors + validation ----------

def test_invalid_input(tmp_path):
    with pytest.raises(MediaProbeError):
        trim(FIX / "missing_123.mp4", 0, 1, tmp_path / "x.mp4")


def test_invalid_timestamps(tmp_path):
    src = FIX / "tone_5s.mp4"
    with pytest.raises(ValueError):
        trim(src, 3, 1, tmp_path / "x.mp4")       # end <= start
    with pytest.raises(ValueError):
        trim(src, -1, 2, tmp_path / "x.mp4")      # negative
    with pytest.raises(ValueError):
        trim(src, 99, 100, tmp_path / "x.mp4")    # beyond duration
    with pytest.raises(ValueError):
        render_keep(src, [], tmp_path / "x.mp4")  # empty EDL


def test_output_validation(tmp_path):
    out = trim(FIX / "tone_5s.mp4", 0, 2, tmp_path / "v.mp4")
    ok = validate_output(out, ValidateExpect(duration=2.0, width=640, height=360,
                                             video_codec="h264", require_audio=True))
    assert ok.verdict == "pass"
    bad = validate_output(out, ValidateExpect(duration=999.0))
    assert bad.verdict == "fail"
    assert any(not c.passed for c in bad.checks)
    missing = validate_output(tmp_path / "nope.mp4", ValidateExpect())
    assert missing.verdict == "fail"


# ---------- 13: full pipeline integration ----------

def test_full_pipeline_silence_cut(tmp_path):
    from engine.analysis.audio import analyze_audio
    a = analyze_audio(FIX / "mixed_6s.mp4")
    assert len(a.silence) == 1  # Phase 3 output drives the EDL
    keep = [(s.start, s.end) for s in a.non_silent]
    out = render_keep(FIX / "mixed_6s.mp4", keep, tmp_path / "nosil.mp4")
    info = probe(out)
    assert info.duration == pytest.approx(4.0, abs=0.5)
    report = validate_output(out, ValidateExpect(duration=4.0, duration_tol=0.5,
                                                 require_audio=True))
    assert report.verdict == "pass"


def test_extract_audio_and_frame(tmp_path):
    wav = extract_audio(FIX / "tone_5s.mp4", tmp_path / "a.wav")
    assert probe(wav).audio_codec == "pcm_s16le"
    jpg = extract_frame(FIX / "tone_5s.mp4", 1.0, tmp_path / "f.jpg")
    assert jpg.stat().st_size > 0
    with pytest.raises(ValueError):
        extract_audio(FIX / "silent_video.mp4", tmp_path / "b.wav")  # no audio


def test_apply_vf_resize_and_mix(tmp_path):
    small = apply_vf(FIX / "tone_5s.mp4", "scale=320:180", tmp_path / "small.mp4")
    assert (probe(small).width, probe(small).height) == (320, 180)
    mixed = mix_audio([FIX / "tone_5s.wav", FIX / "silence_5s.wav"], tmp_path / "mix.m4a")
    assert probe(mixed).duration == pytest.approx(5.0, abs=0.3)


def test_cli_render(capsys):
    from engine.cli import main
    from engine.core.orchestrator import run_inspect
    pid = run_inspect(str(FIX / "mixed_6s.mp4"))["project"]
    rc = main(["render", pid, "--keep", "0-2,4-6", "--out", "cli_test.mp4"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["validation"]["verdict"] == "pass"
    assert Path(out["output"]).is_file()
    assert probe(Path(out["output"])).duration == pytest.approx(4.0, abs=0.5)
