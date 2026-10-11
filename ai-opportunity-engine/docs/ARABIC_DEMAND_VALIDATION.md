# docs/ARABIC_DEMAND_VALIDATION.md — real-data report (2026-09-23, live)

No synthetic Arabic data. Zeros reported as zero. Dubious clusters flagged, not celebrated.

## Validation sequence (mostaql)

PROBE (read-only collect, 10/10 Arabic) → PROBE_OK → SCHEDULED RUN
(`collect --source mostaql`: 10 collected, 10 analyzed, 0 dup, 1 new opp) →
SECOND RUN (last_success backdated): 10 duplicates, 0 new, row count unchanged → DEDUP OK.
github_ar: PROBE 29 items (23 Arabic) → SCHEDULED RUN (29 collected/analyzed, 3 new opps).

## Totals

- Arabic requests: **29** (mostaql 10, github_ar 19; 10 English github_ar rows honestly kept as en).
- By dialect: msa 23, egyptian 6 (multi-signal rule; single shared words never decide alone).
- By region: Egypt 1, Saudi Arabia 2, Unknown 26 (explicit-only; dialect never infers region).
- Commercial intent (AR): high 11, low 10, unknown 8, medium 0.
- Evidence kinds (AR): payment 15, business 11, automation 9, service_request/hiring/
  software_request/price_request/urgent_need/repeated_manual_work 2 each, plus singles.
- Leads (AR): high 3, medium 16, low 10 (public only; phones redacted, never stored).

## Opportunities from Arabic intake

- #3 (design hiring, 2 INDEPENDENT authors فهد ش./Dareen T., high intent, weak, 0.70) —
  genuine independent buyer pair, still thin (2 observations).
- #4 (score 0.72, "moderate") — ⚠ SPURIOUS cross-domain match: a book-translation
  Mostaql project clustered with an unrelated Arabic GitHub issue by embedding
  similarity. The "moderate" label is mechanically correct (2 authors, 2 sources) but
  semantically unvalidated. Do NOT treat as repeated demand. Follow-up: Arabic
  cluster-threshold tuning / cross-language guard.
- #6 (AI-engineer hiring + WP site, SAME author ×2) — correctly single_observation;
  same-author repetition not counted as independent. Score 0.70 reflects intent, not market.
- #5 English/low — not Arabic demand.

## INDEPENDENT BUYER SIGNALS (verified)

Exactly **one** independent pair (opp #3, design hiring, 2 distinct buyers, 2 project
URLs, budgets on source pages). Everything else is single_observation. Zero buyer-grade
validated markets. That is the honest result: acquisition works, demand depth does not
yet exist in the data.

## Phase 3.5 addendum (live cycle 2026-09-23)

- Arabic requests: 29 → **43** (RSS r/Egypt feed ingesting: 14 social-chatter rows;
  Reddit JSON still 403, RSS works — different surface, honestly reported).
- The 14 new rows are social venting (محتوى اجتماعي/ترفيهي), queued behind the 60/cycle
  analyze cap — expected verdict: not_commercial/unknown, zero buyer signal so far.
- High-intent AR stays 11; cross-evidence sweep attached 4–5 real links, invented none.
- New opps #7–#9 (EN): #7 CROSS_SOURCE_DEMAND (news duplication, revenue unknown —
  correctly excluded from FIRST-MONEY), #8/#9 REPEATED_SAME_AUTHOR.
- FIRST-MONEY view live: shows only high/medium-intent, feasible, evidenced, public-URL
  candidates; opp #4 SPURIOUS excluded; singles carry SINGLE_OBSERVATION badges.

## Source ledger (unchanged)

mostaql LIVE (robots allow /projects + /project/*; 2s politeness; ≤10 details/run).
github_ar LIVE (official API, 2 Arabic queries, 2h interval). reddit BLOCKED (403 ×9).
hsoub_io CANDIDATE (readable, unstructured). nafezly CANDIDATE (path unknown).
khamsat NOT_SUPPORTED (supply-side). telegram_ar CONFIG_REQUIRED.
