"""Phase 11 guarantees: shadow never changes results, never breaks pipelines."""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import shadow_benchmark as SH
from decision_engine.adapters.news import NewsGate
from decision_engine.adapters.opportunity import OpportunityGate
from decision_engine.adapters.orchestrator import LocalDecisionEngineAdapter
from decision_engine.engine import LocalDecisionEngine

ROOT = os.path.join(os.path.dirname(__file__), "..")


def test_disabled_adapters_change_nothing():
    assert LocalDecisionEngineAdapter().route_hint("x")["status"] == "disabled"
    assert OpportunityGate().prefilter_item("x")["verdict"] == "review"
    assert NewsGate().triage("x")["verdict"] == "maybe"


def test_low_confidence_is_review_required():
    rec = {"stream": "opportunity", "error": "",
           "answers": {"opp": {"type": "choice", "choice": "real",
                               "confidence": 0.45,
                               "probabilities": {"real": 0.5, "maybe": 0.3, "spam": 0.2}}}}
    v, conf, _ = SH.verdict_for(rec, 0.6)
    assert v == "review" and conf == 0.45


def test_failures_become_review_and_pipeline_continues():
    rec = {"stream": "news", "error": "backend_error:boom", "answers": {}}
    assert SH.verdict_for(rec, 0.6)[0] == "review"

    class Dead(LocalDecisionEngine):
        def system_one(self, *a, **k):
            raise RuntimeError("down")

    r = SH.run_shadow(Dead(), "opportunity", "ref", "filter", "text",
                      {"q": {"type": "noul", "instructions": "x"}}, {})
    assert r["error"].startswith("backend_error") and r["answers"] == {}


def test_verdict_never_mutates_input():
    eng = LocalDecisionEngine()
    q = {"opp": {"type": "choice", "instructions": "Is this real?",
                 "criteria": {"real": "paying client", "spam": "junk"}}}
    before = json.dumps(q, sort_keys=True)
    eng.decide("Need a website, budget $2000", q)
    assert json.dumps(q, sort_keys=True) == before


def test_no_network_calls():
    import socket
    real = socket.socket

    def blocked(*a, **k):
        raise AssertionError("network call attempted")

    socket.socket = blocked
    try:
        eng = LocalDecisionEngine()
        eng.decide("Need a website, budget $2000",
                   {"q": {"type": "noul", "instructions": "service opportunity"}})
        SH.run_shadow(eng, "news", "r", "t", "some text",
                      {"q": {"type": "noul", "instructions": "x"}}, {})
    finally:
        socket.socket = real


def test_no_secrets_in_shadow_log():
    assert "sk-test-SECRET123" not in SH.redact("key sk-test-SECRET123 here")
    assert "[REDACTED]" in SH.redact("Authorization: Bearer abc123")
    log = os.path.join(ROOT, "logs", "shadow_run_20260923_052907.jsonl")
    if os.path.exists(log):
        blob = open(log, encoding="utf-8").read().lower()
        for bad in ("sk-", "bearer ", "password:", "api_key"):
            assert bad not in blob, bad
        for line in blob.splitlines():
            rec = json.loads(line)
            assert len(rec.get("text_redacted", "")) <= 200


def test_localhost_only():
    from decision_engine.server import run
    try:
        run(host="0.0.0.0", port=18799)
        raise AssertionError("non-loopback bind accepted")
    except ValueError:
        pass


def test_deterministic_behavior():
    eng = LocalDecisionEngine()
    q = {"a": {"type": "choice", "instructions": "Route it?",
               "criteria": {"x": "code work", "y": "research work"}}}
    texts = ["Fix the typo and commit.", "What launched this week?",
             "مطلوب متجر إلكتروني بميزانية واضحة"]
    first = [eng.decide(t, q) for t in texts]
    second = [eng.decide(t, q) for t in texts]
    assert first == second


def test_harness_is_read_only():
    src = open(os.path.join(ROOT, "scripts", "shadow_benchmark.py"),
               encoding="utf-8").read()
    assert "mode=ro" in src
    for kw in ("INSERT ", "UPDATE ", "DELETE ", "DROP TABLE"):
        assert kw not in src.upper().replace("MODE=RO", "")
