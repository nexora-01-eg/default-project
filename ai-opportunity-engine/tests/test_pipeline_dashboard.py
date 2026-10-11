"""Offline pipeline + dashboard tests (no network, no LM Studio)."""
import os
import tempfile

from oppengine import dashboard as D
from oppengine import db as DB
from oppengine import pipeline as PIPE
from oppengine.sources import registry as REG

CFG = {"db_path": "", "lmstudio_base": "http://127.0.0.1:9", "chat_model": "x",
       "embed_model": "x", "ai_timeout_s": 2, "http_user_agent": "test",
       "http_timeout_s": 3, "max_collect_per_source": 10,
       "cluster_threshold": 0.0, "min_requests_for_opportunity": 2}


class FakeAdapter:
    name = "fake"
    kind = "test"
    interval_s = 0
    items = [{"source_url": "https://example.com/f1",
              "original_text": "عاوز برنامج يحول الكلام في الفيديو إلى subtitles",
              "author": "user1"},
             {"source_url": "https://example.com/f2",
              "original_text": "محتاج أداة تطلع Reels من الفيديوهات الطويلة",
              "author": "user2"}]

    def __init__(self, cfg):
        pass

    def due(self, db):
        return True

    def safe_collect(self, db):
        return [{**it, "source": "fake"} for it in self.items]


def test_full_cycle_offline(monkeypatch):
    p = os.path.join(tempfile.mkdtemp(), "p.db")
    cfg = dict(CFG)
    monkeypatch.setattr(REG, "all_adapters", lambda c: ([FakeAdapter(c)], []))
    DB.init(p)
    run = PIPE.collect_cycle(p, cfg)
    assert run["collected"] == 2 and run["analyzed"] == 2 and run["error"] is None
    assert DB.stats(p)["opportunities"] >= 1
    # second run: same urls -> duplicates, no crash
    run2 = PIPE.collect_cycle(p, cfg)
    assert run2["duplicates"] == 2


def test_spec_shape(monkeypatch):
    p = os.path.join(tempfile.mkdtemp(), "p2.db")
    monkeypatch.setattr(REG, "all_adapters", lambda c: ([FakeAdapter(c)], []))
    DB.init(p)
    PIPE.collect_cycle(p, dict(CFG))
    cx = DB.connect(p)
    try:
        oid = cx.execute("SELECT id FROM opportunities LIMIT 1").fetchone()["id"]
    finally:
        cx.close()
    spec = PIPE.opportunity_spec(p, oid)
    for k in ["problem", "evidence", "requirements", "local_capabilities",
              "existing_solutions", "gap", "mvp_scope", "test_requirements"]:
        assert k in spec


def test_dashboard_pages_render():
    assert "AI Opportunity" in D.page("en", "dark", "<p>x</p>")
    assert 'dir=\'rtl\'' in D.page("ar", "dark", "<p>x</p>")
    assert 'dir=\'ltr\'' in D.page("en", "light", "<p>x</p>")
    assert D.STR["feed"]["ar"] == "التدفق المباشر"


def test_i18n_helpers():
    assert D._lang({"lang": ["ar"]}) == "ar"
    assert D._lang({"lang": ["en"]}) == "en"
    assert D._theme({"theme": ["light"]}) == "light"
