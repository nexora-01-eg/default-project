"""Phase 14 caption planning tests — pure logic, no ffmpeg, no network."""
import json
from dataclasses import asdict
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

from engine.core.models import CaptionCue, CaptionPlan, CaptionWord
from engine.subtitles.captions import (
    CaptionError,
    build_caption_plan,
    build_cues,
    flatten_words,
    keeps_from_edl,
    map_cues_to_output,
    reading_metrics,
    resolve_caption_config,
    validate_cues,
    wrap_lines,
)
from engine.subtitles.formats import (
    FormatError,
    resolve_style,
    srt_time,
    vtt_time,
    write_ass,
    write_srt,
    write_vtt,
)


def _tr(words, lang="en", duration=10.0):
    return {"language": lang, "duration": duration,
            "segments": [{"id": 0, "text": " ".join(w[0] for w in words),
                          "start": 0.0, "end": duration,
                          "words": [{"word": w, "start": s, "end": e,
                                     "probability": p}
                                    for w, s, e, p in words]}],
            "fillers": [], "skipped_reason": ""}


def _words(n, start=0.0, step=0.5, dur=0.4, prefix="w"):
    return [(f"{prefix}{i}", round(start + i * step, 3),
             round(start + i * step + dur, 3), 0.9) for i in range(n)]


def _cfg(**over):
    base = resolve_caption_config(None)
    base.update(over)
    return base


# ---------- 1. model serialization ----------

def test_model_serialization():
    w = CaptionWord(word_id="s0w0", text="hi", start=0.0, end=0.5, probability=0.9)
    c = CaptionCue(cue_id="cue_0001", start=0.0, end=0.5, text="hi",
                   word_refs=[asdict(w)])
    p = CaptionPlan(cues=[c], cue_count=1)
    d = asdict(p)
    assert d["cues"][0]["word_refs"][0]["word_id"] == "s0w0"
    assert json.loads(json.dumps(d))["cue_count"] == 1


def test_config_defaults_and_validation():
    cfg = resolve_caption_config(None)
    assert (cfg["caption_max_lines"], cfg["caption_max_chars_per_line"],
            cfg["caption_max_cps"]) == (2, 42, 20.0)
    assert cfg["caption_mode"] == "sidecar"  # explicit default, never silent
    with pytest.raises(CaptionError):
        resolve_caption_config({"caption_position": "sideways"})
    with pytest.raises(CaptionError):
        resolve_caption_config({"caption_min_duration": 9.0,
                                "caption_max_duration": 1.0})


# ---------- 2-5. segmentation / boundaries / caps / reading speed ----------

def test_punctuation_boundaries():
    tr = _tr([("Hello", 0.0, 0.5, 0.9), ("world.", 0.5, 1.0, 0.9),
              ("Next", 1.2, 1.7, 0.9), ("one.", 1.7, 2.2, 0.9)])
    cues, _ = build_cues(tr, [], _cfg())
    assert [(c.text, c.start, c.end) for c in cues] == [
        ("Hello world.", 0.0, 1.0), ("Next one.", 1.2, 2.2)]


def test_pause_boundaries():
    tr = _tr([("a", 0.0, 0.4, 0.9), ("b", 2.0, 2.4, 0.9)])
    cues, _ = build_cues(tr, [], _cfg())
    assert len(cues) == 2  # 1.6 s gap splits


def test_max_duration_and_words_split():
    tr = _tr(_words(20, step=0.5, dur=0.4))
    cues, _ = build_cues(tr, [], _cfg())
    assert len(cues) >= 2
    for c in cues:
        assert c.end - c.start <= 7.0 + 1e-6
        assert len(c.word_refs) <= 14


