import json
import os
import sys
import urllib.request
import urllib.error

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from decision_engine.server import run_in_background

BASE = "http://127.0.0.1:18765"
_srv = run_in_background(port=18765)


def req(method, path, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    r = urllib.request.Request(BASE + path, data=data, method=method,
                               headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(r, timeout=15) as resp:
            return resp.status, dict(resp.headers), json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), json.loads(e.read().decode())


def low(headers):
    return {k.lower(): v for k, v in headers.items()}


def test_health():
    code, headers, body = req("GET", "/healthz")
    assert code == 200 and body["ok"] is True
    assert "x-typesafe-request-id" in low(headers)


def test_models():
    code, _, body = req("GET", "/v1/models")
    assert code == 200 and any(m["name"] == "rules-tfidf" for m in body["models"])
    assert any(m["name"] == "jev-latest" for m in body["models"])


def test_systemone_shapes():
    code, _, body = req("POST", "/v1/systemone", {
        "state": "You charged my card twice this month. Fix it.",
        "questions": {
            "refund": {"type": "noul", "instructions": "asking for money back"},
            "team": {"type": "choice", "instructions": "handling team",
                     "criteria": {"billing": "charges", "technical": "bugs"}},
            "sev": {"type": "score", "instructions": "severity",
                    "criteria": ["minor", "major"]}}})
    assert code == 200
    assert body["model"] == "rules-tfidf"
    assert abs(sum(body["answers"]["team"]["probabilities"].values()) - 1) < 0.02


def test_malformed_inputs():
    assert req("POST", "/v1/systemone", {"state": "x", "questions": {}})[0] == 422
    assert req("POST", "/v1/systemone", {"state": "x", "questions": {"q": {"type": "z"}}})[0] == 422
    assert req("POST", "/v1/systemone", {"state": "", "questions": {"q": {"type": "noul", "instructions": "x"}}})[0] == 422
    assert req("POST", "/v1/systemone", {"state": "x", "model": "nope",
                                         "questions": {"q": {"type": "noul", "instructions": "x"}}})[0] == 404


def test_truncation_header():
    code, headers, _ = req("POST", "/v1/systemone",
                           {"state": "word " * 9000,
                            "questions": {"q": {"type": "noul", "instructions": "x"}}})
    assert code == 200 and low(headers).get("x-local-jev-truncated") == "true"
