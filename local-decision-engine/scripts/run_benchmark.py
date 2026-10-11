"""Offline benchmark: accuracy, calibration, latency, resources. No invented numbers.

Usage: decision-engine benchmark [--cases dataset/decisions_80.jsonl] [--threshold 0.6]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

try:
    import psutil
except ImportError:
    psutil = None

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from decision_engine.engine import LocalDecisionEngine  # noqa: E402


def load_cases(path):
    cases = []
    with open(path, encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if line:
                c = json.loads(line)
                c["_line"] = i
                cases.append(c)
    return cases


def norm_questions(q):
    """Dataset rows may hold a bare wire question or {name: wire}."""
    if isinstance(q, dict) and "type" in q:
        return {"q": q}
    return q


def judge(case, answers):
    """Return (correct: bool|None, confidence: float). None = unsupported shape."""
    q = norm_questions(case["question"])
    exp = case["expected"]
    name = next(iter(q))
    wire, ans = q[name], answers[name]
    if wire["type"] == "choice":
        return ans["choice"] == exp, ans.get("confidence", 0.0)
    if wire["type"] == "noul":
        pred = ans["noul"] >= 0.5
        return bool(pred) == bool(exp), abs(ans["noul"] - 0.5) * 2
    if wire["type"] == "score":
        pred = int(round(ans["score"]))
        return pred == int(exp), ans.get("confidence", 0.0)
    return None, 0.0


def mem_mb():
    if psutil:
        return round(psutil.Process().memory_info().rss / 1e6, 1)
    return None


def main(a=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", default=os.path.join(ROOT, "dataset", "decisions_80.jsonl"))
    ap.add_argument("--threshold", type=float, default=0.6)
    ns = ap.parse_args([] if a is None else ([a.cases, "--threshold", str(a.threshold)]
                                             if hasattr(a, "cases") else []))
    cases = load_cases(ns.cases if hasattr(ns, "cases") else ns.cases)
    eng = LocalDecisionEngine()
    # warm-up (excluded from timing)
    eng.decide("warm up", {"q": {"type": "noul", "instructions": "warm"}})

    t0 = time.time()
    mem0 = mem_mb()
    rows, lat = [], []
    for c in cases:
        q = norm_questions(c["question"])
        s = time.time()
        try:
            answers = eng.decide(c["state"], q)
            dt = (time.time() - s) * 1000
            ok, conf = judge(c, answers)
        except Exception as exc:  # count, never hide
            dt, ok, conf, answers = (time.time() - s) * 1000, False, 0.0, {"error": str(exc)[:120]}
        lat.append(dt)
        rows.append({"line": c["_line"], "domain": c["domain"], "expected": c["expected"],
                     "answers": answers, "correct": ok, "confidence": round(conf, 3),
                     "latency_ms": round(dt, 2)})
    total_s = time.time() - t0
    mem1 = mem_mb()
    n = len(rows)
    correct = sum(1 for r in rows if r["correct"] is True)
    wrong = [r for r in rows if r["correct"] is False]
    sure = [r for r in rows if r["confidence"] >= 0.8]
    sure_ok = sum(1 for r in sure if r["correct"])
    lat_sorted = sorted(lat)
    by_domain = {}
    for r in rows:
        d = by_domain.setdefault(r["domain"], {"n": 0, "ok": 0})
        d["n"] += 1
        d["ok"] += 1 if r["correct"] else 0

    report = {
        "engine": "rules-tfidf", "version": "0.1.0", "cases": n,
        "accuracy": round(correct / n, 4) if n else 0,
        "correct": correct, "wrong": len(wrong),
        "accuracy_when_sure_conf_ge_0.8": round(sure_ok / len(sure), 4) if sure else None,
        "n_sure": len(sure),
        "latency_ms": {"p50": round(lat_sorted[n // 2], 2),
                       "p95": round(lat_sorted[int(n * 0.95) - 1], 2),
                       "max": round(max(lat), 2), "mean": round(sum(lat) / n, 2)},
        "total_s": round(total_s, 2),
        "throughput_per_s": round(n / total_s, 1) if total_s else None,
        "ram_mb": {"before": mem0, "after": mem1},
        "vram": "not used (CPU/std-only backend)",
        "by_domain": {k: {"n": v["n"], "acc": round(v["ok"] / v["n"], 3)} for k, v in by_domain.items()},
        "startup_time_s": "see server log (import + first decision)",
        "stability": "no crashes/errors other than rows flagged below",
        "errors": [r for r in rows if "error" in r["answers"]][:10],
        "false_positives_negatives": [
            {"line": r["line"], "domain": r["domain"], "expected": r["expected"],
             "got": list(r["answers"].values())[0] if r["answers"] else None}
            for r in wrong[:20]],
    }
    out = os.path.join(ROOT, "docs", "BENCHMARK_RESULT.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(json.dumps({k: v for k, v in report.items() if k != "false_positives_negatives"}, indent=2))
    print(f"\nfull report -> {out}  ({n} cases, {correct} correct)")


if __name__ == "__main__":
    main()
