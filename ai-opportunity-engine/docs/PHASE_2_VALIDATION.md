# docs/PHASE_2_VALIDATION.md — real-source validation (2026-09-23, live)

Method: `backfill` over 80 Phase-1 rows + 2 full `cycle` runs + read-only live probes
(no DB writes) for rss/reddit/stackexchange after fixes. No synthetic demand anywhere.

## Per-source report

| SOURCE | STATUS | ITEMS (probe/cycle) | NEW | DUP | ERROR | BACKOFF | LAST SUCCESS |
|---|---|---|---|---|---|---|---|
| github | LIVE | 40 collected | 40 | 0 | — | — | 2026-09-23 01:41 |
| hackernews | LIVE | 42 collected (40+2) | 42 | 35 | — | — | 2026-09-23 01:41 |
| stackexchange | FIXED→LIVE | 40 live (probe) | 0* | 0 | was HTTP 400 (bad `filter` param, removed) | 2h | pending next due run |
| rss | FIXED→LIVE | 36 live (probe; HN feed) | 0* | 0 | was ET iterator bug, fixed | to ~02:25 | pending next due run |
| reddit (incl. Egypt/arabic/Arabs) | BLOCKED | 0 | 0 | 0 | HTTP 403 on all 9 subs | 2h intervals | says ZERO, not success |
| x/facebook/tiktok/instagram | NOT_SUPPORTED | — | — | — | login/paid/ToS | — | never (honest stubs) |
| youtube/discord/telegram/freelance | CONFIG_REQUIRED | — | — | — | no key/channels configured | — | never (honest stubs) |

*Probe was read-only; ingestion happens on next due scheduler tick (10-min global tick,
per-source intervals respected — verified idle 2.1s cycle with zero hammering).

## Data totals

- Real requests: 122 (80 EN + 42 EN). Arabic requests: **0** — reddit AR subs 403-blocked,
  AR RSS feeds pending first due run. Reported as ZERO, not converted to success.
- Revenue signals: 122 rows (levels mostly unknown/low; 5+ med/high from EN hiring/tool-want).
- Opportunities: 2 (opp #1 new/score ~0.52/unknown intent/single_observation; opp #2
  rejected via feedback, revenue high from bounty text — kept as evidence, hidden from lists).
- Leads: 122 rows (mostly `none` contactability — HN/GitHub authors exist; contactability
  low/medium where profiles observed; phones redacted, never stored).
- LLM: 4 attempts / 0 success / 4 failures / ~308s latency — budget enforced, fallbacks honest.

## Known limitations

1. Current demand is EN dev-news/issues, not buyer demand — Arabic demand still zero.
2. Local Qwen too slow for bulk reasoning (~1 tok/s, frequent timeouts); rules carry volume.
3. SE/RSS fixes validated by probe, not yet by scheduled ingestion.
4. Reddit requires login-grade access from this network — do not retry aggressively.
