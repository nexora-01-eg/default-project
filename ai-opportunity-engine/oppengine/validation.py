"""Opportunity validation (Phase 3.5): states, guards, cross-evidence search.

States: SINGLE_OBSERVATION | REPEATED_SAME_AUTHOR | INDEPENDENT_DEMAND |
CROSS_SOURCE_DEMAND | VALIDATED_OPPORTUNITY | SPURIOUS_MATCH | INSUFFICIENT_EVIDENCE.
Nothing is deleted: reclassification only writes validation_* columns + evidence rows.
"""
import json

from . import db as DB
from . import demand as DEM
from . import domains as DOM
from . import semantic as SEM

STATES = ("SINGLE_OBSERVATION", "REPEATED_SAME_AUTHOR", "INDEPENDENT_DEMAND",
          "CROSS_SOURCE_DEMAND", "VALIDATED_OPPORTUNITY", "SPURIOUS_MATCH",
          "INSUFFICIENT_EVIDENCE")

FEASIBLE = {"clearly_feasible", "feasible_with_local_tools", "feasible_with_human",
            "feasible_with_external", "experimental"}


def _member_revenue(db_path, raw_ids):
    if not raw_ids:
        return {}
    cx = DB.connect(db_path)
    try:
        rows = cx.execute(
            f"SELECT request_id, level FROM revenue_signals WHERE request_id IN "
            f"({','.join('?' * len(raw_ids))})", tuple(raw_ids)).fetchall()
        return {r["request_id"]: r["level"] for r in rows}
    finally:
        cx.close()


def validate_opportunity(db_path, opp, threshold=None):
    """Recompute guards + state for one opportunity. Writes validation columns."""
    members = DEM._members(db_path, opp["id"])
    n = len(members)
    rev = _member_revenue(db_path, [m.get("raw_id") for m in members if m.get("raw_id")])
    if n == 0:
        return _store(db_path, opp["id"], "INSUFFICIENT_EVIDENCE", "no members",
                      0, 0, 0, {"verdict": "unknown-domain", "reasons": ["empty cluster"]})
    seed = members[0]
    pair_details, flagged_with_seed = [], []
    for m in members[1:]:
        g = DOM.pair_guard(seed.get("normalized_text") or "", seed.get("request_type") or "",
                           m.get("normalized_text") or "", m.get("request_type") or "")
        pair_details.append({"with": m.get("raw_id"), "verdict": g["verdict"],
                             "reasons": g["reasons"]})
        if g["verdict"] == "flagged":
            flagged_with_seed.append(m.get("raw_id"))
    same_problem = 1 + sum(1 for i, m in enumerate(members[1:])
                           if pair_details[i]["verdict"] in ("pass", "unknown-domain"))
    verdict = "flagged" if flagged_with_seed else (
        "unknown-domain" if any(p["verdict"] == "unknown-domain" for p in pair_details) else "pass")
    guard = {"verdict": verdict, "pairs": pair_details,
             "flagged_members": flagged_with_seed}
    indep = DEM.independent_count(members)
    sources = sorted({m.get("source", "?") for m in members})
    min_req = 2
    confs = [m.get("confidence") or 0 for m in members]
    max_conf = max(confs) if confs else 0
    levels = [rev.get(m.get("raw_id")) for m in members if rev.get(m.get("raw_id"))]
    top_rev = max(levels, key=lambda l: ["not_commercial", "unknown", "low", "medium", "high"].index(l)) if levels else "unknown"
    if n == 1:
        if max_conf < 0.4 and top_rev == "unknown":
            return _store(db_path, opp["id"], "INSUFFICIENT_EVIDENCE",
                          f"single weak member: conf={max_conf}, revenue={top_rev}",
                          indep, len(sources), same_problem, guard)
        return _store(db_path, opp["id"], "SINGLE_OBSERVATION",
                      "n=1: candidate, not a validated market",
                      indep, len(sources), same_problem, guard)
    if same_problem < min_req:
        if flagged_with_seed:
            reason = (f"cross-domain guard failed: only {same_problem} coherent member(s); "
                      f"flagged raw_ids {flagged_with_seed}; "
                      f"{pair_details[0]['reasons'] if pair_details else ''}")
            return _store(db_path, opp["id"], "SPURIOUS_MATCH", reason, indep,
                          len(sources), same_problem, guard)
        return _store(db_path, opp["id"], "INSUFFICIENT_EVIDENCE",
                      f"same_problem={same_problem}", indep, len(sources),
                      same_problem, guard)
    if max_conf < 0.4 and top_rev == "unknown":
        return _store(db_path, opp["id"], "INSUFFICIENT_EVIDENCE",
                      f"max_conf={max_conf}, revenue={top_rev}",
                      indep, len(sources), same_problem, guard)
    authors = {m.get("author") for m in members if m.get("author")}
    if n == 1 or indep <= 1:
        state = "REPEATED_SAME_AUTHOR" if (n > 1 and len(authors) <= 1) else "SINGLE_OBSERVATION"
        return _store(db_path, opp["id"], state,
                      f"n={n}, independent={indep}, authors={sorted(authors)}",
                      indep, len(sources), same_problem, guard)
    multi = len(sources) >= 2
    state = "CROSS_SOURCE_DEMAND" if (indep >= 2 and multi) else "INDEPENDENT_DEMAND"
    # VALIDATED upgrade: cross/independent + revenue + clear problem + feasible + gap signal
    seed_text = (seed.get("normalized_text") or seed.get("problem") or "")
    has_gap = bool((opp.get("gap_analysis") or "").strip())
    cx = DB.connect(db_path)
    try:
        nsol = cx.execute("SELECT COUNT(*) c FROM solutions WHERE opportunity_id=?",
                          (opp["id"],)).fetchone()["c"]
    finally:
        cx.close()
    if (state in ("CROSS_SOURCE_DEMAND", "INDEPENDENT_DEMAND")
            and top_rev in ("high", "medium") and len(seed_text) >= 60
            and (opp.get("ai_feasibility") or "") in FEASIBLE and (has_gap or nsol > 0)):
        state = "VALIDATED_OPPORTUNITY"
        reason = (f"independent={indep} across {len(sources)} sources, revenue={top_rev}, "
                  f"feasible, gap={'yes' if has_gap else f'{nsol} solutions'}")
    else:
        reason = (f"independent={indep}, sources={len(sources)}, revenue={top_rev}, "
                  f"gap={'yes' if has_gap else 'no'}")
    return _store(db_path, opp["id"], state, reason, indep, len(sources), same_problem, guard)


