"""Phase 3.5 tests: guards, states, reclassification, first-money filtering."""
import os
import tempfile

from oppengine import dashboard as D
from oppengine import db as DB
from oppengine import domains as DOM
from oppengine import validation as VAL


def test_cross_domain_false_positive():
    g = DOM.pair_guard("ترجمة كتاب من العربية إلى الإنجليزية باحترافية أبحث عن مترجم",
                       "implicit_ai",
                       "لماذا يزداد الاحتياج إلى رعاية المنقطعين في الحرم في الإجازات الدينية؟",
                       "implicit_ai")
    assert g["verdict"] == "flagged"
    assert any("cross-domain" in r for r in g["reasons"])
    assert "translation" in g["domains_a"] and "religious_content" in g["domains_b"]


def test_same_domain_match():
    g = DOM.pair_guard("تحديث تصاميم بوت Discord نحتاج مصمم", "implicit_ai",
                       "تصميم كتالوج لمنتجات متجر أبحث عن مصمم جرافيك", "implicit_ai")
    assert g["verdict"] == "pass"
    assert "design" in g["domains_a"] and "design" in g["domains_b"]


def test_compatible_domains_subtitles():
    g = DOM.pair_guard("need subtitles for my videos", "implicit_ai",
                       "ترجمة فيديوهات اليوتيوب", "implicit_ai")
    assert g["verdict"] == "pass"  # translation ~ video compatible


def test_secondary_overlap_never_decides():
    # design brief sharing only an incidental 'writing' signal with a book
    # translation must NOT pass on secondary overlap alone
    g = DOM.pair_guard("تصميم كتالوج منتجات أبحث عن مصمم جرافيك والكتاب المرجعي",
                       "implicit_ai",
                       "ترجمة كتاب من العربية أبحث عن مترجم محترف",
                       "implicit_ai")
    assert g["verdict"] == "flagged"
    assert any("cross-domain" in r for r in g["reasons"])


def test_request_type_family_mismatch_flagged():
    g = DOM.pair_guard("build a dashboard app", "implicit_ai",
                       "need a plumber tomorrow", "human_service")
    assert g["verdict"] == "flagged"
    assert any("family mismatch" in r for r in g["reasons"])


def test_unknown_domain_needs_high_bar():
    g = DOM.pair_guard("something vague here", "implicit_ai",
                       "another vague thing", "implicit_ai")
    assert g["verdict"] == "unknown-domain"


def test_shared_entities_recorded():
    g = DOM.pair_guard("update designs for Discord bot", "implicit_ai",
                       "Discord server icons needed", "implicit_ai")
    assert "discord" in g["entities"]


def _seed(rows):
    """rows: list of (url, text, author, source, rtype). Returns (db, opp_id)."""
    p = os.path.join(tempfile.mkdtemp(), "v.db")
    DB.init(p)
    for i, (url, t, a, src, rt) in enumerate(rows):
        rid = DB.insert_raw(p, {"source": src, "source_url": url, "original_text": t,
                                "language": "ar", "author": a})
        DB.insert_normalized(p, {"raw_id": rid, "normalized_text": t, "request_type": rt,
                                 "problem": t, "ai_relevance": "high",
                                 "ai_feasibility": "feasible_with_local_tools",
                                 "confidence": 0.7, "provider": "rules"})
        DB.store_revenue(p, rid, {"level": "high", "evidence": [], "payment_language": False,
                                  "hiring_language": True, "business_context": False,
                                  "urgency": "medium", "provenance": "x"})
    cx = DB.connect(p)
    try:
        cx.execute("INSERT INTO opportunities(title,normalized_problem,request_count,"
                   "ai_feasibility,confidence,status,score,gap_analysis,"
                   "created_at,updated_at) VALUES('t','" + "x" * 80 + "',0,"
                   "'feasible_with_human',0.7,'new',0.7,'some gap',?,?)",
                   (DB.now_iso(), DB.now_iso()))
        oid = cx.execute("SELECT last_insert_rowid() i").fetchone()["i"]
        for nid in cx.execute("SELECT id FROM normalized"):
            cx.execute("INSERT INTO opportunity_members(opportunity_id,normalized_id,similarity)"
                       " VALUES(?,?,0.9)", (oid, nid["id"]))
        cx.commit()
    finally:
        cx.close()
    return p, oid


def test_reclassify_spurious_translation_pair():
    p, oid = _seed([
        ("https://m/1", "ترجمة كتاب من العربية إلى الإنجليزية أبحث عن مترجم محترف", "A", "mostaql", "implicit_ai"),
        ("https://g/2", "لماذا يزداد الاحتياج إلى رعاية المنقطعين في الحرم في المواسم؟", "B", "github_ar", "implicit_ai"),
    ])
    r = VAL.validate_opportunity(p, {"id": oid, "ai_feasibility": "feasible_with_human"})
    assert r["validation_state"] == "SPURIOUS_MATCH"
    assert r["same_problem"] == 1
    cx = DB.connect(p)
    try:
        kept = cx.execute("SELECT COUNT(*) c FROM opportunity_members WHERE opportunity_id=?",
                          (oid,)).fetchone()["c"]
    finally:
        cx.close()
    assert kept == 2  # evidence NOT deleted


