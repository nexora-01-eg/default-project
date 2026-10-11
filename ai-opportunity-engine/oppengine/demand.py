"""Demand signal engine (Phase 2): evidence-backed, never manufactured.

Single request -> demand_evidence 'single_observation'.
Same-author repeats do NOT count as independent demand.
"""
import json

from . import db as DB
from .cluster import opportunity_age_days


def _members(db_path, opp_id):
    cx = DB.connect(db_path)
    try:
        return [dict(r) for r in cx.execute(
            "SELECT n.*, r.source, r.source_url, r.author, r.collected_at, r.published_at,"
            " r.original_text FROM opportunity_members m "
            "JOIN normalized n ON n.id=m.normalized_id "
            "JOIN raw_requests r ON r.id=n.raw_id WHERE m.opportunity_id=?", (opp_id,))]
    finally:
        cx.close()


def independent_count(members):
    """Distinct non-null authors + one group per distinct URL among null-author rows."""
    authors = {m.get("author") for m in members if m.get("author")}
    null_urls = {m.get("source_url") for m in members if not m.get("author")}
    return len(authors) + len(null_urls)


def demand_strength_label(indep, sources, growth):
    if indep >= 5 and sources >= 2:
        return "strong"
    if indep >= 3 or (indep >= 2 and sources >= 2):
        return "moderate"
    if indep >= 2:
        return "weak"
    return "single_observation"


def analyze_opportunity(db_path, opp):
    members = _members(db_path, opp["id"])
    n = len(members)
    sources = sorted({m.get("source", "?") for m in members})
    authors = sorted({m.get("author") for m in members if m.get("author")})
    indep = independent_count(members)
    # Phase 3: repetition quality — same-author reposts and cross-source spread
    from collections import Counter
    per_author = Counter(m.get("author") or m.get("source_url") for m in members)
    same_author_repeats = sum(c - 1 for c in per_author.values() if c > 1)
    cross_source = len(sources) >= 2  # cross-source == cross-community repetition
    times = sorted(m.get("collected_at") or "" for m in members if m.get("collected_at"))
    ages = [opportunity_age_days(m.get("collected_at") or opp.get("created_at") or "")
            for m in members]
    recent = sum(1 for a in ages if a <= 2.0)
    growth = (recent / n) if n else 0.0
    fresh = (sum(1.0 / (1.0 + a / 3.0) for a in ages) / n) if n else 0.0
    strength = demand_strength_label(indep, len(sources), growth) if n else "single_observation"
    summary = {"demand_evidence": "single_observation" if indep <= 1 else f"{indep}_independent",
               "request_count": n, "independent_request_count": indep,
               "unique_sources": sources, "unique_authors": authors,
               "same_author_repeats": same_author_repeats,
               "cross_source_repetition": cross_source,
               "first_seen": times[0] if times else None,
               "last_seen": times[-1] if times else None,
               "growth_48h_share": round(growth, 3), "freshness": round(fresh, 3),
               "strength": strength,
               "provenance": "OBSERVED member rows; strength INFERRED from counts"}
    cx = DB.connect(db_path)
    try:
        cx.execute("INSERT INTO demand_signals(opportunity_id,request_count,unique_source_count,"
                   "unique_author_count,independent_request_count,first_seen,last_seen,growth_rate,"
                   "freshness,repeated_problem_count,evidence_summary,created_at,updated_at)"
                   " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?) "
                   "ON CONFLICT(opportunity_id) DO UPDATE SET request_count=excluded.request_count,"
                   " unique_source_count=excluded.unique_source_count,"
                   " unique_author_count=excluded.unique_author_count,"
                   " independent_request_count=excluded.independent_request_count,"
                   " first_seen=excluded.first_seen, last_seen=excluded.last_seen,"
                   " growth_rate=excluded.growth_rate, freshness=excluded.freshness,"
                   " evidence_summary=excluded.evidence_summary, updated_at=excluded.updated_at",
                   (opp["id"], n, len(sources), len(authors), indep,
                    summary["first_seen"], summary["last_seen"], growth, fresh, 0,
                    json.dumps(summary, ensure_ascii=False), DB.now_iso(), DB.now_iso()))
        cx.execute("UPDATE opportunities SET demand_strength=?, updated_at=? WHERE id=?",
                   (strength, DB.now_iso(), opp["id"]))
        cx.commit()
    finally:
        cx.close()
    return summary


def refresh_all(db_path):
    cx = DB.connect(db_path)
    try:
        opps = [dict(r) for r in cx.execute("SELECT * FROM opportunities")]
    finally:
        cx.close()
    return [analyze_opportunity(db_path, o) for o in opps]
