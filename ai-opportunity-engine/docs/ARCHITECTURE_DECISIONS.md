# ARCHITECTURE_DECISIONS.md — AI Opportunity Engine MVP

All decisions derive from `LOCAL_ENVIRONMENT_AUDIT.md`. Principle: use what the machine
already has; install nothing for the MVP runtime.

| # | Decision | Why (evidence) | Rejected alternative |
|---|---|---|---|
| 1 | Stdlib-only Python 3.11 runtime (`urllib`, `sqlite3`, `http.server`, `difflib`) | Real interpreter at `Python311\python.exe`; no new pip installs; bare `python` is a Store shim so docs pin the full path | Flask/FastAPI + requests + sklearn (unneeded weight; system Flask exists but adds deployment surface) |
| 2 | SQLite (stdlib, v3.45.1) as the only store | Zero-server, file-backed, covers MVP scale (thousands of rows); full traceability raw→opportunity | Postgres/Redis/Elastic/vector DB — none installed, all overkill for MVP |
| 3 | LM Studio `qwen2.5-coder-7b-instruct` via `POST /v1/chat/completions` for AI reasoning | Verified loaded + smoke-tested; free/local; AR/EN capable; no auth | Cloud APIs (cost + keys), Gemma-4 (download incomplete), training a custom model (explicitly out of scope) |
| 4 | LM Studio `text-embedding-nomic-embed-text-v1.5` for semantic similarity, token-Jaccard fallback | Verified working; free/local; fallback keeps pipeline alive when server is down | sklearn/Torch embeddings (not installed), massive vector infra (scope-banned) |
| 5 | Deterministic rules + structured AI analysis + historical signals for learning | Spec forbids fake ML; feedback table + scoring weights give a real основание for a future ranker | Custom model training (banned for MVP) |
| 6 | Initial live sources: Hacker News API, GitHub Search, StackExchange API, generic RSS | Public, no-key, ToS-compatible, reachable with stdlib; each with own interval/backoff/health | Reddit/Facebook/X/YouTube/TikTok scraping or auth-walled APIs (rate-limit/CAPTCHA/ToS risk → stub adapters with honest status) |
| 7 | 10-min pipeline cycle; per-source intervals longer (30–120 min) + backoff | Spec demands freshness without hammering; HN/GitHub unauth quotas require politeness | Hitting every source every 10 min (quota burn + bans) |
| 8 | Dashboard on stdlib `http.server`, server-rendered HTML, AR/EN + RTL/LTR + dark/light | Zero deps; works offline; single-file templates per view; no build step | React/Next.js (Node exists but adds toolchain for a local intelligence UI) |
| 9 | New code isolated in `ai-opportunity-engine/` | Working dir hosts an unrelated video project — must not be touched | Mixing into existing `engine/` package (collision + contamination risk) |
| 10 | `opportunity_spec.json` export only (no auto-build) | Spec requires future-ready boundary, not auto-launch | Auto-invoking OpenCode per opportunity (banned for MVP) |
| 11 | No browser automation, no accounts, no payments, no mobile | Explicit scope limits + nothing installed (no Playwright/Selenium) | — (deferred to Phases 5–7) |
| 12 | Security: URL allow-list validation, SSRF guard (no private-range fetching), secret redaction, arg-list subprocesses (none in MVP path), input sanitization, HTML escaping | Dashboard renders untrusted public text; adapters fetch remote URLs | Rendering raw text unescaped / fetching arbitrary user URLs server-side |

Data flow: `SOURCE → COLLECT → RAW → NORMALIZE → LANG → AI-DETECT → EXTRACT →
DEDUP → SEMANTIC → CLUSTER → FEASIBILITY → SOLUTIONS → GAP → SCORE → DASHBOARD`
implemented in `oppengine/pipeline.py` with one SQLite transaction per stage batch
and a `runs` log row per cycle (observability).
