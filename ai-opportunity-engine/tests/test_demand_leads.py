"""Phase 2 tests: demand signals, independent counting, lead privacy, contact brief."""
import os
import tempfile

from oppengine import db as DB
from oppengine import demand as DEM
from oppengine import leads as LEADS


def seed_opp(authors):
    p = os.path.join(tempfile.mkdtemp(), "d.db")
    DB.init(p)
    rids = []
    for i, a in enumerate(authors):
        rid = DB.insert_raw(p, {"source": "t", "source_url": f"https://example.com/d{i}",
                                "original_text": "need subtitles for arabic videos plz",
                                "language": "ar", "author": a,
                                "author_url": f"https://example.com/u/{a}" if a else None})
        rids.append(rid)
        DB.insert_normalized(p, {"raw_id": rid, "normalized_text": "need subtitles",
                                 "request_type": "implicit_ai", "ai_relevance": "high",
                                 "ai_feasibility": "feasible_with_local_tools",
                                 "confidence": 0.7, "provider": "rules"})
    cx = DB.connect(p)
    try:
        cx.execute("INSERT INTO opportunities(title,request_count,status,created_at,updated_at)"
                   " VALUES('t',0,'new',?,?)", (DB.now_iso(), DB.now_iso()))
        oid = cx.execute("SELECT last_insert_rowid() i").fetchone()["i"]
        for nid in cx.execute("SELECT id FROM normalized"):
            cx.execute("INSERT OR IGNORE INTO opportunity_members(opportunity_id,normalized_id,similarity)"
                       " VALUES(?,?,1.0)", (oid, nid["id"]))
        cx.commit()
    finally:
        cx.close()
    return p, oid


def test_independent_count_collapses_same_author():
    assert DEM.independent_count([{"author": "a", "source_url": "u1"},
                                  {"author": "a", "source_url": "u2"},
                                  {"author": "b", "source_url": "u3"},
                                  {"author": None, "source_url": "u4"}]) == 3


def test_single_observation():
    p, oid = seed_opp(["solo"])
    s = DEM.analyze_opportunity(p, {"id": oid})
    assert s["demand_evidence"] == "single_observation"
    assert s["independent_request_count"] == 1
    assert s["strength"] == "single_observation"


def test_multi_author_demand():
    p, oid = seed_opp(["a", "a", "b", None])
    s = DEM.analyze_opportunity(p, {"id": oid})
    assert s["independent_request_count"] == 3  # a, b, +1 null-url group
    assert s["strength"] in ("moderate", "weak")
    assert s["unique_authors"] == ["a", "b"]
    assert s["provenance"].startswith("OBSERVED")


def test_lead_extraction_public_only():
    lead = LEADS.extract_lead({"id": 1, "author": "nour_dev",
                               "author_url": "https://github.com/nour_dev",
                               "source_url": "https://github.com/x/y/issues/1",
                               "original_text": "need this built, contact me at me@example.com, see https://my-site.com. Call +201001234567"})
    assert lead["public_username"] == "nour_dev"
    assert lead["public_profile_url"] == "https://github.com/nour_dev"
    assert lead["public_email"] == "me@example.com"
    assert lead["public_website"] == "https://my-site.com."
    assert lead["phone_redacted"] is True
    assert lead["contactability"] in ("high", "medium")
    assert "OBSERVED" in lead["contactability_reason"]


def test_lead_no_inference_no_contact():
    lead = LEADS.extract_lead({"id": 2, "author": None, "author_url": None,
                               "source_url": "https://news.ycombinator.com/item?id=1",
                               "original_text": "interesting discussion about compilers"})
    assert lead["contactability"] == "none"
    assert lead["public_email"] is None and lead["public_website"] is None


def test_brief_is_draft_only():
    p, oid = seed_opp(["a"])
    b = LEADS.contact_brief(p, oid, lang="en")
    assert b and "DRAFT ONLY" in b and "automatically" in b
    assert "will sell" not in b and "guaranteed" not in b
    ar = LEADS.contact_brief(p, oid, lang="ar")
    assert "مسودة فقط" in ar
    assert LEADS.contact_brief(p, 99999) is None
