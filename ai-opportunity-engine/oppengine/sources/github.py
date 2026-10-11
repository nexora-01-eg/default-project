"""GitHub: public search for help-wanted / request-style issues (unauth, rate-limited).

Uses the issues search endpoint; conservative query set, graceful on 403/429.
"""
import datetime
import urllib.parse

from .base import SourceAdapter

QUERIES = ["label:\"help wanted\" sort:updated-desc", "\"looking for\" tool sort:updated-desc",
           "AI request sort:updated-desc"]


class GithubAdapter(SourceAdapter):
    name = "github"
    kind = "api"
    interval_s = 3600
    languages = ["en"]
    source_type = "api"
    timeout_s = 20
    QUERIES = QUERIES

    def collect(self):
        out, seen = [], set()
        for q in (self.QUERIES or QUERIES):
            url = ("https://api.github.com/search/issues?q=" + urllib.parse.quote_plus(q) +
                   "&sort=updated&order=desc&per_page=15")
            try:
                data = self.fetch_json(url, headers={"Accept": "application/vnd.github+json"})
            except Exception:
                continue  # rate limit / network: backoff handled by caller via mark_source
            for it in (data.get("items") or []):
                u = it.get("html_url")
                if not u or u in seen:
                    continue
                seen.add(u)
                blob = f"{it.get('title','')}\n{(it.get('body') or '')[:1500]}".strip()
                if len(blob) < 20:
                    continue
                out.append({"source_url": u, "external_id": f"gh-{it.get('id')}",
                            "original_text": blob[:2000], "published_at": it.get("updated_at"),
                            "author": (it.get("user") or {}).get("login"),
                            "author_url": (it.get("user") or {}).get("html_url"),
                            "raw_meta": {"repo": u.split('/')[3] + '/' + u.split('/')[4] if u.count('/') >= 4 else "",
                                         "comments": it.get("comments"), "state": it.get("state")}})
                if len(out) >= self.cfg.get("max_collect_per_source", 40):
                    return out
        return out
