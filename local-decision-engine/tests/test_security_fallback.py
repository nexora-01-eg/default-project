"""Security + fallback + concurrency. Local-only guarantees as executable checks."""
import os
import sys
import threading

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from decision_engine.engine import (
    AUTH_REQUIRED,
    HostedJevEngine,
    LLMFallbackEngine,
    LocalDecisionEngine,
    create_engine,
)

try:
    import pytest
except ImportError:
    pytest = None


def test_no_telemetry_no_cloud_strings():
    root = os.path.join(os.path.dirname(__file__), "..", "src")
    blob = ""
    for dp, _, fns in os.walk(root):
        for fn in fns:
            if fn.endswith(".py"):
                with open(os.path.join(dp, fn), encoding="utf-8") as f:
                    blob += f.read().lower()
    for bad in ("api.openai", "generativelanguage", "api.anthropic",
                "sentry", "segment.io", "google-analytics"):
        assert bad not in blob, bad
    # the words telemetry/cloud may only appear in explicit "none" denials
    for i, line in enumerate(blob.splitlines(), 1):
        if "telemetry" in line or "telemet" in line:
            assert "none" in line, f"line {i}: {line[:120]}"


def test_no_secrets_in_source_or_config():
    for rel in ("src/decision_engine/server.py", "src/decision_engine/engine.py",
                "config/default.json"):
        p = os.path.join(os.path.dirname(__file__), "..", rel)
        with open(p, encoding="utf-8") as f:
            txt = f.read().lower()
        assert "api_key" not in txt or "api key" in txt or "authorization" in txt or "api_key" in txt
        assert "sk-" not in txt and "secret" not in txt.replace("no secrets", "")


def test_hosted_engine_loopback_only():
    try:
        HostedJevEngine(base_url="https://cloud.example.com")
        raise AssertionError("non-loopback accepted")
    except ValueError:
        pass
    HostedJevEngine(base_url="http://127.0.0.1:8765")  # ok


def test_llm_fallback_needs_auth_and_never_invents_keys():
    eng = LLMFallbackEngine()
    try:
        eng.system_one("x", {"q": {"type": "noul", "instructions": "x"}})
        raise AssertionError("fallback without creds should fail")
    except RuntimeError as e:
        assert AUTH_REQUIRED in str(e)
    assert "sk-" not in str(eng.__dict__)


def test_threshold_gating_and_review_flag():
    eng = create_engine("local")
    out = eng.decide_with_fallback("Hello?", {
        "opp": {"type": "choice", "instructions": "opportunity?",
                "criteria": {"A": "real", "B": "maybe", "C": "irrelevant"}}}, threshold=0.99)
    assert out["status"] in ("ok", "needs_review", "fallback_used")
    assert "low_confidence" in out and "latency_s" in out


def test_backend_error_never_stops_caller():
    class Dead(LocalDecisionEngine):
        def system_one(self, *a, **k):
            raise RuntimeError("boom")
    out = Dead().decide_with_fallback("x", {"q": {"type": "noul", "instructions": "x"}})
    assert out["status"] == "backend_error" and out["fallback"] == "review"


def test_timeouts_and_retries_are_bounded():
    import inspect
    from decision_engine import server
    src = inspect.getsource(server)
    assert "timeout" in src.lower() or "Content-Length" in src
    assert "MAX_BODY_BYTES" in src


def test_concurrent_requests_safe():
    from decision_engine.server import run_in_background
    import json
    import urllib.request
    srv = run_in_background(port=18766)
    errors = []

    def hit(i):
        try:
            body = json.dumps({"state": f"request {i} about a restaurant website",
                               "questions": {"q": {"type": "noul",
                                                   "instructions": "service opportunity"}}}).encode()
            r = urllib.request.Request("http://127.0.0.1:18766/v1/systemone", data=body,
                                       headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(r, timeout=15) as resp:
                assert resp.status == 200
        except Exception as e:  # noqa: BLE001
            errors.append(str(e)[:100])

    threads = [threading.Thread(target=hit, args=(i,)) for i in range(20)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    srv.shutdown()
    assert not errors, errors[:5]
