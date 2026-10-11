"""Dedup + clustering. Raw rows are never deleted; members link to opportunities.

Phase 3.5: embedding similarity alone never groups rows — the cross-domain guard
(domain overlap/compatibility + request-type family) must also pass. Unknown-domain
pairs require a higher bar (high_bar) instead of the standard threshold.
"""
import datetime

from . import db as DB
from . import domains as DOM
from . import semantic as SEM

HIGH_BAR = 0.85


def _get_norms(db_path):
    cx = DB.connect(db_path)
    try:
        return [dict(r) for r in cx.execute(
            "SELECT n.*, r.source FROM normalized n JOIN raw_requests r ON r.id=n.raw_id")]
    finally:
        cx.close()


def dedup_cluster(db_path, cfg):
    """Group normalized rows with similarity >= cluster_threshold into opportunities.

    Returns (created, updated). Rows with ai_relevance 'none' are never clustered.
    """
    norms = [n for n in _get_norms(db_path)
             if (n.get("ai_relevance") or "none") != "none"
             and (n.get("ai_feasibility") or "") not in ("not_ai", "insufficient_info")
             and not n.get("cluster_id")]
    if not norms:
        return 0, 0
    # preload embeddings (best effort)
    vecs = {}
    for n in norms:
        v, _ = SEM.get_embedding(cfg, db_path, n["id"], n["normalized_text"])
        vecs[n["id"]] = v
    groups, used = [], set()
    thresh = cfg.get("cluster_threshold", 0.72)
    for i, a in enumerate(norms):
        if a["id"] in used:
            continue
        g = [a]
        used.add(a["id"])
        for b in norms[i + 1:]:
            if b["id"] in used:
                continue
            s = SEM.similarity(cfg, db_path, a["id"], a["normalized_text"],
                               b["id"], b["normalized_text"], vecs[a["id"]], vecs[b["id"]])
            if s < thresh:
                continue
            guard = DOM.pair_guard(a["normalized_text"] or "", a.get("request_type") or "",
                                   b["normalized_text"] or "", b.get("request_type") or "",
                                   high_bar=HIGH_BAR, sim=s)
            if guard["verdict"] == "flagged":
                continue  # cross-domain: embedding alone is insufficient
            if guard["verdict"] == "unknown-domain" and s < HIGH_BAR:
                continue  # no domain signals: demand a much stronger match
            g.append(b)
            used.add(b["id"])
        groups.append(g)
    created = updated = 0
    cx = DB.connect(db_path)
    try:
        for g in groups:
            if len(g) < cfg.get("min_requests_for_opportunity", 2):
                continue
            title = (g[0].get("problem") or g[0]["normalized_text"])[:160]
            sources = sorted({x.get("source", "?") for x in g})
            now = DB.now_iso()
            cur = cx.execute(
                "INSERT INTO opportunities(title,normalized_problem,category,request_count,"
                "unique_sources,ai_feasibility,confidence,status,score,evidence,created_at,updated_at)"
                " VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                (title, title, g[0].get("category") or "general", len(g), len(sources),
                 g[0].get("ai_feasibility"), g[0].get("confidence"), "new", 0.0,
                 __import__("json").dumps({"sources": sources,
                                           "request_ids": [x["id"] for x in g]}, ensure_ascii=False),
                 now, now))
            oid = cur.lastrowid
            for x in g:
                cx.execute("INSERT OR IGNORE INTO opportunity_members(opportunity_id,normalized_id,similarity)"
                           " VALUES(?,?,?)", (oid, x["id"], 1.0))
                cx.execute("UPDATE normalized SET cluster_id=? WHERE id=?", (oid, x["id"]))
            created += 1
        cx.commit()
    finally:
        cx.close()
    # refresh counts for existing opportunities touched by new members (none in MVP pass)
    return created, updated


def opportunity_age_days(created_at):
    try:
        dt = datetime.datetime.fromisoformat(created_at)
        now = datetime.datetime.now(datetime.timezone.utc)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        return max(0.0, (now - dt).total_seconds() / 86400.0)
    except Exception:
        return 0.0
