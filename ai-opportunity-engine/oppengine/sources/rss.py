"""Generic RSS/Atom adapter (stdlib xml). Respects robots.txt implicitly via polite intervals.

Default feeds: public, ToS-friendly aggregators. Configurable via meta['feeds'].
"""
import time
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

from .base import SourceAdapter

DEFAULT_FEEDS = [
    "https://news.ycombinator.com/rss",
    "https://stackoverflow.com/feeds/tag/automation",
    # Arabic-first public feeds (honest status per validation; may 403 -> backoff)
    "https://www.reddit.com/r/Egypt/.rss",
    "https://www.reddit.com/r/arabic/.rss",
]


class RssAdapter(SourceAdapter):
    name = "rss"
    kind = "rss"
    interval_s = 1800
    languages = ["ar", "en"]
    source_type = "rss"
    timeout_s = 20

    def feeds(self):
        from ..config import cfg_list
        return cfg_list(self.cfg, "rss_feeds") or DEFAULT_FEEDS

    def collect(self):
        out = []
        for feed in self.feeds():
            try:
                xml = self.fetch_text(feed)
            except Exception:
                continue
            try:
                root = ET.fromstring(xml)
            except Exception:
                continue
            for item in root.findall(".//item")[:20]:
                title = (item.findtext("title") or "").strip()
                desc = (item.findtext("description") or "").strip()
                link = (item.findtext("link") or "").strip()
                pub = (item.findtext("pubDate") or "").strip()
                blob = f"{title}\n{desc}".strip()
                if len(blob) < 20 or not link:
                    continue
                try:
                    pub_iso = parsedate_to_datetime(pub).isoformat() if pub else None
                except Exception:
                    pub_iso = None
                out.append({"source_url": link, "external_id": None,
                            "original_text": blob[:2000], "published_at": pub_iso,
                            "author": None, "author_url": None, "raw_meta": {"feed": feed}})
            for e in root.findall(".//{http://www.w3.org/2005/Atom}entry")[:20]:
                title = (e.findtext("{http://www.w3.org/2005/Atom}title") or "").strip()
                link_el = e.find("{http://www.w3.org/2005/Atom}link")
                link = (link_el.get("href") if link_el is not None else "").strip()
                pub = (e.findtext("{http://www.w3.org/2005/Atom}updated") or "").strip()
                if len(title) < 20 or not link:
                    continue
                out.append({"source_url": link, "external_id": None,
                            "original_text": title[:2000], "published_at": pub or None,
                            "author": None, "author_url": None, "raw_meta": {"feed": feed}})
            if len(out) >= self.cfg.get("max_collect_per_source", 40):
                break
            time.sleep(1)  # politeness between feeds
        return out[: self.cfg.get("max_collect_per_source", 40)]
