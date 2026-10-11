import os
import tempfile

from oppengine import cluster as CLU
from oppengine import db as DB
from oppengine import feasibility as FEAS
from oppengine import scoring as SCORE
from tests.fixtures import AR_REELS, AR_SHORTS, AR_TRIM

CFG = {"lmstudio_base": "http://127.0.0.1:9", "embed_model": "x",
       "cluster_threshold": 0.05, "min_requests_for_opportunity": 2}


def seed(p):
    DB.init(p)
    texts = [AR_SHORTS, AR_REELS, AR_TRIM]
    for i, t in enumerate(texts):
        rid = DB.insert_raw(p, {"source": "test", "source_url": f"https://example.com/c{i}",
                                "original_text": t, "language": "ar"})
        DB.insert_normalized(p, {"raw_id": rid, "normalized_text": t, "request_type": "implicit_ai",
                                 "problem": t, "ai_relevance": "high",
                                 "ai_feasibility": "feasible_with_local_tools",
                                 "confidence": 0.7, "provider": "rules",
                                 "reasoning": "test", "urgency": "medium"})


def test_cluster_groups_similar_keeps_raw():
    p = os.path.join(tempfile.mkdtemp(), "c.db")
    seed(p)
    new, _ = CLU.dedup_cluster(p, CFG)
    assert new == 1
    assert DB.stats(p)["raw_requests"] == 3  # raw rows never deleted
    cx = DB.connect(p)
    try:
        n = cx.execute("SELECT COUNT(*) c FROM opportunity_members").fetchone()["c"]
    finally:
        cx.close()
    assert n == 2  # offline Jaccard groups the overlapping pair; live embeddings group more


def test_non_ai_never_clustered():
    p = os.path.join(tempfile.mkdtemp(), "c2.db")
    DB.init(p)
    for i in range(3):
        rid = DB.insert_raw(p, {"source": "t", "source_url": f"https://example.com/n{i}",
                                "original_text": "plumber needed", "language": "en"})
        DB.insert_normalized(p, {"raw_id": rid, "normalized_text": "plumber needed",
                                 "request_type": "human_service", "ai_relevance": "none",
                                 "ai_feasibility": "not_ai", "confidence": 0.7, "provider": "rules"})
    assert CLU.dedup_cluster(p, CFG) == (0, 0)
    # low-relevance but not_ai feasibility must also be excluded
    rid = DB.insert_raw(p, {"source": "t", "source_url": "https://example.com/n9",
                            "original_text": "review my PR please", "language": "en"})
    DB.insert_normalized(p, {"raw_id": rid, "normalized_text": "review my PR please",
                             "request_type": "human_service", "ai_relevance": "low",
                             "ai_feasibility": "not_ai", "confidence": 0.6, "provider": "rules"})
    rid2 = DB.insert_raw(p, {"source": "t", "source_url": "https://example.com/n10",
                             "original_text": "review my PR please friend", "language": "en"})
    DB.insert_normalized(p, {"raw_id": rid2, "normalized_text": "review my PR please friend",
                             "request_type": "human_service", "ai_relevance": "low",
                             "ai_feasibility": "not_ai", "confidence": 0.6, "provider": "rules"})
    assert CLU.dedup_cluster(p, dict(CFG, cluster_threshold=0.0)) == (0, 0)


def test_scoring_and_feasibility():
    p = os.path.join(tempfile.mkdtemp(), "c3.db")
    seed(p)
    CLU.dedup_cluster(p, CFG)
    assert SCORE.rescore_all(p) == 1
    assert FEAS.refresh(p) == 1
    cx = DB.connect(p)
    try:
        o = dict(cx.execute("SELECT * FROM opportunities").fetchone())
    finally:
        cx.close()
    assert 0.0 <= o["score"] <= 1.0 and o["score"] > 0.2
    assert o["local_feasibility"] in ("High", "Medium", "Low")


def test_feasibility_word_boundaries():
    level, why = FEAS.assess("GitHub surfaces per-stage status", "")
    assert "opencv" not in why  # 'face' must not match 'surfaces'
    level2, _ = FEAS.assess("face detection in photos", "")
    assert level2 == "High" and "opencv" in FEAS.assess("face detection in photos", "")[1]
