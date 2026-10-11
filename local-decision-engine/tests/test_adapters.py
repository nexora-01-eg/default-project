import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from decision_engine.adapters.news import NewsGate
from decision_engine.adapters.opportunity import OpportunityGate
from decision_engine.adapters.orchestrator import LocalDecisionEngineAdapter


def test_orchestrator_adapter_disabled_by_default():
    a = LocalDecisionEngineAdapter()
    assert a.route_hint("anything")["status"] == "disabled"


def test_orchestrator_route_hint_enabled():
    a = LocalDecisionEngineAdapter(enabled=True)
    r = a.route_hint("Fix the typo in README and commit with a clean git message.")
    assert r["status"] == "ok" and r["hint"]["agent"] == "Aider"


def test_needs_llm_gate():
    a = LocalDecisionEngineAdapter(enabled=True)
    r = a.needs_large_llm("Which category does this ticket belong to?")
    assert r["answers"]["gate"]["choice"] == "local"


def test_opportunity_gate_never_drops_on_low_confidence():
    g = OpportunityGate(enabled=True)
    r = g.prefilter_item("Some vague message with no clear intent whatsoever xyz")
    assert r["verdict"] in ("keep", "review")  # never silent-drop unsure items


def test_opportunity_gate_drops_clear_spam():
    g = OpportunityGate(enabled=True)
    r = g.prefilter_item("CONGRATULATIONS you won $5000 click here to claim")
    assert r["verdict"] in ("drop", "review")


def test_news_gate_batch_reduction():
    g = NewsGate(enabled=True)
    r = g.filter_batch(["New transformer paper cuts inference cost by 40%.",
                        "Weather forecast: sunny weekend."])
    assert r["drop"] == [1] and r["keep"] == [0]
