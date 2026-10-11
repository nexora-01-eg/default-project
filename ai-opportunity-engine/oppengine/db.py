"""SQLite store. One connection per operation (WAL mode); parameterized queries only."""
import datetime
import json
import os
import sqlite3

SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS sources(
  name TEXT PRIMARY KEY, kind TEXT, status TEXT DEFAULT 'active',
  interval_s INTEGER DEFAULT 3600, last_attempt TEXT, last_success TEXT,
  consecutive_errors INTEGER DEFAULT 0, backoff_until TEXT, meta TEXT DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS raw_requests(
  id INTEGER PRIMARY KEY AUTOINCREMENT, source TEXT, source_url TEXT UNIQUE,
  external_id TEXT, collected_at TEXT, published_at TEXT, original_text TEXT,
  language TEXT, author TEXT, author_url TEXT, raw_meta TEXT DEFAULT '{}',
  rejected_reason TEXT
);
CREATE INDEX IF NOT EXISTS idx_raw_source ON raw_requests(source);
CREATE INDEX IF NOT EXISTS idx_raw_collected ON raw_requests(collected_at);
CREATE TABLE IF NOT EXISTS normalized(
  id INTEGER PRIMARY KEY AUTOINCREMENT, raw_id INTEGER UNIQUE REFERENCES raw_requests(id),
  normalized_text TEXT, request_type TEXT, problem TEXT, desired_result TEXT,
  requirements TEXT DEFAULT '[]', constraints TEXT DEFAULT '[]', urgency TEXT,
  ai_relevance TEXT, ai_feasibility TEXT, confidence REAL,
  provider TEXT, reasoning TEXT, cluster_id INTEGER, created_at TEXT
);
CREATE TABLE IF NOT EXISTS opportunities(
  id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, normalized_problem TEXT,
  category TEXT, request_count INTEGER DEFAULT 0, unique_sources INTEGER DEFAULT 0,
  freshness_score REAL DEFAULT 0, growth_score REAL DEFAULT 0, ai_feasibility TEXT,
  competition_note TEXT, gap_analysis TEXT, suggested_solution TEXT,
  local_feasibility TEXT, local_why TEXT, confidence REAL,
  status TEXT DEFAULT 'new', score REAL DEFAULT 0, evidence TEXT DEFAULT '{}',
  created_at TEXT, updated_at TEXT
);
CREATE TABLE IF NOT EXISTS opportunity_members(
  opportunity_id INTEGER REFERENCES opportunities(id), normalized_id INTEGER UNIQUE REFERENCES normalized(id),
  similarity REAL, PRIMARY KEY(opportunity_id, normalized_id)
);
CREATE TABLE IF NOT EXISTS solutions(
  id INTEGER PRIMARY KEY AUTOINCREMENT, opportunity_id INTEGER REFERENCES opportunities(id),
  name TEXT, url TEXT, capabilities TEXT, limitations TEXT, pricing TEXT,
  complaints TEXT, gap TEXT, source TEXT
);
CREATE TABLE IF NOT EXISTS feedback(
  id INTEGER PRIMARY KEY AUTOINCREMENT, opportunity_id INTEGER REFERENCES opportunities(id),
  decision TEXT, reason TEXT, created_at TEXT
);
CREATE TABLE IF NOT EXISTS embeddings(
  normalized_id INTEGER PRIMARY KEY REFERENCES normalized(id),
  model TEXT, vector TEXT, dim INTEGER
);
CREATE TABLE IF NOT EXISTS runs(
  id INTEGER PRIMARY KEY AUTOINCREMENT, started_at TEXT, finished_at TEXT,
  source TEXT, collected INTEGER DEFAULT 0, rejected INTEGER DEFAULT 0,
  analyzed INTEGER DEFAULT 0, ai_failures INTEGER DEFAULT 0, duplicates INTEGER DEFAULT 0,
  opportunities_new INTEGER DEFAULT 0, opportunities_updated INTEGER DEFAULT 0,
  duration_s REAL DEFAULT 0, error TEXT
);
"""


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def connect(db_path):
    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    cx = sqlite3.connect(db_path)
    cx.row_factory = sqlite3.Row
    cx.execute("PRAGMA journal_mode=WAL;")
    return cx


def init(db_path):
    cx = connect(db_path)
    try:
        cx.executescript(SCHEMA)
        cx.commit()
    finally:
        cx.close()
    migrate(db_path)  # Phase 2+ additions; preserves all existing data


# Phase 2 schema additions (idempotent; ALTERs only add missing columns).
MIGRATION_TABLES = """
CREATE TABLE IF NOT EXISTS revenue_signals(
  id INTEGER PRIMARY KEY AUTOINCREMENT, request_id INTEGER UNIQUE REFERENCES raw_requests(id),
  level TEXT, evidence TEXT DEFAULT '[]', payment_language INTEGER DEFAULT 0,
  hiring_language INTEGER DEFAULT 0, business_context INTEGER DEFAULT 0,
  urgency TEXT, provenance TEXT, created_at TEXT
);
CREATE TABLE IF NOT EXISTS demand_signals(
  id INTEGER PRIMARY KEY AUTOINCREMENT, opportunity_id INTEGER UNIQUE REFERENCES opportunities(id),
  request_count INTEGER DEFAULT 0, unique_source_count INTEGER DEFAULT 0,
  unique_author_count INTEGER DEFAULT 0, independent_request_count INTEGER DEFAULT 0,
  first_seen TEXT, last_seen TEXT, growth_rate REAL DEFAULT 0, freshness REAL DEFAULT 0,
  repeated_problem_count INTEGER DEFAULT 0, evidence_summary TEXT DEFAULT '{}',
  created_at TEXT, updated_at TEXT
);
CREATE TABLE IF NOT EXISTS leads(
  id INTEGER PRIMARY KEY AUTOINCREMENT, request_id INTEGER UNIQUE REFERENCES raw_requests(id),
  opportunity_id INTEGER REFERENCES opportunities(id),
  public_username TEXT, public_profile_url TEXT, public_email TEXT, public_website TEXT,
  public_social_links TEXT DEFAULT '[]', source_url TEXT, contactability TEXT,
  contactability_reason TEXT, created_at TEXT
);
CREATE TABLE IF NOT EXISTS opportunity_evidence(
  id INTEGER PRIMARY KEY AUTOINCREMENT, opportunity_id INTEGER REFERENCES opportunities(id),
  request_id INTEGER REFERENCES raw_requests(id), evidence_type TEXT, evidence_text TEXT,
  source_url TEXT, observed_at TEXT
);
CREATE TABLE IF NOT EXISTS commercial_analysis(
  id INTEGER PRIMARY KEY AUTOINCREMENT, opportunity_id INTEGER UNIQUE REFERENCES opportunities(id),
  revenue_intent TEXT, demand_strength TEXT, urgency TEXT, buyer_context TEXT,
  competition_level TEXT, solution_gap TEXT, local_buildability TEXT,
  estimated_complexity TEXT, evidence_confidence REAL, analyzed_at TEXT,
  provenance TEXT DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS llm_usage(
  id INTEGER PRIMARY KEY AUTOINCREMENT, started_at TEXT, attempts INTEGER DEFAULT 0,
  successes INTEGER DEFAULT 0, failures INTEGER DEFAULT 0, latency_ms INTEGER DEFAULT 0,
  tokens INTEGER DEFAULT 0, provider TEXT, model TEXT
);
CREATE TABLE IF NOT EXISTS source_qualification(
  name TEXT PRIMARY KEY, url TEXT, language TEXT, category TEXT,
  public_access TEXT, robots_status TEXT, authentication_required INTEGER DEFAULT 0,
  technical_access TEXT, terms_risk TEXT, expected_signal_quality TEXT,
  polling_interval INTEGER DEFAULT 7200, status TEXT DEFAULT 'CANDIDATE',
  reason TEXT, probe_items INTEGER DEFAULT 0, probe_at TEXT, scheduled_items INTEGER DEFAULT 0,
  checked_at TEXT
);
"""

# (table, column, ddl-fragment)
MIGRATION_COLUMNS = [
    ("normalized", "revenue_level", "TEXT"),
    ("normalized", "revenue_evidence", "TEXT DEFAULT '[]'"),
    ("normalized", "dialect", "TEXT DEFAULT ''"),
    ("normalized", "lang_confidence", "REAL DEFAULT 0"),
    ("normalized", "explicit_region", "TEXT DEFAULT ''"),
    ("normalized", "region_evidence", "TEXT DEFAULT ''"),
    ("normalized", "region_confidence", "TEXT DEFAULT ''"),
    ("opportunities", "validation_state", "TEXT DEFAULT ''"),
    ("opportunities", "validation_reason", "TEXT DEFAULT ''"),
    ("opportunities", "independent_evidence_count", "INTEGER DEFAULT 0"),
    ("opportunities", "independent_source_count", "INTEGER DEFAULT 0"),
    ("opportunities", "same_problem_count", "INTEGER DEFAULT 0"),
    ("opportunities", "cross_domain_guard", "TEXT DEFAULT '{}'"),
    ("opportunities", "opp_types", "TEXT DEFAULT '[]'"),
    ("opportunities", "revenue_intent", "TEXT"),
    ("opportunities", "demand_strength", "TEXT"),
    ("opportunities", "complexity", "TEXT"),
    ("opportunities", "service_ideas", "TEXT DEFAULT '[]'"),
    ("sources", "lang_coverage", "TEXT DEFAULT '[]'"),
    ("sources", "source_type", "TEXT DEFAULT ''"),
    ("sources", "enabled", "INTEGER DEFAULT 1"),
    ("sources", "timeout_s", "INTEGER DEFAULT 20"),
    ("sources", "rate_limit_state", "TEXT DEFAULT ''"),
    ("sources", "last_error", "TEXT"),
    ("sources", "request_count", "INTEGER DEFAULT 0"),
    ("runs", "llm_attempts", "INTEGER DEFAULT 0"),
    ("runs", "llm_successes", "INTEGER DEFAULT 0"),
    ("runs", "llm_failures", "INTEGER DEFAULT 0"),
    ("runs", "llm_latency_ms", "INTEGER DEFAULT 0"),
]


def store_revenue(db_path, raw_id, rev):
    import json as _j
    cx = connect(db_path)
    try:
        cx.execute("INSERT INTO revenue_signals(request_id,level,evidence,payment_language,"
                   "hiring_language,business_context,urgency,provenance,created_at)"
                   " VALUES(?,?,?,?,?,?,?,?,?) "
                   "ON CONFLICT(request_id) DO UPDATE SET level=excluded.level,"
                   " evidence=excluded.evidence, provenance=excluded.provenance",
                   (raw_id, rev.get("level"),
                    _j.dumps(rev.get("evidence") or [], ensure_ascii=False),
                    1 if rev.get("payment_language") else 0,
                    1 if rev.get("hiring_language") else 0,
                    1 if rev.get("business_context") else 0,
                    rev.get("urgency"), rev.get("provenance"), now_iso()))
        cx.execute("UPDATE normalized SET revenue_level=?, revenue_evidence=? WHERE raw_id=?",
                   (rev.get("level"), _j.dumps(rev.get("evidence") or [], ensure_ascii=False), raw_id))
        cx.commit()
    finally:
        cx.close()


def store_linguistics(db_path, raw_id, lang_info, region_info):
    """Phase 3: persist dialect + region verdicts for an analyzed request."""
    cx = connect(db_path)
    try:
        cx.execute("UPDATE normalized SET dialect=?, lang_confidence=?, explicit_region=?,"
                   " region_evidence=?, region_confidence=? WHERE raw_id=?",
                   ((lang_info or {}).get("dialect") or "",
                    (lang_info or {}).get("confidence") or 0,
                    (region_info or {}).get("region") or "",
                    (region_info or {}).get("evidence") or "",
                    (region_info or {}).get("confidence") or "", raw_id))
        cx.commit()
    finally:
        cx.close()


def record_llm_usage(db_path, attempts, successes, failures, latency_ms, tokens, provider, model):
    cx = connect(db_path)
    try:
        cx.execute("INSERT INTO llm_usage(started_at,attempts,successes,failures,latency_ms,"
                   "tokens,provider,model) VALUES(?,?,?,?,?,?,?,?)",
                   (now_iso(), attempts, successes, failures, latency_ms, tokens, provider, model))
        cx.commit()
    finally:
        cx.close()


def migrate(db_path):
    cx = connect(db_path)
    try:
        cx.executescript(MIGRATION_TABLES)
        for table, col, ddl in MIGRATION_COLUMNS:
            cols = [r["name"] for r in cx.execute(f"PRAGMA table_info({table})")]
            if col not in cols:
                cx.execute(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}")
        cx.commit()
    finally:
        cx.close()


def insert_raw(db_path, item):
    """item: dict with source, source_url, ... Returns id or None if duplicate."""
    cx = connect(db_path)
    try:
        cur = cx.execute(
            "INSERT OR IGNORE INTO raw_requests(source,source_url,external_id,collected_at,"
            "published_at,original_text,language,author,author_url,raw_meta,rejected_reason)"
            " VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (item.get("source"), item.get("source_url"), item.get("external_id"),
             item.get("collected_at") or now_iso(), item.get("published_at"),
             item.get("original_text"), item.get("language"), item.get("author"),
             item.get("author_url"), json.dumps(item.get("raw_meta") or {}, ensure_ascii=False),
             item.get("rejected_reason")),
        )
        cx.commit()
        return cur.lastrowid or None
    finally:
        cx.close()


def fetch_unanalyzed(db_path, limit=200):
    cx = connect(db_path)
    try:
        rows = cx.execute(
            "SELECT r.* FROM raw_requests r LEFT JOIN normalized n ON n.raw_id=r.id "
            "WHERE n.id IS NULL AND (r.rejected_reason IS NULL) ORDER BY r.id LIMIT ?", (limit,)
        ).fetchall()
        return [dict(x) for x in rows]
    finally:
        cx.close()


def insert_normalized(db_path, row):
    cx = connect(db_path)
    try:
        cur = cx.execute(
            "INSERT INTO normalized(raw_id,normalized_text,request_type,problem,desired_result,"
            "requirements,constraints,urgency,ai_relevance,ai_feasibility,confidence,provider,"
            "reasoning,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (row["raw_id"], row.get("normalized_text"), row.get("request_type"), row.get("problem"),
             row.get("desired_result"), json.dumps(row.get("requirements") or [], ensure_ascii=False),
             json.dumps(row.get("constraints") or [], ensure_ascii=False), row.get("urgency"),
             row.get("ai_relevance"), row.get("ai_feasibility"), row.get("confidence"),
             row.get("provider"), row.get("reasoning"), now_iso()),
        )
        cx.commit()
        return cur.lastrowid
    finally:
        cx.close()


def upsert_source(db_path, name, kind, interval_s, meta=None, langs=None,
                  source_type="", enabled=True, timeout_s=20):
    cx = connect(db_path)
    try:
        cx.execute(
            "INSERT INTO sources(name,kind,interval_s,meta) VALUES(?,?,?,?) "
            "ON CONFLICT(name) DO UPDATE SET kind=excluded.kind, interval_s=excluded.interval_s",
            (name, kind, interval_s, json.dumps(meta or {}, ensure_ascii=False)),
        )
        # Phase 2 metadata (columns guaranteed by migrate(); ignore if running old DB)
        try:
            cx.execute("UPDATE sources SET lang_coverage=?, source_type=?, enabled=?, timeout_s=? "
                       "WHERE name=?", (json.dumps(langs or [], ensure_ascii=False),
                                        source_type, 1 if enabled else 0, timeout_s, name))
        except Exception:
            pass
        cx.commit()
    finally:
        cx.close()


def mark_source(db_path, name, ok, error=None, collected=0):
    cx = connect(db_path)
    try:
        if ok:
            cx.execute("UPDATE sources SET last_attempt=?, last_success=?, consecutive_errors=0,"
                       " backoff_until=NULL, last_error=NULL, rate_limit_state='',"
                       " request_count=request_count+? WHERE name=?",
                       (now_iso(), now_iso(), collected or 0, name))
        else:
            row = cx.execute("SELECT consecutive_errors FROM sources WHERE name=?", (name,)).fetchone()
            n = (row["consecutive_errors"] if row else 0) + 1
            backoff = min(3600 * (2 ** min(n, 4)), 43200)
            import datetime as dt
            until = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=backoff)).isoformat()
            err = str(error or "")[:500]
            rl = "RATE_LIMITED" if any(k in err.lower() for k in ("429", "rate", "limit", "quota", "403")) else "BLOCKED" if n >= 3 else "ERROR"
            try:
                cx.execute("UPDATE sources SET last_attempt=?, consecutive_errors=?,"
                           " backoff_until=?, last_error=?, rate_limit_state=? WHERE name=?",
                           (now_iso(), n, until, err, rl, name))
            except Exception:
                cx.execute("UPDATE sources SET last_attempt=?, consecutive_errors=?,"
                           " backoff_until=? WHERE name=?", (now_iso(), n, until, name))
        cx.commit()
    finally:
        cx.close()


def stats(db_path):
    cx = connect(db_path)
    try:
        out = {}
        for t in ("raw_requests", "normalized", "opportunities", "feedback", "runs"):
            out[t] = cx.execute(f"SELECT COUNT(*) c FROM {t}").fetchone()["c"]
        out["by_source"] = [dict(r) for r in cx.execute(
            "SELECT source, COUNT(*) c FROM raw_requests GROUP BY source ORDER BY c DESC")]
        out["by_lang"] = [dict(r) for r in cx.execute(
            "SELECT language, COUNT(*) c FROM raw_requests GROUP BY language ORDER BY c DESC")]
        out["by_category"] = [dict(r) for r in cx.execute(
            "SELECT category, COUNT(*) c FROM opportunities GROUP BY category ORDER BY c DESC")]
        out["sources"] = [dict(r) for r in cx.execute("SELECT * FROM sources ORDER BY name")]
        return out
    finally:
        cx.close()
