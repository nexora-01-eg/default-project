"""Hacker News: public Firebase API (no key). Ask HN / Show HN carry real demand signals."""
import datetime

from .base import SourceAdapter

TOP = "https://hacker-news.firebaseio.com/v0/topstories.json"
ITEM = "https://hacker-news.firebaseio.com/v0/item/{}.json"
ASK_KEYWORDS = ["ask", "?", "help", "looking", "need", "recommend", "alternative", "how"]


class HackerNewsAdapter(SourceAdapter):
    name = "hackernews"
    kind = "api"
    interval_s = 1800
    languages = ["en"]
    source_type = "forum"
    timeout_s = 20

    def collect(self):
        ids = self.fetch_json(TOP)[: self.cfg.get("max_collect_per_source", 40)]
        out = []
        for i in ids:
            try:
                it = self.fetch_json(ITEM.format(int(i)))
            except Exception:
                continue
            if not it or it.get("dead") or it.get("deleted"):
                continue
            title = (it.get("title") or "").strip()
            text = (it.get("text") or "").strip()
            blob = f"{title} {text}".strip()
            if len(blob) < 20:
                continue
            ts = it.get("time")
            pub = None
            if ts:
                try:
                    pub = datetime.datetime.fromtimestamp(int(ts),
                          tz=datetime.timezone.utc).isoformat()
                except Exception:
                    pass
            out.append({"source_url": f"https://news.ycombinator.com/item?id={it.get('id')}",
                        "external_id": f"hn-{it.get('id')}", "original_text": blob[:2000],
                        "published_at": pub, "author": it.get("by"),
                        "author_url": f"https://news.ycombinator.com/user?id={it.get('by')}" if it.get("by") else None,
                        "raw_meta": {"score": it.get("score"), "descendants": it.get("descendants"),
                                     "type": it.get("type")}})
        return out
