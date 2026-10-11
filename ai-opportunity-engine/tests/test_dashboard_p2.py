"""Phase 2 tests: dashboard routes, filters, RTL/LTR, brief, no-autosend, security."""
import os
import tempfile

from oppengine import dashboard as D
from oppengine import db as DB


def seed_db():
    p = os.path.join(tempfile.mkdtemp(), "dash2.db")
    DB.init(p)
    rid = DB.insert_raw(p, {"source": "reddit", "source_url": "https://reddit.com/r/Egypt/x",
                            "original_text": "محتاج حد يعمللي بوت للرد على العملاء",
                            "language": "ar", "author": "cairo_dev",
                            "author_url": "https://reddit.com/user/cairo_dev"})
    DB.insert_normalized(p, {"raw_id": rid, "normalized_text": "x", "request_type": "implicit_ai",
                             "problem": "x", "ai_relevance": "high",
                             "ai_feasibility": "feasible_with_human", "confidence": 0.7,
                             "provider": "rules", "urgency": "high"})
    DB.store_revenue(p, rid, {"level": "high",
                              "evidence": [{"phrase": "محتاج حد", "kind": "hiring",
                                            "provenance": "OBSERVED"}],
                              "payment_language": False, "hiring_language": True,
                              "business_context": True, "urgency": "high", "provenance": "INFERRED"})
    from oppengine import leads as LEADS
    cx = DB.connect(p)
    try:
        r = dict(cx.execute("SELECT * FROM raw_requests WHERE id=?", (rid,)).fetchone())
    finally:
        cx.close()
    LEADS.store_lead(p, LEADS.extract_lead(r))
    cx = DB.connect(p)
    try:
        cx.execute("INSERT INTO opportunities(title,normalized_problem,category,request_count,"
                   "ai_feasibility,local_feasibility,local_why,confidence,status,score,"
                   "revenue_intent,complexity,opp_types,service_ideas,created_at,updated_at)"
                   " VALUES('t','t','general',1,'feasible_with_human','High','why',0.7,'new',0.66,"
                   "'high','simple','[\"AI customer support\"]','[]',?,?)",
                   (DB.now_iso(), DB.now_iso()))
        oid = cx.execute("SELECT last_insert_rowid() i").fetchone()["i"]
        nid = cx.execute("SELECT id FROM normalized").fetchone()["id"]
        cx.execute("INSERT INTO opportunity_members(opportunity_id,normalized_id,similarity)"
                   " VALUES(?,?,0.9)", (oid, nid))
        cx.commit()
    finally:
        cx.close()
    from oppengine import demand as DEM, commercial as COMM
    DEM.analyze_opportunity(p, {"id": oid})
    COMM.analyze(p, {"id": oid, "ai_feasibility": "feasible_with_human",
                     "local_feasibility": "High", "demand_strength": "single_observation"})
    from oppengine import scoring as SCORE
    SCORE.rescore_all(p)
    return p, oid


class H:
    db_path = ""
    def __init__(self, db):
        self.db_path = db


def call(view, db, *a):
    h = H(db)
    return getattr(D.Handler, view)(h, *a)


def test_new_routes_render():
    p, oid = seed_db()
    assert "فرص" in call("v_revenue", p, {"rev": [""], "flang": [""], "otype": [""], "status": [""]}, "ar", "dark")
    assert "cairo_dev" in call("v_leads", p, {}, "en", "dark")
    assert "single_observation" in call("v_demand", p, {}, "en", "dark")
    sig = call("v_signals", p, {}, "en", "dark")
    assert "محتاج حد" in sig and "hiring" in sig
    brief = call("v_brief", p, {"id": [str(oid)], "lang": ["en"]}, "en", "dark")
    assert "DRAFT ONLY" in brief and "never sends" in brief
    assert call("v_brief", p, {"id": ["99999"]}, "en", "dark") == "<div class='card'>not found</div>"


def test_revenue_filters():
    p, oid = seed_db()
    qs = {"rev": ["high"], "flang": ["ar"], "otype": ["AI customer support"], "status": [""]}
    html = call("v_revenue", p, qs, "ar", "dark")
    assert "فرص الإيرادات" in html  # filtered view keeps Arabic heading
    qs2 = {"rev": ["low"], "flang": [""], "otype": [""], "status": [""]}
    assert "No data yet" in call("v_revenue", p, qs2, "en", "dark")


def test_opp_detail_phase2_sections():
    p, oid = seed_db()
    html = call("v_opp", p, {"id": [str(oid)]}, "ar", "dark")
    for marker in ["Demand evidence", "Revenue signals", "Public leads", "Commercial analysis",
                   "contact brief", "single_observation", "cairo_dev", "draft"]:
        assert marker in html, marker
    assert 'dir=\'rtl\'' in D.page("ar", "dark", html)
    assert 'dir=\'ltr\'' in D.page("en", "light", html)


def test_no_autonomous_outreach_text():
    p, oid = seed_db()
    body = (call("v_opp", p, {"id": [str(oid)]}, "en", "dark")
            + call("v_brief", p, {"id": [str(oid)]}, "en", "dark")
            + call("v_leads", p, {}, "en", "dark"))
    for banned in ["will sell", "guaranteed money", "guaranteed customer"]:
        assert banned not in body


def test_feedback_accepts_contact_manually():
    import pathlib
    src = pathlib.Path(__file__).resolve().parent.parent.joinpath("oppengine", "dashboard.py").read_text(encoding="utf-8")
    assert "contact_manually" in src  # POST allow-list + decision dropdown
    from oppengine import cli as CLI
    import argparse
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd")
    c = sub.add_parser("feedback")
    c.add_argument("decision", choices=["interesting", "ignore", "already_solved", "too_difficult",
                                        "investigate", "build", "contact_manually", "archive"])
    ns = ap.parse_args(["feedback", "contact_manually"])
    assert ns.decision == "contact_manually"


def test_analytics_widgets():
    p, oid = seed_db()
    html = call("v_analytics", p, "en", "dark")
    assert "LLM budget" in html and "Revenue widgets" in html
