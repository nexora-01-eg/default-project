"""Reddit public JSON adapter (no auth). Conservative: may 429 -> backoff handles it.

Status: EXPERIMENTAL — enabled but long interval; disabled automatically on repeated errors
via backoff. Never bypasses auth/CAPTCHA; uses only public .json endpoints.
"""
from .base import SourceAdapter

SUBS = ["artificial", "automation", "smallbusiness", "freelance", "Egypt", "arabic"]
# Arabic-first communities (public only; tested live, reported honestly)
AR_SUBS = ["Egypt", "arabic", "Arabs"]


class RedditAdapter(SourceAdapter):
    name = "reddit"
    kind = "api"
    interval_s = 7200
    languages = ["ar", "en"]
    source_type = "forum"
    timeout_s = 20

    def subs(self):
        from ..config import cfg_list
        custom = cfg_list(self.cfg, "reddit_subs")
        return custom or (SUBS + [s for s in AR_SUBS if s not in SUBS])

    def collect(self):
        out, errors = [], []
        for sub in self.subs():
            url = f"https://www.reddit.com/r/{sub}/new.json?limit=20"
            try:
                data = self.fetch_json(url)
            except Exception as exc:
                errors.append(f"{sub}: {str(exc)[:120]}")
                continue
            for ch in ((data.get("data") or {}).get("children") or []):
                d = ch.get("data") or {}
                blob = f"{d.get('title','')}\n{(d.get('selftext') or '')[:1500]}".strip()
                if len(blob) < 20:
                    continue
                out.append({"source_url": f"https://www.reddit.com{d.get('permalink','')}",
                            "external_id": f"rd-{d.get('id')}", "original_text": blob[:2000],
                            "published_at": None, "author": d.get("author"),
                            "author_url": f"https://www.reddit.com/user/{d.get('author')}" if d.get("author") else None,
                            "raw_meta": {"subreddit": sub, "score": d.get("score"),
                                         "num_comments": d.get("num_comments")}})
                if len(out) >= self.cfg.get("max_collect_per_source", 40):
                    return out
        if not out and errors:
            raise RuntimeError("all subs failed: " + "; ".join(errors)[:300])
        return out
