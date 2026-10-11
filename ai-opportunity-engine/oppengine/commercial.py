"""Commercial analysis (Phase 2): revenue intent + demand + gap + buildability.

Every field carries provenance: OBSERVED (source rows), INFERRED (rules over evidence),
UNKNOWN (no data). Nothing is presented as guaranteed revenue.
"""
import json

from . import db as DB
from . import demand as DEM
from . import opp_types as OT
from . import revenue as REV

LEVEL_ORDER = ["not_commercial", "unknown", "low", "medium", "high"]

COMPLEXITY = ("trivial", "simple", "moderate", "complex", "unknown")

SERVICE_IDEAS_BY_TYPE = {
    "AI automation": ["one-time custom build", "automation service", "monthly maintenance"],
    "AI integration": ["setup service", "API integration", "monthly maintenance"],
    "AI video": ["automation service", "productized service", "one-time custom build"],
    "AI transcription": ["automation service", "productized service"],
    "AI translation": ["automation service", "productized service"],
    "AI audio": ["one-time custom build", "automation service"],
    "AI document processing": ["automation service", "small internal tool", "monthly maintenance"],
    "AI data extraction": ["automation service", "small internal tool"],
    "AI customer support": ["setup service", "monthly maintenance", "API integration"],
    "AI lead processing": ["setup service", "monthly maintenance"],
    "AI content": ["productized service", "monthly maintenance"],
    "AI developer tooling": ["one-time custom build", "small internal tool"],
    "AI research": ["small internal tool", "one-time custom build"],
    "AI workflow": ["automation service", "monthly maintenance"],
    "AI local business solution": ["setup service", "productized service", "monthly maintenance"],
    "AI productivity": ["small internal tool", "productized service"],
    "custom AI software": ["one-time custom build", "setup service"],
    "non-AI automation": ["automation service", "setup service"],
    "not suitable": [],
}


def _member_revenue(db_path, opp_id):
    cx = DB.connect(db_path)
    try:
        return [dict(r) for r in cx.execute(
            "SELECT rs.* FROM opportunity_members m JOIN normalized n ON n.id=m.normalized_id "
            "JOIN revenue_signals rs ON rs.request_id=n.raw_id WHERE m.opportunity_id=?", (opp_id,))]
    finally:
        cx.close()


def estimate_complexity(opp, members):
    avg_req = sum(len(json.loads(m.get("requirements") or "[]")) for m in members) / max(len(members), 1)
    feas = opp.get("ai_feasibility") or ""
    if feas in ("not_ai", "insufficient_info"):
        return "unknown"
    if feas in ("clearly_feasible", "feasible_with_local_tools") and avg_req <= 2:
        return "simple" if avg_req >= 1 else "trivial"
    if feas in ("difficult", "impractical"):
        return "complex"
    return "moderate"