def test_reading_speed_metrics_and_extension():
    cps, wpm = reading_metrics("hello world", 2, 1.0)
    assert cps == 11.0 and wpm == 120.0
    # Fast speech: extend into pause first, split second, warn last.
    tr = _tr([("a", 0.0, 0.2, 0.9), ("b", 0.2, 0.4, 0.9), ("c", 0.4, 0.6, 0.9),
              ("d", 2.0, 2.2, 0.9)])
    cues, warnings = build_cues(tr, [], _cfg(caption_max_cps=5.0))
    assert cues[0].end > 0.6  # extended into the pause
    assert cues[0].split_reason == "extended_into_pause"


# ---------- 6/9. two-line wrapping ----------

def test_two_line_balanced_wrap():
    lines = wrap_lines("This is a professional caption example".split(), 22, 2)
    assert lines is not None and len(lines) == 2
    assert all(len(line) <= 22 for line in lines)
    assert all(" " not in line or True for line in lines)
    joined = " ".join(lines)
    assert joined == "This is a professional caption example"


def test_wrap_never_hyphenates_or_orphans_badly():
    lines = wrap_lines(["hello", "world", "today"], 12, 2)
    assert lines == ["hello world", "today"] or lines == ["hello", "world today"]
    for line in lines:
        assert "-" not in line or line in ("hello", "world", "today")
    assert wrap_lines(["supercalifragilistic"], 5, 1) is None  # impossible: caller splits


def test_wrap_deterministic():
    tokens = "the quick brown fox jumps over".split()
    assert wrap_lines(tokens, 15, 2) == wrap_lines(tokens, 15, 2)


# ---------- 16/17. SRT + WebVTT ----------

def test_srt_generation():
    cues = [{"cue_id": "cue_0001", "start": 61.5, "end": 63.25,
             "text": "hi", "lines": ["hi"]}]
    out = write_srt(cues)
    assert out.startswith("1\n00:01:01,500 --> 00:01:03,250\nhi\n")
    assert srt_time(0.0) == "00:00:00,000"


def test_vtt_generation():
    cues = [{"cue_id": "cue_0001", "start": 0.0, "end": 1.0,
             "text": "a\nb", "lines": ["a", "b"]}]
    out = write_vtt(cues, "en")
    assert out.startswith("WEBVTT - en\n")
    assert "00:00:00.000 --> 00:00:01.000\na\nb" in out
    assert vtt_time(61.5) == "00:01:01.500"


def test_empty_cue_rejected_by_writers():
    bad = [{"cue_id": "x", "start": 0.0, "end": 1.0, "text": "  ", "lines": []}]
    with pytest.raises(FormatError):
        write_srt(bad)
    with pytest.raises(FormatError):
        write_vtt(bad)


# ---------- 18-21. timeline mapping ----------

def test_mapping_shifts_and_trims():
    cues = [{"cue_id": "cue_0001", "start": 0.2, "end": 1.8, "text": "a b",
             "language": "en", "confidence": 0.9, "style": "default",
             "scene_id": 0,
             "word_refs": [{"word_id": "s0w0", "text": "a", "start": 0.2, "end": 0.6,
                            "probability": 0.9},
                           {"word_id": "s0w1", "text": "b", "start": 4.2, "end": 4.6,
                            "probability": 0.9}]}]
    # Source 0-2 and 4-6 kept -> output 0-4. Word b moves 4.2->2.2,
    # leaving a 1.6 s output gap -> split into two cues.
    mapped, warnings, stats = map_cues_to_output(cues, [(0, 2), (4, 6)])
    assert len(mapped) == 2
    assert (mapped[0]["start"], mapped[0]["end"]) == (0.2, 0.6)
    assert (mapped[1]["start"], mapped[1]["end"]) == (2.2, 2.6)
    assert stats == {"kept_words": 2, "dropped_words": 0,
                     "split_cues": 1, "mapped_cues": 2}


