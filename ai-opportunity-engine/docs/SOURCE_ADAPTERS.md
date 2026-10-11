# SOURCE_ADAPTERS.md

Interface (`sources/base.py`): `collect()` yields raw dicts; `due()` checks interval/backoff;
`safe_collect()` never raises (errors → `mark_source(ok=False)` → exponential backoff).

| Source | Kind | Interval | Status |
|---|---|---|---|
| hackernews (Firebase API, no key) | api | 30 min | ✅ live |
| github (issues search, unauth quota) | api | 60 min | ✅ live (graceful on 403/429) |
| stackexchange (no-key quota) | api | 60 min | ✅ live |
| rss (HN + public feeds, stdlib xml) | rss | 30 min | ✅ live |
| reddit (public .json) | api | 120 min | ⚠️ experimental (429-prone, backoff covers) |
| x / facebook / youtube / tiktok / instagram / discord / freelance_marketplaces / telegram | stub | — | ❌ documented reason each; telegram interface ready pending channel opt-in |

Rules: respect rate limits + polite sleeps; no CAPTCHA/auth bypass; SSRF-guarded URLs;
1s sleep between RSS feeds. Add a source: subclass `SourceAdapter`, set name/kind/interval,
register in `sources/registry.py` — no other file changes needed.
