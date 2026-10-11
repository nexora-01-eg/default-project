"""Phase 2 tests: revenue intent (AR/EG/Arabizi/EN, non-commercial, provenance)."""
from oppengine import revenue as REV
from tests.fixtures import AR_LOGO, AR_VIDEO_SUBS, EN_PLUMBER


def test_arabic_hiring_high():
    r = REV.classify_revenue("محتاج حد يعمللي برنامج مخزن لشركتي الصغيرة")
    assert r["level"] == "high"  # hiring + business
    assert r["hiring_language"] and r["business_context"]
    assert r["evidence"] and all(e["provenance"] == "OBSERVED" for e in r["evidence"])


def test_egyptian_tool_want():
    r = REV.classify_revenue("عاوز أتمتة للشغل ده")
    assert r["level"] in ("medium", "low")
    assert r["evidence"]


def test_arabic_examples_from_spec():
    assert REV.classify_revenue("محتاج أداة تحول الفيديو لنص")["level"] in ("medium", "low")
    assert REV.classify_revenue("بدور على حد يربط المتجر بالواتساب")["level"] in ("high", "medium")
    assert REV.classify_revenue("عايز حد يعمللي بوت للرد على العملاء")["level"] == "high"
    assert REV.classify_revenue("فيه برنامج يعمل التصميم تلقائي؟")["level"] in ("medium", "low")


def test_arabizi():
    r = REV.classify_revenue("3ayez 7ad ye3melly bot lel store beta3y")
    assert r["level"] in ("high", "medium")
    assert REV.classify_revenue("fih program ye7awel el sot le text؟")["evidence"]


def test_english_payment_high():
    r = REV.classify_revenue("I'm willing to pay $200 for someone to automate our invoicing, we do it manually")
    assert r["level"] == "high"
    assert r["payment_language"] and r["business_context"]


def test_english_hiring():
    r = REV.classify_revenue("Looking for a developer to build a small internal tool")
    assert r["level"] in ("high", "medium")
    assert r["hiring_language"]


def test_non_commercial_news():
    r = REV.classify_revenue("Show HN: my new open-source benchmark tool, what do you think?")
    assert r["level"] in ("not_commercial", "unknown", "low")


def test_tutorial_not_commercial():
    r = REV.classify_revenue("Tutorial: how I built a RAG pipeline step by step")
    assert r["level"] in ("not_commercial", "unknown")


def test_plumber_and_logo_not_forced():
    assert REV.classify_revenue(EN_PLUMBER)["level"] in ("unknown", "low", "not_commercial")
    assert REV.classify_revenue(AR_LOGO)["level"] in ("unknown", "low", "medium", "not_commercial")


def test_unknown_empty_short():
    assert REV.classify_revenue("")["level"] == "unknown"
    assert REV.classify_revenue("ok")["level"] == "unknown"


def test_urgency_and_provenance():
    r = REV.classify_revenue("عاجل محتاج حد يخلص الشغل ده اليوم")
    assert r["urgency"] == "high"
    assert "OBSERVED" in r["provenance"] or "INFERRED" in r["provenance"]
    assert REV.level_score("high") > REV.level_score("medium") > REV.level_score("unknown")
    assert REV.level_score("not_commercial") == 0.0
