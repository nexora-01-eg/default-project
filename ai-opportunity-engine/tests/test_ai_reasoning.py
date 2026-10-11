import os
import tempfile

from oppengine import ai_reasoning as AIR
from oppengine import db as DB
from tests.fixtures import AR_LOGO, AR_VIDEO_SUBS, EN_PLUMBER

DEAD_CFG = {"lmstudio_base": "http://127.0.0.1:9", "chat_model": "x", "ai_timeout_s": 3}


def test_rules_fallback_offline():
    res = AIR.analyze(AR_VIDEO_SUBS, "ar", DEAD_CFG)
    assert res["provider"] == "rules"
    assert res["ai_relevance"] in ("high", "medium")
    assert res["ai_feasibility"] in AIR.FEASIBILITY_STATES
    assert 0.0 <= res["confidence"] <= 1.0
    assert res.get("ai_failure") is True


def test_non_ai_skips_llm_honestly():
    res = AIR.analyze(EN_PLUMBER, "en", DEAD_CFG)
    assert res["ai_relevance"] in ("none", "low")
    assert "provider" in res and "reasoning" in res


def test_logo_keeps_low_relevance():
    res = AIR.analyze(AR_LOGO, "ar", DEAD_CFG)
    assert res["ai_relevance"] in ("low", "none", "medium")
    assert res["ai_feasibility"] in AIR.FEASIBILITY_STATES


def test_all_feasibility_states_valid():
    assert len(AIR.FEASIBILITY_STATES) == 9
    assert "not_ai" in AIR.FEASIBILITY_STATES and "insufficient_info" in AIR.FEASIBILITY_STATES
