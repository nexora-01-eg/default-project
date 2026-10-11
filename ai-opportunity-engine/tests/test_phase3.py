"""Phase 3 integration: pipeline linguistics, demand quality keys, dashboard AR views."""
import os
import tempfile

from oppengine import dashboard as D
from oppengine import db as DB
from oppengine import demand as DEM


def seed_ar(p):
    DB.init(p)
    rids = []
    data = [("https://mostaql.com/project/1-x", "السلام عليكم احتاج اصمم داتا بيس، ارجو توضيح السعر", "شهد"),
            ("https://mostaql.com/project/2-x", "مطلوب مصمم في جدة لمشروع سريع", "شهد"),
            ("https://github.com/x/y/issues/3", "Looking for a developer, budget $300", None)]
    for url, t, a in data:
        rid = DB.insert_raw(p, {"source": "mostaql", "source_url": url, "original_text": t,
                                "language": "ar", "author": a})
        rids.append(rid)
        DB.insert_normalized(p, {"raw_id": rid, "normalized_text": t, "request_type": "implicit_ai",
                                 "problem": t, "ai_relevance": "high",
                                 "ai_feasibility": "feasible_with_local_tools",
                                 "confidence": 0.7, "provider": "rules", "urgency": "medium"})
    from oppengine import arabic_lang as ARL
    from oppengine import region as RG
    cx = DB.connect(p)
    try:
        raws = [dict(r) for r in cx.execute("SELECT * FROM raw_requests")]
    finally:
        cx.close()
    for r in raws:
        DB.store_linguistics(p, r["id"], ARL.analyze(r["original_text"] or ""),
                             RG.detect_region(r["original_text"] or ""))
    cx = DB.connect(p)
    try:
        cx.execute("INSERT INTO opportunities(title,request_count,status,created_at,updated_at)"
                   " VALUES('t',0,'new',?,?)", (DB.now_iso(), DB.now_iso()))
        oid = cx.execute("SELECT last_insert_rowid() i").fetchone()["i"]
        for nid in cx.execute("SELECT id FROM normalized"):
            cx.execute("INSERT OR IGNORE INTO opportunity_members(opportunity_id,normalized_id,similarity)"
                       " VALUES(?,?,0.9)", (oid, nid["id"]))
        cx.commit()
    finally:
        cx.close()
    return p, oid


class H:
    def __init__(self, db):
        self.db_path = db


def test_demand_quality_keys():
    p = os.path.join(tempfile.mkdtemp(), "q3.db")
    _, oid = seed_ar(p)
    s = DEM.analyze_opportunity(p, {"id": oid})
    assert "same_author_repeats" in s and "cross_source_repetition" in s
    assert s["same_author_repeats"] == 1  # شهد twice
    assert s["cross_source_repetition"] is False  # single source here


def test_cross_source_flag():
    p = os.path.join(tempfile.mkdtemp(), "q4.db")
    DB.init(p)
    for i, src in enumerate(("mostaql", "github_ar")):
        rid = DB.insert_raw(p, {"source": src, "source_url": f"https://x/{i}",
                                "original_text": "محتاج حد يعمل برنامج", "language": "ar",
                                "author": f"u{i}"})
        DB.insert_normalized(p, {"raw_id": rid, "normalized_text": "x", "confidence": 0.7,
                                 "provider": "rules"})
    cx = DB.connect(p)
    try:
        cx.execute("INSERT INTO opportunities(title,status,created_at,updated_at)"
                   " VALUES('t','new',?,?)", (DB.now_iso(), DB.now_iso()))
        oid = cx.execute("SELECT last_insert_rowid() i").fetchone()["i"]
        for nid in cx.execute("SELECT id FROM normalized"):
            cx.execute("INSERT INTO opportunity_members(opportunity_id,normalized_id,similarity)"
                       " VALUES(?,?,0.9)", (oid, nid["id"]))
        cx.commit()
    finally:
        cx.close()
    s = DEM.analyze_opportunity(p, {"id": oid})
    assert s["cross_source_repetition"] is True


def test_arabic_dashboard_views():
    p = os.path.join(tempfile.mkdtemp(), "q5.db")
    _, oid = seed_ar(p)
    h = H(p)
    ar = D.Handler.v_arabic(h, {"dialect": [""], "region": [""], "intent": [""], "source": [""]},
                            "ar", "dark")
    assert "الطلب العربي" in ar and "جدة" in ar or "Saudi Arabia" in ar
    assert "mostaql" in ar
    f = D.Handler.v_arabic(h, {"dialect": ["msa"], "region": [""], "intent": [""], "source": [""]},
                           "ar", "dark")
    assert "mostaql" in f
    src = D.Handler.v_arabic_sources(h, "ar", "dark")
    assert "المصادر العربية" in src  # empty table state is honest
    opp = D.Handler.v_opp(h, {"id": [str(oid)]}, "ar", "dark")
    assert "اللهجة" in opp and "مصر" not in opp  # no region invented for these rows


def test_pipeline_stores_linguistics(monkeypatch):
    import oppengine.pipeline as PIPE
    from oppengine.sources import registry as REG
    p = os.path.join(tempfile.mkdtemp(), "q6.db")

    class FakeAR:
        name = "fake_ar"
        kind = "test"
        interval_s = 0
        QUALIFY = None

        def __init__(self, cfg):
            pass

        def enabled(self):
            return True

        def due(self, db):
            return True

        def safe_collect(self, db):
            return [{"source": "fake_ar", "source_url": "https://x/1",
                     "original_text": "عايز حد يعمللي برنامج ازاي؟ فين المبرمجين؟"}]

    monkeypatch.setattr(REG, "all_adapters", lambda c: ([FakeAR(c)], []))
    cfg = {"db_path": p, "lmstudio_base": "http://127.0.0.1:9", "chat_model": "x",
           "embed_model": "x", "ai_timeout_s": 2, "http_user_agent": "test",
           "http_timeout_s": 3, "max_collect_per_source": 10, "max_llm_per_cycle": 0,
           "max_analyze_per_cycle": 10, "cluster_threshold": 0.99,
           "min_requests_for_opportunity": 2, "cycle_seconds": 600}
    DB.init(p)
    run = PIPE.collect_cycle(p, cfg)
    assert run["collected"] == 1 and run["error"] is None
    cx = DB.connect(p)
    try:
        n = dict(cx.execute("SELECT dialect, lang_confidence, language FROM normalized n "
                            "JOIN raw_requests r ON r.id=n.raw_id").fetchone())
    finally:
        cx.close()
    assert n["dialect"] == "egyptian"
    assert n["language"] == "ar"
