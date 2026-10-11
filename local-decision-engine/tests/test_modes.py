"""Phase 12: modes, kill switch, fail-open, logging, determinism."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest

from decision_engine.modes import (
    ALLOWED_LOG_KEYS,
    CURRENT_DEFAULT,
    DecisionMode,
    ModeGate,
    SafetyPolicy,
    kill_switch,
    resolve_mode,
)

Q = {"opp": {"type": "choice", "instructions": "Is this real?",
             "criteria": {"real": "paying client", "spam": "junk"}}}


def local_ok():
    from decision_engine.engine import LocalDecisionEngine
    eng = LocalDecisionEngine()
    ans = eng.decide("Need a website, budget $2000", Q)["opp"]
    return {"choice": ans["choice"]}, ans["confidence"]


def test_default_is_shadow_and_not_active():
    assert CURRENT_DEFAULT == DecisionMode.SHADOW
    assert resolve_mode() == DecisionMode.SHADOW


def test_disabled_never_calls_engine():
    called = []
    g = ModeGate()
    r = g.evaluate(DecisionMode.DISABLED, "ref1", lambda: "EXISTING",
                   lambda: (called.append(1), 0.99))
    assert r.existing_decision == "EXISTING" and called == []
    assert r.local_decision is None


def test_shadow_records_without_changing():
    g = ModeGate()
    r = g.evaluate(DecisionMode.SHADOW, "ref2", lambda: "EXISTING", local_ok,
                   lambda e, l: e == l.get("choice"))
    assert r.existing_decision == "EXISTING"
    assert r.local_decision == {"choice": "real"}
    assert r.action == "existing"
    assert r.log["mode"] == "shadow"


def test_canary_opt_in_sampling_and_no_change():
    g = ModeGate(policy=SafetyPolicy(canary_percent=100))
    r = g.evaluate(DecisionMode.CANARY, "ref3", lambda: "EXISTING", local_ok)
    assert r.existing_decision == "EXISTING" and r.local_decision is not None
    g0 = ModeGate(policy=SafetyPolicy(canary_percent=0))
    r0 = g0.evaluate(DecisionMode.CANARY, "ref3", lambda: "EXISTING", local_ok)
    assert r0.local_decision is None and r0.existing_decision == "EXISTING"


def test_canary_sampling_deterministic():
    g = ModeGate(policy=SafetyPolicy(canary_percent=10))
    ins = [g.evaluate(DecisionMode.CANARY, "same-ref", lambda: "E",
                      local_ok).local_decision is not None for _ in range(3)]
    assert ins[0] == ins[1] == ins[2]


def test_active_is_config_only_never_changes_existing():
    g = ModeGate()
    r = g.evaluate(DecisionMode.ACTIVE, "ref4", lambda: "EXISTING", local_ok)
    assert r.existing_decision == "EXISTING" and r.action == "existing"


def test_kill_switch(monkeypatch):
    monkeypatch.setenv("LOCAL_DECISION_ENGINE_ENABLED", "0")
    assert not kill_switch()
    assert resolve_mode(DecisionMode.CANARY) == DecisionMode.DISABLED
    g = ModeGate()
    called = []
    r = g.evaluate(DecisionMode.SHADOW, "ref5", lambda: "EXISTING",
                   lambda: (called.append(1), 1.0))
    assert called == [] and r.existing_decision == "EXISTING"
    monkeypatch.setenv("LOCAL_DECISION_ENGINE_ENABLED", "1")
    assert kill_switch()


def test_fail_open_unavailable_engine():
    g = ModeGate(engine=None)
    r = g.evaluate(DecisionMode.SHADOW, "ref6", lambda: "EXISTING", None)
    assert r.existing_decision == "EXISTING" and r.local_decision is None


def test_fail_open_malformed_internal_exception():
    g = ModeGate()
    r = g.evaluate(DecisionMode.SHADOW, "ref7", lambda: "EXISTING",
                   lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    assert r.existing_decision == "EXISTING" and r.local_decision is None
    r2 = g.evaluate(DecisionMode.SHADOW, "ref8",
                    lambda: (_ for _ in ()).throw(ValueError("db gone")),
                    local_ok)
    assert r2.local_decision is not None  # local still recorded
    assert r2.existing_decision == {"__existing_error__": "db gone"}


def test_fail_open_malformed_input_and_corrupted_response():
    from decision_engine.engine import LocalDecisionEngine
    eng = LocalDecisionEngine()
    g = ModeGate()
    r = g.evaluate(DecisionMode.SHADOW, "ref9", lambda: "KEEP",
                   lambda: (eng.decide("", {"q": {"type": "noul", "instructions": "x"}}), 0.0))
    assert r.existing_decision == "KEEP" and r.local_decision is None
    r2 = g.evaluate(DecisionMode.SHADOW, "ref10", lambda: "KEEP",
                    lambda: ({"garbage": object()}, 0.5),
                    lambda e, l: e == l)
    assert r2.existing_decision == "KEEP" and r2.agreement is False
    r3 = g.evaluate(DecisionMode.SHADOW, "ref10b", lambda: "KEEP",
                    lambda: ({"garbage": object()}, 0.5),
                    lambda e, l: (_ for _ in ()).throw(TypeError("uncomparable")))
    assert r3.agreement is None and r3.existing_decision == "KEEP"


def test_fail_open_timeout_style_slow_engine():
    import time as _t
    g = ModeGate(policy=SafetyPolicy(timeout_s=0.01))

    def slow():
        _t.sleep(0.05)
        return {"choice": "x"}, 0.9

    r = g.evaluate(DecisionMode.SHADOW, "ref11", lambda: "EXISTING", slow)
    assert r.existing_decision == "EXISTING"  # recorded even if slow
    assert r.latency_ms >= 40


def test_thresholds_configurable_not_hardcoded(monkeypatch):
    monkeypatch.setenv("HIGH_CONFIDENCE_THRESHOLD", "0.9")
    monkeypatch.setenv("LOW_CONFIDENCE_ACTION", "REVIEW_REQUIRED")
    p = SafetyPolicy.from_env()
    assert p.high_confidence_threshold == 0.9
    assert p.low_confidence_action == "REVIEW_REQUIRED"
    import inspect
    from decision_engine import modes as M
    src = inspect.getsource(M)
    assert "0.8" in src  # default value exists...
    assert "HIGH_CONFIDENCE_THRESHOLD" in src  # ...but comes from env


def test_log_schema_and_no_secrets():
    g = ModeGate()
    r = g.evaluate(DecisionMode.SHADOW, "ref12", lambda: "E", local_ok)
    assert set(r.log) <= ALLOWED_LOG_KEYS
    blob = str(r.log).lower()
    for bad in ("sk-", "bearer", "password", "token", "cookie", "secret"):
        assert bad not in blob
    assert set(ALLOWED_LOG_KEYS) == {"timestamp", "mode", "decision",
                                     "confidence", "latency_ms", "agreement"}


def test_modes_no_network():
    import socket
    real = socket.socket
    socket.socket = lambda *a, **k: (_ for _ in ()).throw(
        AssertionError("network used"))
    try:
        g = ModeGate()
        r = g.evaluate(DecisionMode.SHADOW, "ref13", lambda: "E", local_ok)
        assert r.existing_decision == "E" and r.local_decision is not None
    finally:
        socket.socket = real


def test_modes_deterministic():
    g = ModeGate()
    a = g.evaluate(DecisionMode.SHADOW, "det", lambda: "E", local_ok)
    b = g.evaluate(DecisionMode.SHADOW, "det", lambda: "E", local_ok)
    assert a.local_decision == b.local_decision
    assert a.confidence == b.confidence