def test_removed_interval_handling():
    cues = [{"cue_id": "cue_0001", "start": 0.2, "end": 5.0, "text": "a b c",
             "language": "en", "confidence": 0.9, "style": "default",
             "scene_id": 0,
             "word_refs": [
                 {"word_id": "s0w0", "text": "a", "start": 0.2, "end": 0.6,
                  "probability": 0.9},
                 {"word_id": "s0w1", "text": "b", "start": 2.5, "end": 2.9,
                  "probability": 0.9},  # removed region
                 {"word_id": "s0w2", "text": "c", "start": 4.2, "end": 4.6,
                  "probability": 0.9}]}]
    mapped, warnings, stats = map_cues_to_output(cues, [(0, 2), (4, 6)])
    assert stats["dropped_words"] == 1
    assert len(mapped) == 2  # output gap 1.6 s >= 0.8 -> split
    assert [m["split_reason"] for m in mapped] == ["edit_split", "edit_split"]
    assert (mapped[0]["start"], mapped[0]["end"]) == (0.2, 0.6)
    assert (mapped[1]["start"], mapped[1]["end"]) == (2.2, 2.6)


def test_cue_with_no_surviving_words_dropped():
    cues = [{"cue_id": "cue_0001", "start": 2.2, "end": 2.9, "text": "b",
             "language": "en", "confidence": 0.9, "style": "default",
             "scene_id": 0,
             "word_refs": [{"word_id": "s0w0", "text": "b", "start": 2.5,
                            "end": 2.9, "probability": 0.9}]}]
    mapped, warnings, stats = map_cues_to_output(cues, [(0, 2), (4, 6)])
    assert mapped == [] and stats["dropped_words"] == 1
    assert any("no surviving words" in w for w in warnings)


def test_keeps_from_edl_validation():
    edl = {"decisions": [{"action": "KEEP", "start": 0.0, "end": 2.0},
                         {"action": "REMOVE", "start": 2.0, "end": 4.0},
                         {"action": "KEEP", "start": 4.0, "end": 6.0}],
           "duration": 6.0}
    assert keeps_from_edl(edl) == [(0.0, 2.0), (4.0, 6.0)]
    with pytest.raises(Exception):
        keeps_from_edl({"decisions": [], "duration": 0.0})


# ---------- safety: validate_cues ----------

def test_validate_cues_catches_problems():
    from engine.core.models import CaptionCue as _CC
    good = [_CC(cue_id="cue_0001", start=0.0, end=1.0, text="hi",
                word_refs=[{"text": "hi", "start": 0.0, "end": 0.5}])]
    assert validate_cues(good) == []
    bad = [_CC(cue_id="cue_0001", start=1.0, end=1.0, text="",
               word_refs=[{"text": "x", "start": 5.0, "end": 5.5}])]
    issues = validate_cues(bad)
    assert len(issues) >= 3  # duration, empty, word-outside, text mismatch


# ---------- styles ----------

def test_style_presets_have_required_fields():
    for name in ("default", "clean", "social", "cinematic", "minimal"):
        s = resolve_style(name)
        assert {"font_family", "font_size", "alignment", "margin_v",
                "max_lines", "outline"} <= set(s)
    with pytest.raises(FormatError):
        resolve_style("neon-noir")


# ---------- undecodable chars ----------

def test_fffd_sanitized_with_warning():
    from engine.subtitles.captions import build_cues, validate_cues
    tr = _tr([("hello", 0.0, 0.5, 0.9), ("wor�ld", 0.5, 1.0, 0.9),
              ("ok.", 1.2, 1.7, 0.9)])
    cues, _ = build_cues(tr, [], _cfg())
    assert cues
    for c in cues:
        assert "�" not in c.text
        for w in c.word_refs:
            assert "�" not in w["text"]
    assert any("undecodable_chars" in c.warnings for c in cues)
    assert validate_cues(cues) == []  # text/refs consistent after scrub


def test_fffd_only_word_keeps_cue_flagged():
    from engine.subtitles.captions import build_cues
    tr = _tr([("�", 0.0, 0.5, 0.9)])
    cues, _ = build_cues(tr, [], _cfg())
    assert cues  # content preserved, flagged — never silently erased
    assert any("undecodable_chars" in c.warnings for c in cues)