def analyze(db_path, opp):
    import sqlite3
    members = DEM._members(db_path, opp["id"])
    revs = _member_revenue(db_path, opp_id=opp["id"])
    levels = [r.get("level") for r in revs if r.get("level")]
    agg = max(levels, key=lambda l: LEVEL_ORDER.index(l)) if levels else "unknown"
    urg_order = {"low": 0, "medium": 1, "high": 2}
    urg = max([r.get("urgency") or "low" for r in revs],
              key=lambda u: urg_order.get(u, 0)) if revs else "low"
    buyer = any(r.get("business_context") for r in revs)
    cx = DB.connect(db_path)
    try:
        sols = [dict(r) for r in cx.execute(
            "SELECT * FROM solutions WHERE opportunity_id=?", (opp["id"],))]
    finally:
        cx.close()
    complaints = [s for s in sols if s.get("complaints")]
    if sols and complaints:
        comp, comp_prov = ("high" if len(sols) >= 3 else "moderate"), "INFERRED from solution count"
    elif sols:
        comp, comp_prov = "moderate", "INFERRED from solution count"
    else:
        comp, comp_prov = "unknown", "UNKNOWN: no solution lookup yet"
    gap = ("identified" if (opp.get("gap_analysis") or "").strip() else
           "partial" if complaints else "unknown")
    local = (opp.get("local_feasibility") or "UNKNOWN").lower()
    local = local if local in ("high", "medium", "low") else "unknown"
    cplx = estimate_complexity(opp, members)
    confs = [m.get("confidence") or 0 for m in members]
    conf = round(sum(confs) / len(confs), 3) if confs else 0.0
    tags = OT.valid(json.loads(opp.get("opp_types") or "[]")) or \
        OT.tag(" ".join((m.get("normalized_text") or "")[:200] for m in members[:3]),
               opp.get("ai_feasibility") or "", "")
    ideas = []
    for t in tags:
        ideas += SERVICE_IDEAS_BY_TYPE.get(t, [])
    ideas = sorted(set(ideas))
    prov = {"revenue_intent": "INFERRED from member revenue signals" if revs else "UNKNOWN: no revenue signals",
            "demand_strength": "INFERRED from member counts",
            "urgency": "OBSERVED revenue/urgency signals" if revs else "UNKNOWN",
            "buyer_context": "OBSERVED business-context signals" if buyer else "UNKNOWN: no business context observed",
            "competition_level": comp_prov,
            "solution_gap": "OBSERVED gap analysis" if gap == "identified" else ("INFERRED from complaints" if gap == "partial" else "UNKNOWN"),
            "local_buildability": "OBSERVED local capability match",
            "estimated_complexity": "INFERRED heuristic (requirements + feasibility)",
            "evidence_confidence": "INFERRED from member confidences"}
    row = {"opportunity_id": opp["id"], "revenue_intent": agg,
           "demand_strength": opp.get("demand_strength") or "single_observation",
           "urgency": urg, "buyer_context": "business" if buyer else "unknown",
           "competition_level": comp if comp != "unknown" else "unknown",
           "solution_gap": gap, "local_buildability": local,
           "estimated_complexity": cplx, "evidence_confidence": conf, "provenance": prov}
    cx = DB.connect(db_path)
    try:
        cx.execute("INSERT INTO commercial_analysis(opportunity_id,revenue_intent,demand_strength,"
                   "urgency,buyer_context,competition_level,solution_gap,local_buildability,"
                   "estimated_complexity,evidence_confidence,analyzed_at,provenance)"
                   " VALUES(?,?,?,?,?,?,?,?,?,?,?,?) "
                   "ON CONFLICT(opportunity_id) DO UPDATE SET revenue_intent=excluded.revenue_intent,"
                   " demand_strength=excluded.demand_strength, urgency=excluded.urgency,"
                   " buyer_context=excluded.buyer_context, competition_level=excluded.competition_level,"
                   " solution_gap=excluded.solution_gap, local_buildability=excluded.local_buildability,"
                   " estimated_complexity=excluded.estimated_complexity,"
                   " evidence_confidence=excluded.evidence_confidence,"
                   " analyzed_at=excluded.analyzed_at, provenance=excluded.provenance",
                   (opp["id"], agg, row["demand_strength"], urg, row["buyer_context"], comp,
                    gap, local, cplx, conf, DB.now_iso(), json.dumps(prov, ensure_ascii=False)))
        cx.execute("UPDATE opportunities SET revenue_intent=?, complexity=?, service_ideas=?,"
                   " opp_types=?, updated_at=? WHERE id=?",
                   (agg, cplx, json.dumps([{ "format": i, "pricing": "UNKNOWN"} for i in ideas], ensure_ascii=False),
                    json.dumps(tags, ensure_ascii=False), DB.now_iso(), opp["id"]))
        # traceable evidence rows (cap: refresh per analysis)
        cx.execute("DELETE FROM opportunity_evidence WHERE opportunity_id=? AND evidence_type LIKE 'rev-%'",
                   (opp["id"],))
        for r in revs[:20]:
            evs = []
            try:
                evs = json.loads(r.get("evidence") or "[]")
            except Exception:
                pass
            for e in evs[:3]:
                cx.execute("INSERT INTO opportunity_evidence(opportunity_id,request_id,evidence_type,"
                           "evidence_text,source_url,observed_at) VALUES(?,?,?,?,?,?)",
                           (opp["id"], r.get("request_id"), "rev-" + str(e.get("kind")),
                            str(e.get("phrase"))[:300], None, DB.now_iso()))
        cx.commit()
    finally:
        cx.close()
    return row


def refresh_all(db_path):
    cx = DB.connect(db_path)
    try:
        opps = [dict(r) for r in cx.execute("SELECT * FROM opportunities")]
    finally:
        cx.close()
    return [analyze(db_path, o) for o in opps]
