"""Extra adapters: mediapipe (pinned model DL), rapidocr, pycaption, ocio."""
import sys
from pathlib import Path

sys.path.insert(0, ".")
import pytest

from engine.tools.adapters import providers  # noqa: F401 (base 14)
from engine.tools.adapters import providers_extra  # noqa: F401 (adds 4)
from engine.tools.adapters.providers import get

TMP = Path(r"C:\Users\NOURSO~1\AppData\Local\Temp\opencode\tooltest")
TMP.mkdir(parents=True, exist_ok=True)
FACE_MODEL_URL = ("https://storage.googleapis.com/mediapipe-models/"
                  "face_landmarker/face_landmarker/float16/1/"
                  "face_landmarker.task")


def test_mediapipe_face_pipeline():
    import urllib.request
    model = TMP / "face_landmarker.task"
    if not model.is_file():
        urllib.request.urlretrieve(FACE_MODEL_URL, str(model))
    src = r"C:\Users\NOURSO~1\AppData\Local\Temp\opencode\qc_8.jpg"
    art = get("mediapipe").run({"src": src, "model": str(model)})
    assert art["count"] >= 0 and art["provider"] == "mediapipe"


def test_rapidocr_synthetic():
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (640, 200), "white")
    ImageDraw.Draw(img).text((60, 60), "AI 87%", fill="black")
    src = TMP / "ocr.png"
    img.save(src)
    art = get("rapidocr").run({"src": str(src)})
    assert art["boxes"] >= 1
    assert any("AI" in t or "87" in t for t in art["texts"])


def test_pycaption_convert():
    srt = ("1\n00:00:00,000 --> 00:00:02,000\n"
           "Hello world\n")
    art = get("pycaption").run({"srt_text": srt,
                                "dst": str(TMP / "caps.vtt")})
    text = Path(TMP / "caps.vtt").read_text(encoding="utf-8")
    assert "WEBVTT" in text and art["cues"] == 1


def test_ocio_exposure():
    art = get("opencolorio").run(
        {"pixels": [[[0.25, 0.25, 0.25]]], "exposure_mult": 2.0})
    assert abs(art["mean_out"] - 2 * art["mean_in"]) < 1e-3
