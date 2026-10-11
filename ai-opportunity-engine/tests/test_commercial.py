"""Phase 2 tests: opportunity types, commercial analysis, migration safety, scoring."""
import json
import os
import tempfile

from oppengine import commercial as COMM
from oppengine import db as DB
from oppengine import demand as DEM
from oppengine import opp_types as OT
from oppengine import scoring as SCORE


def seed(p=None):
    p = p or os.path.join(tempfile.mkdtemp(), "c2.db")
    DB.init(p)
    texts = [("https://example.com/a1", "عاوز برنامج يحول الفيديو العربي إلى subtitles", "ali"),
             ("https://example.com/a2", "محتاج أداة تطلع ترجمة من الفيديوهات", "mona")]
    for url, t, a in texts:
        rid = DB.insert_raw(p, {"source": "t", "source_url": url, "original_text": t,
                                "language": "ar", "author": a})
        DB.insert_normalized(p, {"raw_id": rid, "normalized_text": t, "request_type": "implicit_ai",
                                 "problem": t, "ai_relevance": "high",
                                 "ai_feasibility": "feasible_with_local_tools",
                                 "confidence": 0.7, "provider": "rules", "urgency": "medium"})
        DB.store_revenue(p, rid, {"level": "medium",
                                  "evidence": [{"phrase": "محتاج أداة", "kind": "tool_want",
                                                "provenance": "OBSERVED"}],
                                  "payment_language": False, "hiring_language": False,
                                  "business_context": False, "urgency": "medium",
                                  "provenance": "INFERRED"})
    cx = DB.connect(p)
    try:
        cx.execute("INSERT INTO opportunities(title,normalized_problem,category,request_count,"
                   "ai_feasibility,local_feasibility,confidence,status,created_at,updated_at)"
                   " VALUES('vid','vid','general',0,'feasible_with_local_tools','High',0.7,'new',?,?)",
                   (DB.now_iso(), DB.now_iso()))
        oid = cx.execute("SELECT last_insert_rowid() i").fetchone()["i"]
        for nid in cx.execute("SELECT id FROM normalized"):
            cx.execute("INSERT OR IGNORE INTO opportunity_members(opportunity_id,normalized_id,similarity)"
                       " VALUES(?,?,0.9)", (oid, nid["id"]))
        cx.commit()
        return p, oid
    finally:
        cx.close()


def test_opp_types_arabic_video():
    tags = OT.tag("عاوز برنامج يحول الفيديو العربي إلى subtitles", "feasible_with_local_tools", "high")
    assert "AI video" in tags and "AI transcription" in tags
    assert OT.tag("plumber needed", "not_ai", "none") == ["not suitable"]
    assert OT.valid(["AI video", "bogus"]) == ["AI video"]


def test_migration_preserves_phase1_data():
    p = os.path.join(tempfile.mkdtemp(), "mig.db")
    cx = DB.connect(p)
    try:
        cx.executescript(DB.SCHEMA)  # phase-1-only schema, simulate old DB
        cx.execute("INSERT INTO raw_requests(source,source_url,original_text) VALUES('t','u1','hello')")
        cx.execute("INSERT INTO opportunities(title,status) VALUES('old','new')")
        cx.commit()
    finally:
        cx.close()
    DB.init(p)  # must migrate without destroying rows
    cx = DB.connect(p)
    try:
        assert cx.execute("SELECT COUNT(*) c FROM raw_requests").fetchone()["c"] == 1
        assert cx.execute("SELECT COUNT(*) c FROM opportunities").fetchone()["c"] == 1
        for t in ("revenue_signals", "demand_signals", "leads", "opportunity_evidence",
                  "commercial_analysis", "llm_usage"):
            assert cx.execute(f"SELECT COUNT(*) c FROM {t}").fetchone()["c"] == 0
        cols = [r["name"] for r in cx.execute("PRAGMA table_info(opportunities)")]
        assert "opp_types" in cols and "revenue_intent" in cols
    finally:
        cx.close()


def test_commercial_analysis_provenance():
    p, oid = seed()
    DEM.analyze_opportunity(p, {"id": oid})
    row = COMM.analyze(p, {"id": oid, "ai_feasibility": "feasible_with_local_tools",
                           "local_feasibility": "High", "demand_strength": "weak"})
    assert row["revenue_intent"] == "medium"
    assert row["solution_gap"] == "unknown"
    assert row["buyer_context"] == "unknown"
    assert "UNKNOWN" in json.dumps(row)  # unknowns labeled, not hidden
    cx = DB.connect(p)
    try:
        o = dict(cx.execute("SELECT revenue_intent, complexity, service_ideas, opp_types"
                            " FROM opportunities WHERE id=?", (oid,)).fetchone())
    finally:
        cx.close()
    assert o["revenue_intent"] == "medium"
    assert o["complexity"] in ("trivial", "simple", "moderate")
    ideas = json.loads(o["service_ideas"])
    assert ideas and all(i["pricing"] == "UNKNOWN" for i in ideas)
    assert "AI video" in json.loads(o["opp_types"])


def test_scoring_components_explainable():
    p, oid = seed()
    DEM.analyze_opportunity(p, {"id": oid})
    COMM.analyze(p, {"id": oid, "ai_feasibility": "feasible_with_local_tools",
                     "local_feasibility": "High", "demand_strength": "weak"})
    cx = DB.connect(p)
    try:
        o = dict(cx.execute("SELECT * FROM opportunities WHERE id=?", (oid,)).fetchone())
    finally:
        cx.close()
    s, detail = SCORE.score_opportunity(p, o)
    for k in ("demand", "freshness", "growth", "feasibility", "revenue", "urgency",
              "gap", "competition", "local", "ease", "confidence"):
        assert k in detail, k
    assert abs(sum(SCORE.WEIGHTS.values()) - 1.0) < 1e-9
    assert 0.0 <= s <= 1.0 and s > 0.2
    assert detail["revenue_level"] == "medium"
    assert detail["independent"] == 2


def test_complexity_unknown_for_non_ai():
    assert COMM.estimate_complexity({"ai_feasibility": "not_ai"}, []) == "unknown"
    assert COMM.estimate_complexity({"ai_feasibility": "difficult"}, [{}, {}]) == "complex"
