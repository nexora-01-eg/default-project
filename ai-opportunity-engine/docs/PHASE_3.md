# docs/PHASE_3.md — Arabic Demand Acquisition & Buyer Signal Validation

Objective (sole): acquire REAL public Arabic demand. No new UI chrome beyond what
serves Arabic evidence; no training; no outreach; no payments.

Added: `arabic_lang.py` (7-way dialect + Arabizi + mixed, ≥2-signal rule),
`region.py` (explicit-only gazetteer, عمان ambiguity rule), `qualification.py`
(CANDIDATE→PROBE_OK/PROBE_EMPTY/ERROR→LIVE + BLOCKED/CONFIG_REQUIRED/NOT_SUPPORTED,
live robots.txt checks), `sources/mostaql.py` (marketplace HTML+JSON-LD parsing,
2s politeness, open-only), `sources/github_ar.py` (Arabic issue search, quota-safe),
DB columns (dialect/lang_confidence/explicit_region/region_evidence/region_confidence)
+ `source_qualification` table, pipeline language/dialect/region wiring, demand
repetition quality keys, `/arabic` + `/arabic-sources` dashboard views,
SINGLE_OBSERVATION pills, `arabic-backfill` + `qualify` CLI commands.

Result: 29 real Arabic requests from 2 LIVE sources; acquisition proven, demand depth
not yet (1 independent buyer pair). See ARABIC_DEMAND_VALIDATION.md for the honest ledger.