def _store(db_path, opp_id, state, reason, indep, nsrc, same_problem, guard):
    cx = DB.connect(db_path)
    try:
        cx.execute("UPDATE opportunities SET validation_state=?, validation_reason=?,"
                   " independent_evidence_count=?, independent_source_count=?,"
                   " same_problem_count=?, cross_domain_guard=?, updated_at=? WHERE id=?",
                   (state, reason[:1000], indep, nsrc, same_problem,
                    json.dumps(guard, ensure_ascii=False), DB.now_iso(), opp_id))
        cx.commit()
    finally:
        cx.close()
    return {"opportunity_id": opp_id, "validation_state": state, "reason": reason,
            "independent": indep, "sources": nsrc, "same_problem": same_problem,
            "guard": guard}


def revalidate_all(db_path):
    cx = DB.connect(db_path)
    try:
        opps = [dict(r) for r in cx.execute("SELECT * FROM opportunities")]
    finally:
        cx.close()
    return [validate_opportunity(db_path, o) for o in opps]


def evidence_search(db_path, cfg, raw_id, threshold=None):
    """Find independent evidence for ONE request across all sources.

    Only real rows; guard must not be flagged; similarity >= threshold;
    same author excluded. Returns matches (nothing invented)."""
    th = cfg.get("cluster_threshold", 0.72) if threshold is None else threshold
    cx = DB.connect(db_path)
    try:
        me = cx.execute("SELECT n.*, r.source, r.author, r.source_url FROM normalized n "
                        "JOIN raw_requests r ON r.id=n.raw_id WHERE n.raw_id=?", (raw_id,)).fetchone()
        if not me:
            return []
        me = dict(me)
        others = [dict(r) for r in cx.execute(
            "SELECT n.id, n.raw_id, n.normalized_text, n.request_type, r.source, r.author,"
            " r.source_url FROM normalized n JOIN raw_requests r ON r.id=n.raw_id "
            "WHERE n.raw_id != ?", (raw_id,))]
    finally:
        cx.close()
    mv, _ = SEM.get_embedding(cfg, db_path, me["id"], me["normalized_text"])
    out = []
    for o in others:
        if o.get("author") and me.get("author") and o["author"] == me["author"]:
            continue  # same author is repetition, not independent evidence
        g = DOM.pair_guard(me.get("normalized_text") or "", me.get("request_type") or "",
                           o.get("normalized_text") or "", o.get("request_type") or "")
        if g["verdict"] == "flagged":
            continue
        ov, _ = SEM.get_embedding(cfg, db_path, o["id"], o["normalized_text"])
        s = SEM.similarity(cfg, db_path, me["id"], me["normalized_text"],
                           o["id"], o["normalized_text"], mv, ov)
        if s >= th:
            out.append({"normalized_id": o["id"], "raw_id": o["raw_id"],
                        "source": o["source"], "author": o["author"],
                        "source_url": o["source_url"], "similarity": round(s, 3),
                        "guard": g["verdict"]})
    return sorted(out, key=lambda x: -x["similarity"])[:5]


def attach_cross_evidence(db_path, opp_id, matches):
    """Persist cross-evidence links (dedupe by (opp, request)). Returns count added."""
    cx = DB.connect(db_path)
    try:
        cx.execute("DELETE FROM opportunity_evidence WHERE opportunity_id=? "
                   "AND evidence_type='cross-evidence'", (opp_id,))
        added = 0
        for m in matches[:10]:
            cx.execute("INSERT INTO opportunity_evidence(opportunity_id,request_id,evidence_type,"
                       "evidence_text,source_url,observed_at) VALUES(?,?,?,?,?,?)",
                       (opp_id, m["raw_id"], "cross-evidence",
                        f"guard={m['guard']} sim={m['similarity']} author={m.get('author')}",
                        m.get("source_url"), DB.now_iso()))
            added += 1
        cx.commit()
    finally:
        cx.close()
    return added
