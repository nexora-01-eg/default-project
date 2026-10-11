# ARCHITECTURE.md

```
SOURCE → COLLECT → RAW STORAGE → NORMALIZE → LANGUAGE DETECTION → AI REQUEST
DETECTION → STRUCTURED EXTRACTION → DEDUPLICATION → SEMANTIC MATCHING →
OPPORTUNITY CLUSTERING → FEASIBILITY → SOLUTION DISCOVERY → GAP ANALYSIS →
OPPORTUNITY SCORE → DASHBOARD
```

## Modules (`oppengine/`)

| Module | Role |
|---|---|
| `sources/base.py` | Adapter interface: `collect()`, `due()` (interval/backoff), `safe_collect()` (never raises) |
| `sources/{hackernews,github,stackexchange,rss,reddit}.py` | Live adapters (public JSON/RSS, stdlib urllib) |
| `sources/stubs.py` | X/FB/YouTube/TikTok/IG/Telegram/Discord/marketplaces: honest `not_implemented` status |
| `db.py` | SQLite schema + parameterized access, WAL mode |
| `normalize.py` | Cleaning, AR/EN detection, request-type classification (never forced) |
| `ai_reasoning.py` | LM Studio chat → structured JSON; deterministic fallback; stores provider+confidence |
| `semantic.py` | LM Studio embeddings (cached) + token-Jaccard fallback; cosine blend |
| `cluster.py` | Threshold grouping of AI-relevant rows; raw rows never deleted |
| `scoring.py` | 0.30 demand + 0.20 freshness + 0.15 growth + 0.15 feasibility + 0.10 severity + 0.10 commercial ± feedback |
| `feasibility.py` | Audit-grounded local capability match → High/Medium + why |
| `solutions.py` | GitHub public search → capabilities/limits/pricing/gap (best effort) |
| `pipeline.py` | `collect_cycle()` per-10-min semantics + `opportunity_spec()` export |
| `dashboard.py` | stdlib http.server, AR/EN + RTL/LTR + dark/light, 9 routes |
| `cli.py` | collect/cycle/serve/doctor/spec/stats/feedback |
| `security.py` / `logging_utils.py` | Guards + JSONL observability |

## Cycle semantics

Pipeline runs every 10 min (`cycle --loop`); each source has its own longer interval
(HN 30m, GitHub/SE 60m, Reddit 120m, RSS 30m) + exponential backoff (max 12h) + health
columns. One `runs` row per cycle: collected/rejected/analyzed/ai_failures/duplicates/
opps_new/opps_updated/duration.
