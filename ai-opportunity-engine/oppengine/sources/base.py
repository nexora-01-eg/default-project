"""Source adapter interface: politeness (interval/backoff/health) built in."""
import datetime
import json
import urllib.request

from ..logging_utils import log
from ..security import sanitize_text, validate_public_url


class SourceAdapter:
    name = "base"
    kind = "api"
    interval_s = 3600
    max_items = 40
    # Phase 2 metadata
    languages = ["en"]       # ISO codes covered, e.g. ["ar", "en"]
    source_type = "api"      # api | rss | forum | marketplace | social | chat
    timeout_s = None         # None -> cfg http_timeout_s
    max_response_bytes = 2_000_000

    def __init__(self, cfg):
        self.cfg = cfg

    def enabled(self):
        from ..config import cfg_list
        return self.name not in cfg_list(self.cfg, "disabled_sources")

    def timeout(self):
        return self.timeout_s or self.cfg.get("http_timeout_s", 20)

    # -- politeness ------------------------------------------------------
    def due(self, db_path):
        from .. import db as DB
        cx = DB.connect(db_path)
        try:
            row = cx.execute("SELECT last_success, backoff_until FROM sources WHERE name=?",
                             (self.name,)).fetchone()
        finally:
            cx.close()
        now = datetime.datetime.now(datetime.timezone.utc)
        if row and row["backoff_until"]:
            try:
                if datetime.datetime.fromisoformat(row["backoff_until"]) > now:
                    return False
            except Exception:
                pass
        if row and row["last_success"]:
            try:
                last = datetime.datetime.fromisoformat(row["last_success"])
                if (now - last).total_seconds() < self.interval_s:
                    return False
            except Exception:
                pass
        return True

    def next_run_at(self, db_path):
        """ISO timestamp of next scheduled attempt, or None if due now/unknown."""
        from .. import db as DB
        cx = DB.connect(db_path)
        try:
            row = cx.execute("SELECT last_success, backoff_until, interval_s FROM sources WHERE name=?",
                             (self.name,)).fetchone()
        finally:
            cx.close()
        now = datetime.datetime.now(datetime.timezone.utc)
        if row and row["backoff_until"]:
            try:
                b = datetime.datetime.fromisoformat(row["backoff_until"])
                if b > now:
                    return b.isoformat()
            except Exception:
                pass
        if row and row["last_success"]:
            try:
                nxt = (datetime.datetime.fromisoformat(row["last_success"])
                       + datetime.timedelta(seconds=row["interval_s"] or self.interval_s))
                return nxt.isoformat() if nxt > now else None
            except Exception:
                return None
        return None

    def health(self, db_path):
        """active | backoff | rate_limited | blocked | disabled | never_run."""
        if not self.enabled():
            return "disabled"
        from .. import db as DB
        cx = DB.connect(db_path)
        try:
            row = cx.execute("SELECT last_success, backoff_until, consecutive_errors,"
                             " rate_limit_state FROM sources WHERE name=?", (self.name,)).fetchone()
        finally:
            cx.close()
        if not row:
            return "never_run"
        d = dict(row)
        if d.get("rate_limit_state") == "RATE_LIMITED":
            return "rate_limited"
        if (d.get("consecutive_errors") or 0) >= 3:
            return "blocked"
        if d.get("backoff_until"):
            try:
                if datetime.datetime.fromisoformat(d["backoff_until"]) > \
                        datetime.datetime.now(datetime.timezone.utc):
                    return "backoff"
            except Exception:
                pass
        return "active" if d.get("last_success") else "never_run"

    # -- fetching (timeout + max-size guarded) -------------------------------
    def _get(self, url, headers=None):
        ok, reason = validate_public_url(url)
        if not ok:
            raise ValueError(f"blocked url: {reason}")
        req = urllib.request.Request(url, headers={"User-Agent": self.cfg["http_user_agent"],
                                                   **(headers or {})})
        with urllib.request.urlopen(req, timeout=self.timeout()) as r:
            return r.read(self.max_response_bytes + 1)

    def fetch_json(self, url, headers=None):
        raw = self._get(url, headers)
        if len(raw) > self.max_response_bytes:
            raise ValueError("response too large")
        return json.loads(raw.decode("utf-8", "replace"))

    def fetch_text(self, url):
        raw = self._get(url)
        if len(raw) > self.max_response_bytes:
            raise ValueError("response too large")
        return raw.decode("utf-8", "replace")

    def collect(self):
        """Yield raw item dicts: source_url*, original_text*, published_at, author, ..."""
        raise NotImplementedError

    def safe_collect(self, db_path):
        from .. import db as DB
        items = []
        try:
            for it in self.collect():
                it = dict(it)
                it["source"] = self.name
                it["original_text"] = sanitize_text(it.get("original_text", ""))[:2000]
                if not it.get("source_url") or not it["original_text"]:
                    continue
                items.append(it)
            DB.mark_source(db_path, self.name, True, collected=len(items))
            log("collect", self.name, output={"collected": len(items)})
        except Exception as exc:  # failure handling: record, backoff, continue
            DB.mark_source(db_path, self.name, False, error=exc)
            log("collect", self.name, status="error", output={"error": str(exc)[:300]})
            items = []
        return items
