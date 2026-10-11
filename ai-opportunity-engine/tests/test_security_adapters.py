from oppengine.security import (esc, sanitize_text, scan_for_secrets,
                                  validate_public_url)
from oppengine.sources import registry as REG
from oppengine.sources.stubs import XAdapter


def test_ssrf_blocks_private():
    for u in ["http://192.168.1.1/x", "http://10.0.0.5/", "http://127.0.0.1:11434/",
              "file:///etc/passwd", "ftp://example.com/x", "http://user:pass@example.com/"]:
        ok, _ = validate_public_url(u)
        assert not ok, u


def test_public_url_ok():
    ok, _ = validate_public_url("https://api.github.com/search/repositories?q=x")
    assert ok


def test_lmstudio_local_allowlisted():
    ok, reason = validate_public_url("http://localhost:1234/v1/models",
                                     allow_local_lmstudio=True)
    assert ok


def test_redaction():
    assert "REDACTED" in __import__("oppengine.security", fromlist=["redact_secrets"]
                                    ).redact_secrets("api_key=abcdef12345")


def test_scan():
    assert scan_for_secrets("password=hunter2hunter") != []
    assert scan_for_secrets("hello world, nothing here") == []
    assert scan_for_secrets("Flask-SQLAlchemy 3.1.1") == []  # no false positive
    assert scan_for_secrets("sk-abc123XYZ45678901234567890EXTRA") != []


def test_sanitize_and_escape():
    assert "\x00" not in sanitize_text("a\x00b")
    assert esc("<script>alert(1)</script>") == "&lt;script&gt;alert(1)&lt;/script&gt;"


def test_registry_lists_live_and_stubs():
    cfg = {"http_user_agent": "t", "max_collect_per_source": 5}
    live, stubs = REG.all_adapters(cfg)
    assert len(live) == 7 and len(stubs) == 8
    assert {a.name for a in live} >= {"mostaql", "github_ar", "github", "hackernews"}
    assert all(hasattr(a, "collect") and hasattr(a, "due") for a in live + stubs)


def test_stub_returns_empty_but_healthy():
    import os, tempfile
    from oppengine import db as DB
    p = os.path.join(tempfile.mkdtemp(), "stub.db")
    DB.init(p)
    DB.upsert_source(p, "x", "stub", 86400)
    assert XAdapter({"http_user_agent": "t"}).safe_collect(p) == []
