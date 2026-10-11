"""Opportunity scoring (Phase 2): explainable components, evidence-backed.

score = .20*demand + .12*freshness + .10*growth + .10*feasibility + .15*revenue
      + .08*urgency + .07*gap + .05*competition + .05*local + .03*ease + .05*confidence
Wording: commercial SIGNAL / evidence / potential / confidence. Never guaranteed revenue.
"""
import json
import math

from . import db as DB
from . import demand as DEM
from . import revenue as REV
from .cluster import opportunity_age_days

FEAS_W = {"clearly_feasible": 1.0, "feasible_with_local_tools": 0.9, "feasible_with_human": 0.7,
          "feasible_with_external": 0.6, "experimental": 0.4, "difficult": 0.3,
          "impractical": 0.1, "not_ai": 0.0, "insufficient_info": 0.2}

LOCAL_W = {"high": 1.0, "medium": 0.6, "low": 0.25}
EASE_W = {"trivial": 1.0, "simple": 0.8, "moderate": 0.5, "complex": 0.25, "unknown": 0.4}

WEIGHTS = {"demand": 0.20, "freshness": 0.12, "growth": 0.10, "feasibility": 0.10,
           "revenue": 0.15, "urgency": 0.08, "gap": 0.07, "competition": 0.05,
           "local": 0.05, "ease": 0.03, "confidence": 0.05}


def _commercial_keywords(texts):
    hints = ["سعر", "ميزانية", "budget", "price", "ادفع", "pay", "مستعد", "$",
             "freelance", "فريلانس", "مشروع", "عميل", "client", "hiring"]
    blob = " ".join(texts or []).lower()
    return min(1.0, sum(1 for h in hints if h in blob) / 3.0)


def score_opportunity(db_path, opp):
    members = DEM._members(db_path, opp["id"])
    cx = DB.connect(db_path)
    try:
        rejected = cx.execute("SELECT COUNT(*) c FROM feedback WHERE opportunity_id=? AND decision IN"
                              "('ignore','already_solved','too_difficult','archive')",
                              (opp["id"],)).fetchone()["c"]
        boosts = cx.execute("SELECT COUNT(*) c FROM feedback WHERE opportunity_id=? AND decision IN"
                            "('interesting','investigate','build')", (opp["id"],)).fetchone()["c"]
        revs = [dict(r) for r in cx.execute(
            "SELECT rs.* FROM opportunity_members m JOIN normalized n ON n.id=m.normalized_id "
            "JOIN revenue_signals rs ON rs.request_id=n.raw_id WHERE m.opportunity_id=?", (opp["id"],))]
        sols = [dict(r) for r in cx.execute(
            "SELECT * FROM solutions WHERE opportunity_id=?", (opp["id"],))]
        comm = cx.execute("SELECT * FROM commercial_analysis WHERE opportunity_id=?",
                          (opp["id"],)).fetchone()
        comm = dict(comm) if comm else {}
    finally:
        cx.close()
    n = max(len(members), 1)
    indep = DEM.independent_count(members)
    demand = min(1.0, math.log10(1 + indep) / math.log10(11))
    ages = [opportunity_age_days(m.get("collected_at") or opp.get("created_at") or "") for m in members]
    fresh = sum(1.0 / (1.0 + a / 3.0) for a in ages) / n if ages else 0.0
    growth = sum(1 for a in ages if a <= 2.0) / n if ages else 0.0
    feas = FEAS_W.get(opp.get("ai_feasibility") or "", 0.3)
    levels = [r.get("level") for r in revs if r.get("level")]
    rev_level = max(levels, key=lambda l: ["not_commercial", "unknown", "low", "medium", "high"].index(l)) if levels else "unknown"
    revenue = REV.level_score(rev_level)
    urg = sum({"high": 1.0, "medium": 0.6, "low": 0.3}.get((m.get("urgency") or "low"), 0.3)
              for m in members) / n
    gap = 0.8 if (opp.get("gap_analysis") or "").strip() else (
        0.6 if any(s.get("complaints") for s in sols) else (0.4 if sols else 0.2))
    competition = 0.6 if not sols else (0.5 if len(sols) <= 2 else 0.3)
    local = LOCAL_W.get((opp.get("local_feasibility") or "").lower(), 0.4)
    ease = EASE_W.get(opp.get("complexity") or "unknown", 0.4)
    confs = [m.get("confidence") or 0 for m in members]
    conf = sum(confs) / len(confs) if confs else 0.0
    kw = _commercial_keywords([m.get("original_text", "") for m in members])
    parts = {"demand": demand, "freshness": fresh, "growth": growth, "feasibility": feas,
             "revenue": revenue, "urgency": urg, "gap": gap, "competition": competition,
             "local": local, "ease": ease, "confidence": round(conf, 3)}
    score = sum(parts[k] * WEIGHTS[k] for k in WEIGHTS)
    score = max(0.0, min(1.0, score + 0.05 * boosts - 0.15 * min(rejected, 2)))
    detail = {k: round(v, 3) for k, v in parts.items()}
    detail.update({"members": n, "independent": indep, "boosts": boosts, "rejects": rejected,
                   "revenue_level": rev_level, "keyword_signal": round(kw, 3)})
    return round(score, 4), detail


def rescore_all(db_path):
    cx = DB.connect(db_path)
    try:
        opps = [dict(r) for r in cx.execute("SELECT * FROM opportunities")]
    finally:
        cx.close()
    for o in opps:
        s, detail = score_opportunity(db_path, o)
        cx = DB.connect(db_path)
        try:
            ev = {}
            try:
                ev = json.loads(o.get("evidence") or "{}")
            except Exception:
                pass
            ev["scoring"] = detail
            cx.execute("UPDATE opportunities SET score=?, evidence=?, updated_at=? WHERE id=?",
                       (s, json.dumps(ev, ensure_ascii=False), DB.now_iso(), o["id"]))
            cx.commit()
        finally:
            cx.close()
    return len(opps)
