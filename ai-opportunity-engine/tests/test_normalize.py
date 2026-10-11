from oppengine import normalize as NZ
from tests.fixtures import (AR_LOGO, AR_SHORTS, AR_TRIM, AR_VIDEO_SUBS,
                            EN_PLUMBER, EN_TRANSCRIBE, SHORT_NOISE)


def test_detect_arabic():
    assert NZ.detect_language(AR_VIDEO_SUBS) == "ar"
    assert NZ.detect_language("محتاج مصمم لوجو") == "ar"


def test_detect_english():
    assert NZ.detect_language(EN_TRANSCRIBE) == "en"


def test_detect_unknown():
    assert NZ.detect_language("") == "unknown"
    assert NZ.detect_language("123 !!!") == "unknown"


def test_normalize_strips_urls_and_controls():
    t = NZ.normalize_text("see https://example.com/x  hello\x00world   كده")
    assert "http" not in t and "\x00" not in t and "hello" in t


def test_normalize_strips_html():
    t = NZ.normalize_text("hello <a href=\"https://x.y/z\">world</a> &amp; friends")
    assert "<a" not in t and "world" in t and "&amp;" not in t


def test_explicit_ai_arabic():
    rtype, rel, conf, _ = NZ.classify_request(AR_SHORTS)
    assert rtype == "explicit_ai" and rel == "high"


def test_implicit_ai_video_subs():
    rtype, rel, conf, _ = NZ.classify_request(AR_VIDEO_SUBS)
    assert rtype == "implicit_ai" and rel in ("high", "medium")


def test_logo_is_not_forced_ai():
    rtype, rel, conf, _ = NZ.classify_request(AR_LOGO)
    assert rel in ("low", "none")  # human service; must NOT be forced into AI


def test_plumber_not_ai():
    rtype, rel, conf, _ = NZ.classify_request(EN_PLUMBER)
    assert rel in ("none", "low")


def test_short_is_unclear():
    rtype, rel, conf, _ = NZ.classify_request(SHORT_NOISE)
    assert rtype == "unclear"


def test_urgency():
    f = NZ.extract_fields("عاجل محتاج سباك دلوقتي", "ar")
    assert f["urgency"] == "high"
    f2 = NZ.extract_fields(EN_TRANSCRIBE, "en")
    assert f2["urgency"] in ("low", "medium")
