"""StackExchange: public /questions API (no key, quota-limited). Tech help demand."""
import datetime
import urllib.parse

from .base import SourceAdapter

API = ("https://api.stackexchange.com/2.3/questions?order=desc&sort=activity&tagged={tag}"
       "&site=stackoverflow&pagesize=20")


class StackExchangeAdapter(SourceAdapter):
    name = "stackexchange"
    kind = "api"
    interval_s = 3600
    languages = ["en"]
    source_type = "forum"
    timeout_s = 20
    tags = ["automation", "nlp", "machine-learning", "openai-api", "chatbot"]

    def collect(self):
        out, errors = [], []
        for tag in self.tags:
            try:
                data = self.fetch_json(API.format(tag=urllib.parse.quote(tag)))
            except Exception as exc:
                errors.append(f"{tag}: {str(exc)[:120]}")
                continue
            if "error_id" in data:
                errors.append(f"{tag}: API {data.get('error_name')}")
                continue
            for it in (data.get("items") or []):
                blob = f"{it.get('title','')}\n".strip()
                if len(blob) < 20:
                    continue
                owner = it.get("owner") or {}
                out.append({"source_url": it.get("link"), "external_id": f"se-{it.get('question_id')}",
                            "original_text": blob[:2000],
                            "published_at": datetime.datetime.fromtimestamp(
                                it.get("creation_date", 0), tz=datetime.timezone.utc).isoformat() if it.get("creation_date") else None,
                            "author": owner.get("display_name"), "author_url": owner.get("link"),
                            "raw_meta": {"tags": it.get("tags"), "score": it.get("score"),
                                         "answer_count": it.get("answer_count"), "tag": tag}})
                if len(out) >= self.cfg.get("max_collect_per_source", 40):
                    return out
        if not out and errors:
            raise RuntimeError("all tags failed: " + "; ".join(errors)[:300])
        return out
