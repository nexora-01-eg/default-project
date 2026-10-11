"""CLI: decision-engine doctor|status|test|models|benchmark|serve|decide (stdlib only)."""
from __future__ import annotations

import argparse
import json
import os
import platform
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "src"))

from decision_engine import __version__  # noqa: E402
from decision_engine.engine import (  # noqa: E402
    DEFAULT_MODEL,
    MODEL_ALIASES,
    LocalDecisionEngine,
    create_engine,
)

BASE = os.environ.get("LOCAL_DECISION_URL", "http://127.0.0.1:8765")


def _get(path: str, timeout=5):
    with urllib.request.urlopen(BASE + path, timeout=timeout) as r:
        return r.status, json.loads(r.read().decode())


def _post(state, questions, model="jev-latest", timeout=30):
    body = json.dumps({"state": state, "model": model, "questions": questions}).encode()
    req = urllib.request.Request(BASE + "/v1/systemone", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, json.loads(r.read().decode())


def cmd_doctor(_a):
    print(f"decision-engine v{__version__}")
    print(f"python: {sys.version.split()[0]} @ {sys.executable}")
    print(f"platform: {platform.system()} {platform.release()} ({platform.machine()})")
    try:
        import psutil  # optional
        print(f"ram_free_gb: {round(psutil.virtual_memory().available / 1e9, 1)}")
    except ImportError:
        print("ram: psutil not installed (optional) — see audit doc")
    import socket
    s = socket.socket()
    busy = s.connect_ex(("127.0.0.1", 8765)) == 0
    s.close()
    print(f"port 8765: {'IN USE' + (' (server may be running — good)' if busy else '')}"
          if busy else "port 8765: FREE")
    eng = LocalDecisionEngine()
    t0 = time.time()
    ans = eng.decide("Someone is asking for a website for their restaurant.",
                     {"opp": {"type": "choice", "instructions": "Is this a real service opportunity?",
                              "criteria": {"A": "real service opportunity", "B": "maybe",
                                           "C": "irrelevant"}}})
    print(f"selftest: {ans} ({round((time.time() - t0) * 1000, 1)}ms, offline)")
    print("telemetry: none. cloud: none. api_key: not required.")


def cmd_status(_a):
    try:
        code, h = _get("/healthz")
        _, m = _get("/v1/models")
        print(json.dumps({"reachable": True, "health": h,
                          "models": [x["name"] for x in m.get("models", [])]}, indent=2))
    except Exception as exc:
        print(json.dumps({"reachable": False, "error": str(exc)[:200],
                          "hint": "start with: decision-engine serve"}, indent=2))


def cmd_models(_a):
    try:
        _, m = _get("/v1/models")
        names = [x["name"] for x in m.get("models", [])]
    except Exception:
        names = [c["name"] for c in LocalDecisionEngine.MODELS] + list(MODEL_ALIASES)
    print("available models (local):")
    for n in names:
        print(f"  - {n}")
    print("note: nli-deberta-large (0.87 GB) installs only after a benchmark gate.")


def cmd_test(_a):
    fails = 0

    def check(name, cond, extra=""):
        nonlocal fails
        print(("PASS " if cond else "FAIL ") + name + (f" — {extra}" if extra else ""))
        if not cond:
            fails += 1

    try:
        code, h = _get("/healthz")
        check("health endpoint", code == 200 and h.get("ok") is True, str(h))
    except Exception as exc:
        check("health endpoint", False, str(exc)[:120])
        print(f"{fails} failure(s)")
        sys.exit(1)
    _, m = _get("/v1/models")
    check("models endpoint", any(x["name"] == DEFAULT_MODEL for x in m.get("models", [])))
    _, r = _post("Someone is asking for a website for their restaurant.",
                 {"opp": {"type": "choice", "instructions": "real service opportunity?",
                          "criteria": {"A": "real service opportunity", "B": "maybe",
                                       "C": "irrelevant"}}})
    a = r["answers"]["opp"]
    check("choice shape", a["type"] == "choice" and abs(sum(a["probabilities"].values()) - 1) < 0.01,
          json.dumps(a))
    _, r2 = _post("The server is down, fix it ASAP!", {"u": {"type": "noul", "instructions": "urgent"}})
    check("noul shape", r2["answers"]["u"]["type"] == "noul")
    _, r3 = _post("Small typo on page.", {"s": {"type": "score", "instructions": "severity",
                                                "criteria": ["minor", "major", "blocking"]}})
    s = r3["answers"]["s"]
    check("score shape", s["type"] == "score" and 0 <= s["score"] <= 2)
    print("ALL PASS" if fails == 0 else f"{fails} failure(s)")
    sys.exit(1 if fails else 0)


def cmd_decide(a):
    questions = json.loads(a.questions) if a.questions else {
        "decision": {"type": "choice", "instructions": a.instructions or "Classify the input.",
                     "criteria": {"A": a.a or "yes", "B": a.b or "no"}}}
    try:
        _, r = _post(a.text, questions, model=a.model, timeout=a.timeout)
        print(json.dumps(r["answers"], indent=2, ensure_ascii=False))
    except Exception as exc:  # server down -> direct in-process fallback
        eng = create_engine("local")
        print(json.dumps(eng.decide(a.text, questions), indent=2, ensure_ascii=False))
        print(f"# note: served in-process ({str(exc)[:80]})", file=sys.stderr)


def cmd_benchmark(a):
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    import run_benchmark
    run_benchmark.main(a)


def cmd_serve(a):
    from decision_engine.server import run
    run(host=a.host, port=a.port)


def build():
    p = argparse.ArgumentParser(prog="decision-engine",
                                description="Local decision engine (offline, no API key).")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("doctor").set_defaults(fn=cmd_doctor)
    sub.add_parser("status").set_defaults(fn=cmd_status)
    sub.add_parser("test").set_defaults(fn=cmd_test)
    sub.add_parser("models").set_defaults(fn=cmd_models)
    b = sub.add_parser("benchmark"); b.add_argument("--cases", default="dataset/decisions_80.jsonl")
    b.add_argument("--threshold", type=float, default=0.6); b.set_defaults(fn=cmd_benchmark)
    s = sub.add_parser("serve"); s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8765); s.set_defaults(fn=cmd_serve)
    d = sub.add_parser("decide"); d.add_argument("--text", required=True)
    d.add_argument("--questions", default=""); d.add_argument("--instructions", default="")
    d.add_argument("--a", default="yes"); d.add_argument("--b", default="no")
    d.add_argument("--model", default="jev-latest"); d.add_argument("--timeout", type=int, default=30)
    d.set_defaults(fn=cmd_decide)
    return p


def main(argv=None):
    args = build().parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main()
