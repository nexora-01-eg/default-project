"""Phase 14 Arabic tests — ar-only, en-only, mixed, punctuation, fonts.

No Arabic TTS voice exists on this box, so transcripts below are
hand-written (labeled synthetic text). They exercise segmentation,
wrapping integrity, RTL handling, and real glyph rendering — NOT Whisper
Arabic STT, which stays explicitly unverified (see docs/CAPTIONS.md).
"""
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

from engine.subtitles.captions import (
    build_cues,
    flatten_words,
    has_rtl,
    map_cues_to_output,
    resolve_caption_config,
    validate_cues,
    wrap_lines,
)
from engine.subtitles.fonts import (
    discover_fonts,
    resolve_font,
    validate_font_for_text,
)
from engine.subtitles.formats import write_ass, write_srt, write_vtt

AR = [("مرحبا", 0.0, 0.5, 0.9), ("بالعالم.", 0.5, 1.1, 0.9),
      ("كيف", 1.4, 1.7, 0.9), ("حالك؟", 1.7, 2.2, 0.9)]
EN = [("Hello", 0.0, 0.5, 0.9), ("world.", 0.5, 1.0, 0.9)]
MIXED = [("أهلا", 0.0, 0.4, 0.9), ("بك", 0.4, 0.7, 0.9),
         ("في", 0.7, 0.9, 0.9), ("Windows", 0.9, 1.4, 0.9),
         ("الجديد", 1.6, 2.1, 0.9)]


def _tr(words, lang="ar", duration=10.0):
    return {"language": lang, "duration": duration,
            "segments": [{"id": 0, "text": " ".join(w[0] for w in words),
                          "start": 0.0, "end": duration,
                          "words": [{"word": w, "start": s, "end": e,
                                     "probability": p}
                                    for w, s, e, p in words]}],
            "fillers": [], "skipped_reason": ""}


def _cfg(**over):
    base = resolve_caption_config(None)
    base.update(over)
    return base


def test_rtl_detection():
    assert has_rtl("مرحبا بالعالم") is True
    assert has_rtl("Hello world") is False
    assert has_rtl("Windows 11 الجديد") is True  # mixed counts as RTL-bearing
    assert has_rtl("12345") is False


def test_arabic_only_segmentation():
    cues, _ = build_cues(_tr(AR), [], _cfg())
    assert [(c.text, c.start, c.end) for c in cues] == [
        ("مرحبا بالعالم.", 0.0, 1.1), ("كيف حالك؟", 1.4, 2.2)]  # sentence split kept


def test_english_only_segmentation():
    cues, _ = build_cues(_tr(EN, lang="en"), [], _cfg())
    assert cues[0].text == "Hello world."


def test_mixed_arabic_english_integrity():
    tr = _tr(MIXED)
    cues, _ = build_cues(tr, [], _cfg())
    assert len(cues) == 1
    cue = cues[0]
    # Logical order preserved: first token first, Latin run intact.
    assert cue.text.startswith("أهلا") and "Windows" in cue.text
    assert cue.text == "أهلا بك في Windows الجديد"
    for line in cue.lines:
        assert line == line.strip()  # no split inside words, incl. Latin run
    assert validate_cues(cues) == []


def test_arabic_punctuation_and_numerals():
    words = [("العدد", 0.0, 0.4, 0.9), ("123", 0.4, 0.8, 0.9),
             ("صحيح؟", 0.8, 1.3, 0.9), ("نعم.", 1.5, 1.9, 0.9)]
    cues, _ = build_cues(_tr(words), [], _cfg())
    assert cues[0].text == "العدد 123 صحيح؟"
    assert cues[1].text == "نعم."


def test_two_line_arabic_wrap():
    tokens = "هذا مثال على ترجمة احترافية طويلة".split()
    lines = wrap_lines(tokens, 20, 2)
    assert lines is not None and len(lines) == 2
    assert all(len(line) <= 20 for line in lines)
    assert " ".join(lines) == "هذا مثال على ترجمة احترافية طويلة"


def test_arabic_srt_vtt_roundtrip_text():
    cues, _ = build_cues(_tr(AR), [], _cfg())
    payload = [{"cue_id": c.cue_id, "start": c.start, "end": c.end,
                "text": c.text, "lines": c.lines} for c in cues]
    srt = write_srt(payload)
    vtt = write_vtt(payload, "ar")
    assert "مرحبا بالعالم." in srt and "كيف حالك؟" in srt
    assert "مرحبا بالعالم." in vtt
    # Logical (not visual) order in sidecars: first word first in bytes.
    assert srt.index("مرحبا") < srt.index("بالعالم")


def test_arabic_ass_contains_glyphs_and_style():
    from engine.subtitles.formats import resolve_style
    cues, _ = build_cues(_tr(AR), [], _cfg())
    payload = [{"cue_id": c.cue_id, "start": c.start, "end": c.end,
                "text": c.text, "lines": c.lines} for c in cues]
    ass = write_ass(payload, resolve_style("default"), "Arial", 640, 360)
    assert "مرحبا بالعالم." in ass and "PlayResX: 640" in ass
    assert "Fontname" in ass


def test_font_discovery_lists_windows_fonts():
    fonts = discover_fonts()
    names = [f["file"].lower() for f in fonts]
    assert any("arial.ttf" in n for n in names)
    assert all(f["file"] for f in fonts)


def test_font_validation_tiers():
    import shutil
    assert validate_font_for_text("C:/nope/missing.ttf", "hi")["status"] == "invalid"
    arial = next(f["file"] for f in discover_fonts() if f["file"].lower().endswith("arial.ttf"))
    assert validate_font_for_text(arial, "Hello")["status"] == "valid"
    ar_check = validate_font_for_text(arial, "مرحبا")
    assert ar_check["status"] in ("valid", "uncertain")
    assert ar_check["arabic_known"] is True  # Arial ships Arabic
    other = next((f["file"] for f in discover_fonts()
                  if f["file"].lower().endswith("segoeuiz.ttf")), None)
    if other:
        assert validate_font_for_text(other, "مرحبا")["status"] in ("valid", "uncertain")
    with pytest.raises(Exception, match="not found"):
        from engine.subtitles.fonts import resolve_font
        resolve_font("No Such Family XYZ")
    assert resolve_font("Arial")["file"].lower().endswith("arial.ttf")


def test_missing_font_failure_in_approval():
    from engine.subtitles.captions import approve_captions
    from engine.core.project_store import create_project, write_artifact
    p = create_project(str(ROOT / "tests" / "fixtures" / "tone_5s.mp4"))
    write_artifact(p.id, "captions", "caption_plan.json",
                   {"schema_version": "caption-plan-1.0", "source": "t",
                    "transcript_hash": "h", "cues": [], "cue_count": 0,
                    "style": "default", "language": "en", "warnings": [],
                    "expected_duration": 0.0, "config": {}})
    with pytest.raises(Exception, match="not found"):
        approve_captions(p.id, font_file="C:/nope/missing.ttf")
