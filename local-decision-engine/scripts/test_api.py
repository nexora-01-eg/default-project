"""End-to-end API check against a running server (stdlib only).

Usage: python scripts/test_api.py [base_url]  (default http://127.0.0.1:8765)
Exit non-zero on any failure. No invented passes: every check prints PASS/FAIL.
"""
from __future__ import annotations

import json
import sys
import urllib.request
import urllib.error

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8765"
fails = []


def check(name, cond, extra=""):
    print(("PASS " if cond else "FAIL ") + name + (f" — {extra}" if extra and not cond else ""))
    if not cond:
        fails.append(name)


def get(path):
    with urllib.request.urlopen(BASE + path, timeout=10) as r:
        return r.status, dict(r.headers), json.loads(r.read().decode())


def post(payload):
    body = json.dumps(payload, ensure_ascii=False).encode()
    req = urllib.request.Request(BASE + "/v1/systemone", data=body,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, dict(r.headers), json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), json.loads(e.read().decode())


code, headers, h = get("/healthz")
check("health 200 ok=true", code == 200 and h.get("ok") is True, str(h))
check("request-id header", "x-typesafe-request-id" in {k.lower() for k in headers})

code, _, m = get("/v1/models")
check("models lists rules-tfidf", code == 200 and any(
    x["name"] == "rules-tfidf" for x in m.get("models", [])), str(m)[:150])

code, _, r = post({"state": "You charged my card twice this month. Fix it.", "model": "jev-latest",
                   "questions": {
                       "refund": {"type": "noul", "instructions": "The customer is asking for money back"},
                       "team": {"type": "choice", "instructions": "Which team should handle this",
                                "criteria": {"billing": "Charges and refunds", "technical": "Bugs",
                                             "sales": "Pricing"}},
                       "severity": {"type": "score", "instructions": "How serious is the problem",
                                    "criteria": ["Minor annoyance", "Real problem with a workaround",
                                                 "Blocking"]}}})
check("systemone 200", code == 200, str(r)[:200])
a = r.get("answers", {})
check("noul in [0,1]", a.get("refund", {}).get("type") == "noul"
      and 0 <= a["refund"]["noul"] <= 1, str(a.get("refund")))
check("choice probs sum~1", a.get("team", {}).get("type") == "choice"
      and abs(sum(a["team"]["probabilities"].values()) - 1) < 0.02, str(a.get("team")))
check("score in range", a.get("severity", {}).get("type") == "score"
      and 0 <= a["severity"]["score"] <= 2, str(a.get("severity")))
check("usage present", "usage" in r, str(r.keys()))
check("response model echo", r.get("model") == "rules-tfidf", str(r.get("model")))

code, _, r = post({"state": "x" * 30000, "questions": {"q": {"type": "noul", "instructions": "x"}}})
check("long state shortened not refused", code == 200, f"code={code}")

code, _, _ = post({"state": "hi", "questions": {}})
check("empty questions -> 422", code == 422, f"code={code}")
code, _, _ = post({"state": "hi", "questions": {"q": {"type": "bogus"}}})
check("bad type -> 422", code == 422, f"code={code}")
code, _, _ = post({"state": "hi", "model": "nope", "questions": {"q": {"type": "noul", "instructions": "x"}}})
check("unknown model -> 404", code == 404, f"code={code}")
code, _, _ = post({"state": "hi", "model": "nli-deberta-large",
                   "questions": {"q": {"type": "noul", "instructions": "x"}}})
check("nli not installed -> 503 model_unavailable", code == 503, f"code={code}")
code, _, _ = post({"state": "", "questions": {"q": {"type": "noul", "instructions": "x"}}})
check("empty state -> 422", code == 422, f"code={code}")

print("ALL PASS" if not fails else f"{len(fails)} FAILURE(S): {fails}")
sys.exit(1 if fails else 0)
