"""Adapter validation: real binaries/APIs, CPU-only, deterministic checks."""
import sys
from pathlib import Path

sys.path.insert(0, ".")
import pytest

from engine.core.media import probe
from engine.rendering.ffmpeg import color_clip, make_silence
from engine.tools.adapters.providers import get
from engine.tools.adapters.base import ToolUnavailable

ROOT = Path(".").resolve()
TMP = Path(r"C:\Users\NOURSO~1\AppData\Local\Temp\opencode\tooltest")
TMP.mkdir(parents=True, exist_ok=True)
FIX = ROOT / "tests" / "fixtures"
SAPI = FIX / "speech_sapi.wav"


def test_ffmpeg_camera_push():
    src = TMP / "push_src.mp4"
    color_clip("0x0B102E", 320, 480, 2.0, src, fps=30)
    dst = TMP / "push_out.mp4"
    art = get("ffmpeg").run({"op": "camera_push", "src": str(src),
                             "dst": str(dst), "zoom_from": 1.0,
                             "zoom_to": 1.1, "encoder": "libx264"})
    info = probe(dst)
    assert (info.width, info.height) == (1080, 1920)
    assert abs(info.duration - 2.0) < 0.3
    assert art["provider"] == "ffmpeg"


def test_whisper_word_timing():
    if not SAPI.is_file():
        pytest.skip("SAPI fixture absent")
    art = get("faster-whisper").run({"src": str(SAPI),
                                     "out": str(TMP / "words.json"),
                                     "model": "tiny", "language": "en"})
    assert art["words"] >= 10 and art["language"] == "en"


def test_piper_adapter():
    art = get("piper").run({"text": "اختبار سريع.",
                            "dst": str(TMP / "piper_test.wav")})
    info = probe(TMP / "piper_test.wav")
    assert info.audio_codec and info.duration > 0.5


def test_scenedetect_adapter():
    clip = TMP / "sd_src.mp4"
    color_clip("0x0B102E", 320, 480, 3.0, clip, fps=15)
    art = get("scenedetect").run({"src": str(clip),
                                  "out": str(TMP / "scenes.json")})
    assert art["count"] >= 0


def test_librosa_beats():
    src = r"F:\Arsenal\04_Music\Incompetech\Aitech.mp3"
    art = get("librosa").run({"src": src, "out": str(TMP / "beats.json")})
    assert art["tempo_bpm"] > 40


def test_loudness_adapter():
    src = (r"C:\Users\NOUR SOFT\Documents\Default Project\tools\tts\piper"
           r"\tests\narr\L1_06.wav")
    art = get("pyloudnorm").run({"src": src,
                                 "dst": str(TMP / "loud.wav"),
                                 "target_lufs": -16.0})
    assert Path(TMP / "loud.wav").is_file()


def test_vad_adapter():
    from engine.rendering.ffmpeg import extract_audio
    conv = extract_audio(
        r"C:\Users\NOUR SOFT\Documents\Default Project\tools\tts\piper"
        r"\tests\narr\L2_06.wav", str(TMP / "vad16.wav"),
        sample_rate=16000, channels=1)
    art = get("webrtcvad").run({"src": str(conv),
                                "out": str(TMP / "vad.json")})
    assert art["spans"] >= 1


def test_otio_roundtrip():
    segs = [{"kind": "clip", "label": "a", "span": [0.0, 2.0]},
            {"kind": "card", "label": "b", "len": 1.0}]
    art = get("opentimelineio").run({"op": "export", "segments": segs,
                                     "dst": str(TMP / "tl.otio"), "fps": 30})
    back = get("opentimelineio").run({"op": "read",
                                      "src": str(TMP / "tl.otio")})
    assert art["clips"] == 2 and len(back["clips"]) == 2


def test_svg_adapter():
    art = get("svgwrite").run({"kind": "stat_card", "title": "87%",
                               "body": "faster", "dst": str(TMP / "card.svg")})
    text = Path(TMP / "card.svg").read_text(encoding="utf-8")
    assert "<svg" in text and "87%" in text


def test_rembg_no_download():
    import os
    os.environ.setdefault("U2NET_HOME", r"F:\Arsenal\07_AI_Models\rembg")
    src = r"C:\Users\NOURSO~1\AppData\Local\Temp\opencode\qc_8.jpg"
    art = get("rembg").run({"src": src, "dst": str(TMP / "cut.png"),
                            "model": "u2net"})
    assert Path(TMP / "cut.png").is_file()


def test_colour_adapter():
    a = r"C:\Users\NOURSO~1\AppData\Local\Temp\opencode\qc_8.jpg"
    art = get("colour-science").run({"ref": a, "src": a,
                                     "out": str(TMP / "cm.json")})
    assert art["suggested_eq"]["brightness"] == 0.0


def test_pydub_adapter():
    src = (r"C:\Users\NOUR SOFT\Documents\Default Project\tools\tts\piper"
           r"\tests\narr\L2_06.wav")
    art = get("pydub").run({"op": "slice", "src": src, "start_ms": 0,
                            "end_ms": 2000, "dst": str(TMP / "sl.wav")})
    assert art["ms"] == 2000


def test_jsonschema_adapter():
    art = get("jsonschema").run({
        "document": {"capability": "CUT", "duration": 4.0},
        "schema": {"type": "object",
                   "required": ["capability", "duration"],
                   "properties": {"capability": {"type": "string"},
                                  "duration": {"type": "number"}}},
        "dst": "inline"})
    assert art["valid"] is True


def test_moviepy_gate_honest():
    import pytest as _p
    with _p.raises(ToolUnavailable):
        get("moviepy").run({"op": "probe", "src": "x"})
