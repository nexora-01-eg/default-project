"""Source qualification (Phase 3): honest, evidence-backed source lifecycle.

Statuses: CANDIDATE -> PROBE_EMPTY | PROBE_OK | ERROR ; PROBE_OK -> LIVE (only after
real items are parsed, persisted with URLs + verified language, via scheduled run).
Terminal honest states: BLOCKED | CONFIG_REQUIRED | NOT_SUPPORTED.
robots.txt is fetched and honored before any content fetch.
"""
import urllib.request
from urllib.parse import urlparse

from . import db as DB

STATUSES = ("CANDIDATE", "PROBE_OK", "PROBE_EMPTY", "LIVE", "BLOCKED",
            "CONFIG_REQUIRED", "NOT_SUPPORTED", "ERROR")


def check_robots(page_url, timeout=20):
    """Return (robots_status, note). allowed | restricted | unknown | unparseable.

    restricted = site disallows the exact path we need (we then do NOT fetch it).
    """
    try:
        p = urlparse(page_url)
        root = f"{p.scheme}://{p.netloc}/robots.txt"
        req = urllib.request.Request(root, headers={"User-Agent": "AIOpportunityEngine/0.3 (qualification check)"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read(100_000).decode("utf-8", "replace")
    except Exception as exc:
        return "unknown", f"robots.txt unreachable: {str(exc)[:120]}"
    disallows = []
    in_wildcard, grouped = False, False
    for line in body.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        low = s.lower()
        if low.startswith("user-agent:"):
            ua = s.split(":", 1)[1].strip()
            in_wildcard = ua in ("*",)
            grouped = True
        elif low.startswith("disallow:") and (in_wildcard or not grouped):
            path = s.split(":", 1)[1].strip()
            if path:
                disallows.append(path)
    path = p.path or "/"
    for d in disallows:
        if d == "/" or (d != "" and path.startswith(d)):
            return "restricted", f"robots.txt disallows '{d}' for our path '{path}'"
    note = f"{len(disallows)} disallow rule(s), none cover '{path}'" if disallows else "no disallow rules"
    return "allowed", note


def qualify(db_path, name, url, language, category, public_access, authentication_required,
            technical_access, terms_risk, expected_signal_quality, polling_interval,
            status="CANDIDATE", reason=""):
    """Insert/update a qualification row. Returns the stored row."""
    DB.init(db_path)
    cx = DB.connect(db_path)
    try:
        robots_status, robots_note = check_robots(url)
        cx.execute("INSERT INTO source_qualification(name,url,language,category,public_access,"
                   "robots_status,authentication_required,technical_access,terms_risk,"
                   "expected_signal_quality,polling_interval,status,reason,checked_at)"
                   " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
                   "ON CONFLICT(name) DO UPDATE SET url=excluded.url, language=excluded.language,"
                   " category=excluded.category, public_access=excluded.public_access,"
                   " robots_status=excluded.robots_status,"
                   " authentication_required=excluded.authentication_required,"
                   " technical_access=excluded.technical_access, terms_risk=excluded.terms_risk,"
                   " expected_signal_quality=excluded.expected_signal_quality,"
                   " polling_interval=excluded.polling_interval, status=excluded.status,"
                   " reason=excluded.reason, checked_at=excluded.checked_at",
                   (name, url, language, category, public_access, robots_status,
                    1 if authentication_required else 0, technical_access, terms_risk,
                    expected_signal_quality, polling_interval, status,
                    (reason + f" | robots: {robots_note}" if reason else f"robots: {robots_note}"),
                    DB.now_iso()))
        cx.commit()
        return dict(cx.execute("SELECT * FROM source_qualification WHERE name=?", (name,)).fetchone())
    finally:
        cx.close()


def record_probe(db_path, name, items, error=""):
    """Read-only probe outcome (no persistence of items). Returns new status."""
    status = "ERROR" if error else ("PROBE_OK" if items > 0 else "PROBE_EMPTY")
    cx = DB.connect(db_path)
    try:
        cx.execute("UPDATE source_qualification SET status=?, probe_items=?, probe_at=? WHERE name=?",
                   (status, items, DB.now_iso(), name))
        cx.commit()
    finally:
        cx.close()
    return status


def record_scheduled(db_path, name, new_items):
    """Scheduled run persisted items -> LIVE (only with real persisted rows)."""
    if new_items <= 0:
        return None
    cx = DB.connect(db_path)
    try:
        cx.execute("UPDATE source_qualification SET status='LIVE', scheduled_items=scheduled_items+? "
                   "WHERE name=?", (new_items, name))
        cx.commit()
    finally:
        cx.close()
    return "LIVE"


def all_rows(db_path):
    cx = DB.connect(db_path)
    try:
        return [dict(r) for r in cx.execute("SELECT * FROM source_qualification ORDER BY name")]
    finally:
        cx.close()
