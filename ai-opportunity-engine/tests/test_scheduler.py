"""Phase 2 tests: scheduler intervals, backoff, enabled flag, health, Arabic config."""
import os
import tempfile

from oppengine import config as CFG
from oppengine import db as DB
from oppengine.sources import registry as REG
from oppengine.sources.base import SourceAdapter
from oppengine.sources.stubs import TelegramAdapter, XAdapter


def adapters(cfg):
    live, stubs = REG.all_adapters(cfg)
    return {a.name: a for a in live + stubs}


def test_all_adapters_have_metadata():
    cfg = CFG.load("config.yaml", {"db_path": ":memory:"})
    for name, a in adapters(cfg).items():
        assert hasattr(a, "languages") and hasattr(a, "source_type")
        assert hasattr(a, "enabled") and hasattr(a, "health") and hasattr(a, "next_run_at")
        assert a.interval_s > 0


def test_intervals_differ_by_source():
    cfg = CFG.load("config.yaml", {"db_path": ":memory:"})
    ads = adapters(cfg)
    assert ads["reddit"].interval_s > ads["hackernews"].interval_s  # slow vs fast
    assert ads["telegram"].interval_s >= 86400  # daily-ish stub


def test_arabic_coverage_declared():
    cfg = CFG.load("config.yaml", {"db_path": ":memory:"})
    ads = adapters(cfg)
    assert "ar" in ads["reddit"].languages and "ar" in ads["rss"].languages
    assert "Egypt" in ads["reddit"].subs()


def test_enabled_flag_and_health():
    p = os.path.join(tempfile.mkdtemp(), "s.db")
    DB.init(p)
    cfg = dict(CFG.load("config.yaml", {"db_path": p}))
    cfg["disabled_sources"] = "reddit"
    ads = adapters(cfg)
    assert not ads["reddit"].enabled()
    assert ads["reddit"].health(p) == "disabled"
    assert ads["github"].enabled()


def test_backoff_and_next_run():
    p = os.path.join(tempfile.mkdtemp(), "s2.db")
    DB.init(p)
    cfg = CFG.load("config.yaml", {"db_path": p})
    ads = adapters(cfg)
    DB.upsert_source(p, "github", "api", 3600)
    assert ads["github"].due(p) is True  # never run -> due
    assert ads["github"].health(p) == "never_run"
    DB.mark_source(p, "github", True, collected=3)
    assert ads["github"].due(p) is False  # just succeeded -> not due
    assert ads["github"].health(p) == "active"
    assert ads["github"].next_run_at(p)  # scheduled in future
    DB.mark_source(p, "github", False, error="HTTP 429 rate limited")
    cx = DB.connect(p)
    try:
        r = dict(cx.execute("SELECT rate_limit_state, last_error FROM sources WHERE name='github'").fetchone())
    finally:
        cx.close()
    assert r["rate_limit_state"] == "RATE_LIMITED"
    assert "429" in (r["last_error"] or "")


def test_stub_honest_statuses():
    assert XAdapter({}).support_status == "NOT_SUPPORTED"
    assert TelegramAdapter({}).support_status == "CONFIG_REQUIRED"


def test_per_source_timeout():
    cfg = CFG.load("config.yaml", {"db_path": ":memory:"})
    a = adapters(cfg)["hackernews"]
    assert a.timeout() == 20
    assert a.max_response_bytes >= 1_000_000


def test_mark_source_counts_requests():
    p = os.path.join(tempfile.mkdtemp(), "s3.db")
    DB.init(p)
    DB.upsert_source(p, "rss", "rss", 1800)
    DB.mark_source(p, "rss", True, collected=5)
    cx = DB.connect(p)
    try:
        assert cx.execute("SELECT request_count FROM sources WHERE name='rss'").fetchone()[0] == 5
    finally:
        cx.close()
