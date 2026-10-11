# docs/ARABIC_SOURCE_DISCOVERY.md — how sources were found and judged

Method: fetch robots.txt, fetch a real page, check login walls, assess demand shape.

| Candidate | URL pattern | Robots | Access | Verdict |
|---|---|---|---|---|
| Mostaql open projects | mostaql.com/projects, /project/{id}-* | allows (only /search*, /ajax/ banned) | full HTML+JSON-LD, no login | LIVE |
| GitHub Arabic issues | api.github.com/search/issues (AR queries) | official API | JSON, unauth quota | LIVE |
| Hsoub I/O | io.hsoub.com | no disallows | readable, essay/discussion mix | CANDIDATE (low structure) |
| Nafezly | nafezly.com (/jobs 404) | allows | listing path unknown | CANDIDATE (needs research) |
| Khamsat | khamsat.com | allows | readable | NOT_SUPPORTED (supply-side offers) |
| Reddit r/Egypt, r/arabic, r/Arabs | .json/.rss | n/a | HTTP 403 ×9 | BLOCKED |
| Telegram Arabic channels | t.me | n/a (no robots) | needs opt-in + API | CONFIG_REQUIRED |

Rule: a source is LIVE only after probe items + scheduled persistence + dedup check.
`cli qualify` records any candidate (robots fetched live at record time).
Dashboard: /arabic-sources shows the full ledger.
