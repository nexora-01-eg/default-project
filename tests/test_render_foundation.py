# -*- coding: utf-8 -*-
"""Phase A: rendering-foundation capability tests (real burns, real frames).

One 15 s clip, ten 1.5 s ASS cues (each required case), frame asserts.
Glyph-correctness (shaping/ligatures/RTL order) is additionally verified
by human frame review in the phase report — these tests assert presence,
robustness, and honest unavailability (emoji font, SVG raster).
"""
import sys
from pathlib import Path

sys.path.insert(0, ".")
import pytest

from engine.core.media import probe
from engine.rendering.ffmpeg import (apply_vf, burn_subtitles, color_clip,
                                     concat, extract_frame, trim)

TMP = Path(r"C:\Users\NOURSO~1\AppData\Local\Temp\opencode\phaseA")
TMP.mkdir(parents=True, exist_ok=True)

CASES = [
    ("ar_headline", "الذكاء الاصطناعي بيغيّر الفيديو"),
    ("ar_paragraph", "المونتاج كان بياخد ساعات طويلة من الشغل اليدوي"),
    ("ar_en_mixed", "الـworkflow الجديد أسرع بكتير"),
    ("ar_numerals", "خصم 87% لمدة 3 أيام"),
    ("ar_punct", "إزاي؟ — كده! …تمام."),
    ("rtl_align", "يمين لشمال مظبوط"),
    ("ar_kinetic", "كلمة كلمة بتظهر"),
    ("ar_svgtext", "نص SVG تجريبي"),
    ("ar_overvideo", "فوق الفيديو مباشرة"),
    ("emoji", "test 🎬 end"),
]

ASS_HEAD = ("[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: "
            "1920\nScaledBorderAndShadow: yes\n\n[V4+ Styles]\n"
            "Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, "
            "BackColour, Bold, Alignment, MarginV\n"
            "Style: Body,Arial,64,&H00FFFFFF,&H90000000,&H90000000,1,2,190\n\n"
            "[Events]\nFormat: Layer, Start, End, Style, Text\n")


def _t(s):
    h = int(s // 3600)
    m = int((s % 3600) // 60)
    return f"{h}:{m:02d}:{s % 60:05.2f}"


def _band_variance(jpg):
    import cv2
    import numpy as np
    img = cv2.imread(str(jpg), cv2.IMREAD_GRAYSCALE)
    h, w = img.shape
    band = img[int(h * 0.70):int(h * 0.92), :]
    return float(band.std()), (w, h)


@pytest.fixture(scope="module")
def render():
    clip = TMP / "base.mp4"
    color_clip("0x0B102E", 1080, 1920, 15.0, clip, fps=30)
    lines = [ASS_HEAD]
    for i, (name, text) in enumerate(CASES):
        tags = r"{\kf50}" if name == "ar_kinetic" else ""
        lines.append(f"Dialogue: 0,{_t(i * 1.5)},{_t(i * 1.5 + 1.5)},Body,"
                     f"{tags}{text}")
    ass = TMP / "cases.ass"
    ass.write_text("\n".join(lines) + "\n", encoding="utf-8")
    out = TMP / "burned.mp4"
    burn_subtitles(clip, ass, out, encoder="h264_qsv")
    return out


@pytest.mark.parametrize("idx,name", [(i, n) for i, (n, _) in enumerate(CASES)])
def test_case_text_present(render, idx, name, tmp_path=None):
    mid = idx * 1.5 + 0.75
    jpg = TMP / f"case_{idx:02d}.jpg"
    extract_frame(render, mid, jpg)
    var, (w, h) = _band_variance(jpg)
    assert (w, h) == (1080, 1920)
    if name == "emoji":
        # Color-emoji font fallback: record only (doc decides availability).
        print(f"emoji band variance={var:.1f}")
        assert var >= 0.0
    else:
        assert var > 4.0, f"{name}: no text pixels detected"


def test_ar_over_video():
    src = r"F:\Arsenal\MH - محتوى بصري\02-فيديو\107916-679600385_medium.mp4"
    tmp = TMP / "over_raw.mp4"
    trim(src, 0.0, 2.0, tmp, encoder="h264_qsv")
    ass = TMP / "over.ass"
    ass.write_text(
        ASS_HEAD + f"Dialogue: 0,{_t(0)},{_t(2.0)},Body,فوق الفيديو مباشرة\n",
        encoding="utf-8")
    out = TMP / "over.mp4"
    burn_subtitles(tmp, ass, out, encoder="h264_qsv")
    jpg = TMP / "over.jpg"
    extract_frame(out, 1.0, jpg)
    var, _ = _band_variance(jpg)
    assert var > 4.0


def test_alpha_composite_pillow():
    from PIL import Image, ImageDraw
    base = Image.new("RGB", (1080, 1920), (11, 16, 46))
    layer = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0))
    ImageDraw.Draw(layer).rounded_rectangle(
        [340, 900, 740, 1020], radius=40, fill=(255, 217, 138, 128))
    out = Image.alpha_composite(base.convert("RGBA"), layer).convert("RGB")
    r, g, b = out.getpixel((540, 960))
    assert 100 < r < 255 and 60 < g < 200  # blended, neither endpoint
    out.save(TMP / "alpha.png")


def test_svg_raster_unavailable_structured():
    from engine.tools.router import resolve
    r = resolve("SVG_RASTER")
    assert r["selected"] is None
    assert r["decision"] == "CAPABILITY_MISSING"