def test_independent_authors_state():
    p, oid = _seed([
        ("https://m/1", "تحديث تصاميم بوت نحتاج مصمم محترف للواجهات", "A", "mostaql", "implicit_ai"),
        ("https://m/2", "تصميم كتالوج منتجات أبحث عن مصمم جرافيك مبدع", "B", "mostaql", "implicit_ai"),
    ])
    r = VAL.validate_opportunity(p, {"id": oid, "ai_feasibility": "feasible_with_human"})
    assert r["validation_state"] == "INDEPENDENT_DEMAND"
    assert r["independent"] == 2


def test_cross_source_state():
    p, oid = _seed([
        ("https://m/1", "تحديث تصاميم بوت نحتاج مصمم محترف للواجهات", "A", "mostaql", "implicit_ai"),
        ("https://g/2", "تصميم شعار وهوية أبحث عن مصمم جرافيك مبدع", "B", "github_ar", "implicit_ai"),
    ])
    r = VAL.validate_opportunity(p, {"id": oid, "ai_feasibility": "feasible_with_human"})
    assert r["validation_state"] in ("CROSS_SOURCE_DEMAND", "VALIDATED_OPPORTUNITY")


def test_same_author_collapse_state():
    p, oid = _seed([
        ("https://g/1", "مطلوب مهندس ذكاء اصطناعي لبناء وكيل ذكي", "A", "github_ar", "explicit_ai"),
        ("https://g/2", "تصميم موقع ووردبريس احترافي للشركة", "A", "github_ar", "explicit_ai"),
    ])
    r = VAL.validate_opportunity(p, {"id": oid, "ai_feasibility": "feasible_with_local_tools"})
    assert r["validation_state"] == "REPEATED_SAME_AUTHOR"


def test_single_observation_state():
    p, oid = _seed([
        ("https://m/1", "تحديث تصاميم بوت نحتاج مصمم محترف للواجهات", "A", "mostaql", "implicit_ai"),
    ])
    r = VAL.validate_opportunity(p, {"id": oid, "ai_feasibility": "feasible_with_human"})
    assert r["validation_state"] == "SINGLE_OBSERVATION"


def test_insufficient_evidence_state():
    p = os.path.join(tempfile.mkdtemp(), "v0.db")
    DB.init(p)
    cx = DB.connect(p)
    try:
        cx.execute("INSERT INTO opportunities(title,status,created_at,updated_at)"
                   " VALUES('empty','new',?,?)", (DB.now_iso(), DB.now_iso()))
        oid = cx.execute("SELECT last_insert_rowid() i").fetchone()["i"]
        cx.commit()
    finally:
        cx.close()
    r = VAL.validate_opportunity(p, {"id": oid})
    assert r["validation_state"] == "INSUFFICIENT_EVIDENCE"


def test_firstmoney_filters_spurious_but_keeps_single():
    p = os.path.join(tempfile.mkdtemp(), "vfm.db")
    DB.init(p)
    rid = DB.insert_raw(p, {"source": "mostaql", "source_url": "https://m/9",
                            "original_text": "محتاج حد يعمل برنامج مخزن للشركة بادفع فورا",
                            "language": "ar", "author": "buyer1"})
    DB.insert_normalized(p, {"raw_id": rid, "normalized_text": "محتاج حد يعمل برنامج مخزن للشركة بادفع فورا",
                             "request_type": "implicit_ai", "problem": "x" * 80,
                             "ai_relevance": "high", "ai_feasibility": "feasible_with_local_tools",
                             "confidence": 0.8, "provider": "rules"})
    DB.store_revenue(p, rid, {"level": "high", "evidence": [], "payment_language": True,
                              "hiring_language": True, "business_context": True,
                              "urgency": "high", "provenance": "x"})
    cx = DB.connect(p)
    try:
        cx.execute("INSERT INTO opportunities(title,normalized_problem,request_count,"
                   "ai_feasibility,confidence,status,score,revenue_intent,created_at,updated_at)"
                   " VALUES('t','" + "y" * 80 + "',1,'feasible_with_local_tools',0.8,'new',0.8,"
                   "'high',?,?)", (DB.now_iso(), DB.now_iso()))
        oid = cx.execute("SELECT last_insert_rowid() i").fetchone()["i"]
        nid = cx.execute("SELECT id FROM normalized").fetchone()["id"]
        cx.execute("INSERT INTO opportunity_members(opportunity_id,normalized_id,similarity)"
                   " VALUES(?,?,0.9)", (oid, nid))
        cx.execute("INSERT INTO opportunities(title,status,validation_state,created_at,updated_at)"
                   " VALUES('spur','new','SPURIOUS_MATCH',?,?)", (DB.now_iso(), DB.now_iso()))
        cx.commit()
    finally:
        cx.close()
    VAL.validate_opportunity(p, {"id": oid, "ai_feasibility": "feasible_with_local_tools"})

    class H:
        db_path = p

    html = D.Handler.v_firstmoney(H(), {}, "en", "dark")
    assert "FIRST-MONEY" in html
    assert "spur" not in html  # spurious excluded
    assert "Investigate" in html and "contact_manually" in html
