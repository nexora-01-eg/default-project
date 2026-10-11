import os
import tempfile

from oppengine import db as DB


def tmpdb():
    d = tempfile.mkdtemp(prefix="oppdb_")
    return os.path.join(d, "t.db")


def test_init_and_insert_raw():
    p = tmpdb()
    DB.init(p)
    rid = DB.insert_raw(p, {"source": "test", "source_url": "https://example.com/1",
                            "original_text": "hello", "language": "en"})
    assert rid
    dup = DB.insert_raw(p, {"source": "test", "source_url": "https://example.com/1",
                            "original_text": "hello again", "language": "en"})
    assert dup is None  # UNIQUE source_url -> dedup at storage
    assert DB.stats(p)["raw_requests"] == 1


def test_normalized_flow():
    p = tmpdb()
    DB.init(p)
    rid = DB.insert_raw(p, {"source": "t", "source_url": "https://example.com/2",
                            "original_text": "need subtitles", "language": "en"})
    assert len(DB.fetch_unanalyzed(p)) == 1
    nid = DB.insert_normalized(p, {"raw_id": rid, "normalized_text": "need subtitles",
                                   "request_type": "implicit_ai", "ai_relevance": "high",
                                   "ai_feasibility": "feasible_with_local_tools", "confidence": 0.7,
                                   "provider": "rules"})
    assert nid
    assert DB.fetch_unanalyzed(p) == []


def test_source_backoff():
    p = tmpdb()
    DB.init(p)
    DB.upsert_source(p, "s1", "api", 3600)
    DB.mark_source(p, "s1", False)
    DB.mark_source(p, "s1", False)
    s = DB.stats(p)["sources"][0]
    assert s["consecutive_errors"] == 2 and s["backoff_until"]
    DB.mark_source(p, "s1", True)
    assert DB.stats(p)["sources"][0]["consecutive_errors"] == 0
