"""PHASE 11 — Shadow Mode + real-world benchmark. READ-ONLY vs production.

- Never imports production pipeline code (raw read-only SQLite only).
- Never writes outside local-decision-engine/logs/.
- Never changes any decision: records existing vs local side by side.
- Logs are redacted (secret patterns + 200-char text cap, hashed refs).
- stdlib only (+psutil if present for memory numbers).

Usage:
    python scripts/shadow_benchmark.py [--out logs/shadow_run_<ts>.jsonl]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from decision_engine.engine import LocalDecisionEngine  # noqa: E402

try:
    import psutil
except ImportError:
    psutil = None

OPP_DB = r"C:\Users\NOUR SOFT\Documents\Default Project\ai-opportunity-engine\data\oppengine.db"
ORCH_DB = r"C:\Users\NOUR SOFT\Documents\AI-Agent-Orchestrator\orchestrator.db"
DATASET = os.path.join(ROOT, "dataset", "decisions_80.jsonl")

SECRET_RE = re.compile(
    r"(sk-[A-Za-z0-9\-_]+|Bearer\s+\S+|api[_-]?key\s*[:=]\s*\S+|"
    r"password\s*[:=]\s*\S+|secret\s*[:=]\s*\S+)", re.IGNORECASE)


def redact(text: str, cap: int = 200) -> str:
    t = SECRET_RE.sub("[REDACTED]", text or "")
    return t[:cap]


def ref(text: str) -> str:
    return hashlib.sha1((text or "").encode()).hexdigest()[:12]


def mem_mb():
    if psutil:
        return round(psutil.Process().memory_info().rss / 1e6, 2)
    return None


def ro(db_path):
    return sqlite3.connect("file:%s?mode=ro" % db_path.replace("\\", "/"), uri=True)


ROUTE_Q = {"agent": {"type": "choice", "instructions": "Which agent should handle this task?",
                     "criteria": {"OpenCode": "large multi-file coding work",
                                  "Aider": "git-heavy scoped code change",
                                  "Qwen": "complex orchestration and planning",
                                  "Gemini": "internet research task"}}}
OPP_Q = {"opp": {"type": "choice", "instructions": "Is this a real service opportunity?",
                 "criteria": {"real": "real service opportunity with a paying client",
                              "maybe": "maybe, needs clarification",
                              "spam": "irrelevant or spam"}}}
NEWS_Q = {"relevance": {"type": "choice",
                        "instructions": "Is this AI related and worth summarizing?",
                        "criteria": {"yes": "AI related and worth summarizing",
                                     "maybe": "possibly relevant, needs a second look",
                                     "no": "not AI related or pure noise"}}}


def run_shadow(eng, stream, item_ref, category, text, questions, existing):
    t0 = time.time()
    try:
        answers = eng.decide(text, questions)
        err = ""
    except Exception as exc:  # failure must not stop the pipeline
        answers, err = {}, "backend_error:" + str(exc)[:120]
    dt_ms = round((time.time() - t0) * 1000, 3)
    rec = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "stream": stream,
           "ref": item_ref, "category": category,
           "text_redacted": redact(text), "existing": existing,
           "answers": answers, "error": err, "latency_ms": dt_ms}
    return rec


def top_choice(answers, name):
    a = (answers or {}).get(name, {})
    if a.get("type") == "choice":
        return a["choice"], a.get("confidence", 0.0)
    if a.get("type") == "noul":
        return ("yes" if a["noul"] >= 0.5 else "no"), abs(a["noul"] - 0.5) * 2
    return (None, 0.0)


def collect(eng):
    recs = []
    # --- stream 1: orchestrator history (30 real tasks) ---
    cx = ro(ORCH_DB)
    for tid, agent, result, desc in cx.execute(
            "SELECT task_id, selected_agent, result, task_description FROM tasks"):
        recs.append(run_shadow(eng, "orchestrator", "task:" + tid[:8], "routing",
                               desc or "", ROUTE_Q,
                               {"selected_agent": agent, "result": result}))
    cx.close()
    # --- stream 2+3: opportunity rows (161 real) through filter + news lens ---
    cx = ro(OPP_DB)
    rows = cx.execute("SELECT raw_requests.id, request_type, ai_relevance, urgency,"
                      " original_text FROM raw_requests JOIN normalized"
                      " ON normalized.raw_id = raw_requests.id").fetchall()
    cx.close()
    for rid, rtype, rel, urg, text in rows:
        worthy = not (rtype in ("human_service", "unclear") and rel == "none")
        recs.append(run_shadow(eng, "opportunity", "raw:%s" % rid, "filter",
                               text or "", OPP_Q,
                               {"request_type": rtype, "ai_relevance": rel,
                                "urgency": urg, "existing_llm_worthy": worthy}))
        recs.append(run_shadow(eng, "news", "raw:%s" % rid, "triage",
                               text or "", NEWS_Q,
                               {"ai_relevance": rel,
                                "existing_keep": rel in ("high", "medium")}))
    # --- stream 4: labeled dataset (78 cases, ground truth) ---
    with open(DATASET, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            c = json.loads(line)
            q = c["question"] if "type" not in c["question"] else {"q": c["question"]}
            recs.append(run_shadow(eng, "dataset", "ds", c["domain"],
                                   c["state"], q, {"expected": c["expected"]}))
    return recs


def verdict_for(rec, thr):
    """Map a record to keep/drop/review at threshold thr. REVIEW_REQUIRED below thr."""
    name = {"orchestrator": "agent", "opportunity": "opp",
            "news": "relevance", "dataset": None}[rec["stream"]]
    if rec["error"] or not rec["answers"]:
        return "review", 0.0, None
    if name is None:  # dataset rows have varying single-question names
        qname = next(iter(rec["answers"]))
        a = rec["answers"][qname]
    else:
        a = rec["answers"].get(name, {})
    if a.get("type") == "choice":
        conf = a.get("confidence", 0.0)
        if conf < thr:
            return "review", conf, a["choice"]
        if rec["stream"] == "opportunity" and a["choice"] == "spam":
            return "drop", conf, a["choice"]
        if rec["stream"] == "news" and a["choice"] == "no":
            return "drop", conf, a["choice"]
        return "keep", conf, a["choice"]
    if a.get("type") == "noul":
        conf = abs(a["noul"] - 0.5) * 2
        if conf < thr:
            return "review", conf, ("yes" if a["noul"] >= 0.5 else "no")
        return "keep", conf, ("yes" if a["noul"] >= 0.5 else "no")
    if a.get("type") == "score":
        conf = a.get("confidence", 0.0)
        return ("review", conf, a["score"]) if conf < thr else ("keep", conf, a["score"])
    return "review", 0.0, None


def summarize(recs, thr):
    lat = sorted(r["latency_ms"] for r in recs)
    n = len(lat)
    out = {"threshold": thr, "n": n,
           "latency_ms": {"p50": lat[n // 2], "p95": lat[int(n * 0.95) - 1],
                          "max": lat[-1], "mean": round(sum(lat) / n, 3)},
           "streams": {}}
    for stream in ("orchestrator", "opportunity", "news", "dataset"):
        sub = [r for r in recs if r["stream"] == stream]
        if not sub:
            continue
        vd = {"keep": 0, "drop": 0, "review": 0}
        agree = dis = hi_agree = hi_dis = 0
        tp = fp = tn = fn = 0
        ds_ok = ds_n = 0
        for r in sub:
            v, conf, top = verdict_for(r, thr)
            vd[v] += 1
            hi = conf >= 0.8
            if stream == "orchestrator":
                exp = r["existing"]["selected_agent"]
                if top == exp:
                    agree += 1
                    hi_agree += 1 if hi else 0
                else:
                    dis += 1
                    hi_dis += 1 if hi else 0
            elif stream == "opportunity":
                exp_keep = r["existing"]["existing_llm_worthy"]
                loc_keep = (v in ("keep", "review"))  # review keeps existing behavior
                if loc_keep == exp_keep:
                    agree += 1
                    hi_agree += 1 if hi else 0
                else:
                    dis += 1
                    hi_dis += 1 if hi else 0
                # vs existing pipeline as reference (NOT ground truth)
                if exp_keep and loc_keep:
                    tp += 1
                elif exp_keep and not loc_keep:
                    fn += 1
                elif not exp_keep and loc_keep:
                    fp += 1
                else:
                    tn += 1
            elif stream == "news":
                exp_keep = r["existing"]["existing_keep"]
                loc_keep = (v in ("keep", "review"))
                if loc_keep == exp_keep:
                    agree += 1
                    hi_agree += 1 if hi else 0
                else:
                    dis += 1
                    hi_dis += 1 if hi else 0
                if exp_keep and loc_keep:
                    tp += 1
                elif exp_keep and not loc_keep:
                    fn += 1
                elif not exp_keep and loc_keep:
                    fp += 1
                else:
                    tn += 1
            else:  # dataset: real ground truth -> accuracy only.
                # Precision/recall need a positive class; reporting them here
                # would be misleading, so they stay None (see dataset_accuracy).
                exp = r["existing"]["expected"]
                ans = r["answers"]
                qn = next(iter(ans)) if ans else None
                a = ans.get(qn, {}) if qn else {}
                ok = None
                if a.get("type") == "choice":
                    ok = (a["choice"] == exp)
                elif a.get("type") == "noul":
                    ok = ((a["noul"] >= 0.5) == bool(exp))
                elif a.get("type") == "score":
                    ok = (int(round(a["score"])) == int(exp))
                if ok is not None:
                    ds_n += 1
                    ds_ok += 1 if ok else 0
        prec = tp / (tp + fp) if (tp + fp) else None
        rec = tp / (tp + fn) if (tp + fn) else None
        s = {"n": len(sub), "verdicts": vd,
             "coverage_actionable": round((vd["keep"] + vd["drop"]) / len(sub), 4),
             "low_confidence_rate": round(vd["review"] / len(sub), 4),
             "agreement": round(agree / len(sub), 4) if stream != "dataset" else None,
             "disagreement": round(dis / len(sub), 4) if stream != "dataset" else None,
             "high_conf_agreement": hi_agree, "high_conf_disagreement": hi_dis,
             "tp": tp, "fp": fp, "tn": tn, "fn": fn,
             "precision_vs_reference": round(prec, 4) if prec is not None else None,
             "recall_vs_reference": round(rec, 4) if rec is not None else None,
             "fpr_vs_reference": round(fp / (fp + tn), 4) if (fp + tn) else None,
             "fnr_vs_reference": round(fn / (fn + tp), 4) if (fn + tp) else None,
             "dataset_accuracy": round(ds_ok / ds_n, 4) if ds_n else None}
        out["streams"][stream] = s
    # cost simulation: drops at thr that the existing pipeline would have sent to LLM
    drops, worthy_drops, worthy_total = 0, 0, 0
    for r in recs:
        if r["stream"] not in ("opportunity", "news"):
            continue
        v, conf, _ = verdict_for(r, thr)
        if r["stream"] == "opportunity" and r["existing"]["existing_llm_worthy"]:
            worthy_total += 1
            if v == "drop":
                worthy_drops += 1
        if v == "drop":
            drops += 1
    out["cost_simulation"] = {
        "note": "estimated reduction in LLM invocations (counts only, no money claims)",
        "total_items": sum(1 for r in recs if r["stream"] in ("opportunity", "news")),
        "items_filtered": drops,
        "items_sent_to_LLM_or_review": sum(1 for r in recs if r["stream"] in ("opportunity", "news")) - drops,
        "llm_worthy_items": worthy_total,
        "llm_worthy_filtered": worthy_drops,
        "estimated_reduction_pct": round(100 * drops / sum(
            1 for r in recs if r["stream"] in ("opportunity", "news")), 2),
        "estimated_reduction_on_llm_worthy_pct": round(
            100 * worthy_drops / worthy_total, 2) if worthy_total else 0.0}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None)
    ap.add_argument("--thresholds", default="0.6,0.7,0.8,0.9")
    ns = ap.parse_args()
    ts = time.strftime("%Y%m%d_%H%M%S")
    out_path = ns.out or os.path.join(ROOT, "logs", "shadow_run_%s.jsonl" % ts)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    eng = LocalDecisionEngine()
    eng.decide("warm up", {"q": {"type": "noul", "instructions": "warm"}})
    m0 = mem_mb()
    t0 = time.time()
    recs = collect(eng)
    wall = time.time() - t0
    m1 = mem_mb()
    with open(out_path, "w", encoding="utf-8") as f:
        for r in recs:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    # determinism: re-run everything, digests must match
    recs2 = collect(eng)
    d1 = hashlib.sha256(json.dumps(
        [(r["ref"], r["answers"]) for r in recs], sort_keys=True).encode()).hexdigest()
    d2 = hashlib.sha256(json.dumps(
        [(r["ref"], r["answers"]) for r in recs2], sort_keys=True).encode()).hexdigest()
    summaries = {}
    for thr in [float(x) for x in ns.thresholds.split(",")]:
        summaries[str(thr)] = summarize(recs, thr)
    lat = sorted(r["latency_ms"] for r in recs)
    n = len(lat)
    report = {"records": n, "wall_s": round(wall, 2),
              "decisions_per_s": round(n / wall, 1),
              "memory_mb": {"before": m0, "after": m1},
              "deterministic": d1 == d2,
              "log": out_path,
              "by_threshold": summaries}
    sp = os.path.join(ROOT, "logs", "shadow_summary_%s.json" % ts)
    with open(sp, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    s06 = summaries["0.6"]
    print(json.dumps({"records": n, "deterministic": d1 == d2,
                      "decisions_per_s": report["decisions_per_s"],
                      "memory_mb": report["memory_mb"],
                      "latency_ms": s06["latency_ms"],
                      "streams_t0.6": s06["streams"],
                      "cost_t0.6": s06["cost_simulation"],
                      "log": out_path, "summary": sp}, indent=2))


if __name__ == "__main__":
    main()
