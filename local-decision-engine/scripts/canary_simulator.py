"""PHASE 12 — Canary simulator. Real data only, zero production impact.

Reads the Phase-11 shadow log (measured answers, no re-computation) and
deterministically samples 1%/5%/10% per class (sha1(ref) % 100 < pct).
Existing decisions are never modified, only compared.

Classes (metrics never mixed):
  A. Agent Routing (orchestrator history)
  B. Opportunity Classification (opportunity rows)
  C. News Filtering (news views)

Usage: python scripts/canary_simulator.py [--log logs/shadow_run_*.jsonl]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

HIGH_CONF = float(os.environ.get("HIGH_CONFIDENCE_THRESHOLD", "0.8"))
THR = 0.6  # policy decision threshold for keep/drop (threshold sweep: Phase 11)


def sampled(ref: str, pct: float) -> bool:
    if pct <= 0:
        return False
    if pct >= 100:
        return True
    return int(hashlib.sha1(ref.encode()).hexdigest(), 16) % 100 < pct


def load(log_path):
    with open(log_path, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def local_top(rec):
    name = {"orchestrator": "agent", "opportunity": "opp",
            "news": "relevance", "dataset": None}[rec["stream"]]
    if name is None:
        qn = next(iter(rec["answers"] or {}), None)
        a = (rec["answers"] or {}).get(qn, {}) if qn else {}
    else:
        a = (rec["answers"] or {}).get(name, {})
    if a.get("type") == "choice":
        return a["choice"], a.get("confidence", 0.0)
    return None, 0.0


def verdict(stream, top, conf):
    if top is None or conf < THR:
        return "review"
    if stream == "opportunity" and top == "spam":
        return "drop"
    if stream == "news" and top == "no":
        return "drop"
    return "keep"


def expected(rec):
    s = rec["stream"]
    if s == "orchestrator":
        return ("agent", rec["existing"]["selected_agent"])
    if s == "opportunity":
        w = rec["existing"]["existing_llm_worthy"]
        return ("keepdrop", "keep" if w else "drop")
    if s == "news":
        k = rec["existing"]["existing_keep"]
        return ("keepdrop", "keep" if k else "drop")
    return ("none", None)


def simulate(recs, stream, pct):
    sub = [r for r in recs if r["stream"] == stream]
    chosen = [r for r in sub if sampled(r["ref"] + stream, pct)]
    m = {"cases": len(sub), "sampled": len(chosen), "high_conf": 0,
         "low_conf": 0, "agreement": 0, "disagreement": 0,
         "review_required": 0, "fp": 0, "fn": 0, "llm_avoided": 0,
         "llm_worthy_avoided": 0}
    for r in chosen:
        top, conf = local_top(r)
        v = verdict(stream, top, conf)
        kind, exp = expected(r)
        if conf >= HIGH_CONF:
            m["high_conf"] += 1
        else:
            m["low_conf"] += 1
        if kind == "agent":
            if top == exp:
                m["agreement"] += 1
            else:
                m["disagreement"] += 1
                if conf < THR:
                    m["review_required"] += 1
            if v == "review":
                m["review_required"] += 0  # counted once below via low-conf
            continue
        if kind == "keepdrop":
            loc_keep = v in ("keep", "review")  # fail-open
            exp_keep = (exp == "keep")
            if loc_keep == exp_keep:
                m["agreement"] += 1
            else:
                m["disagreement"] += 1
            if v == "review":
                m["review_required"] += 1
            if not exp_keep and loc_keep:
                m["fp"] += 1
            if exp_keep and not loc_keep:
                m["fn"] += 1
            if v == "drop":
                m["llm_avoided"] += 1
                if exp_keep:
                    m["llm_worthy_avoided"] += 1
    # review_required for keepdrop already counted; add low-conf keeps? No:
    # review_required == verdict==review count. Recompute exactly:
    m["review_required"] = sum(
        1 for r in chosen
        if verdict(stream, *local_top(r)) == "review")
    return m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", default=None)
    ns = ap.parse_args()
    log = ns.log or sorted(
        [os.path.join(ROOT, "logs", f) for f in os.listdir(os.path.join(ROOT, "logs"))
         if f.startswith("shadow_run_") and f.endswith(".jsonl")])[-1]
    recs = load(log)
    ts = time.strftime("%Y%m%d_%H%M%S")
    out = {"source_log": log, "threshold": THR, "high_conf": HIGH_CONF,
           "classes": {}}
    for stream, label in (("orchestrator", "A_routing"),
                          ("opportunity", "B_opportunity"),
                          ("news", "C_news")):
        out["classes"][label] = {str(p): simulate(recs, stream, p)
                                 for p in (1, 5, 10, 100)}
    sp = os.path.join(ROOT, "logs", "canary_sim_%s.json" % ts)
    with open(sp, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    for label, tabs in out["classes"].items():
        print("== %s ==" % label)
        print("pct | cases sampled hi low | agree disagr review | fp fn | llm_avoided")
        for p, m in tabs.items():
            print("%s | %s %s %s %s | %s %s %s | %s %s | %s (worthy %s)" % (
                p, m["cases"], m["sampled"], m["high_conf"], m["low_conf"],
                m["agreement"], m["disagreement"], m["review_required"],
                m["fp"], m["fn"], m["llm_avoided"], m["llm_worthy_avoided"]))
    print("saved ->", sp)


if __name__ == "__main__":
    main()
