# docs/PHASE_2.md — Arabic Demand + Revenue Signal + Lead Intelligence

Phase 2 extends Phase 1 without replacing it. Pipeline is now:

SOURCE → COLLECT → RAW → NORMALIZE → LANG → REQUEST DETECTION → **REVENUE INTENT**
→ EXTRACTION → DEDUP → SEMANTIC → CLUSTER → **DEMAND SIGNALS** → FEASIBILITY →
SOLUTIONS → GAP → **COMMERCIAL ANALYSIS** → SCORE → **LEADS** → REVIEW → SPEC.

New modules: `revenue.py` (intent), `demand.py` (signals), `leads.py` (public contact +
draft brief), `opp_types.py` (taxonomy), `commercial.py` (analysis). Extended:
`scoring.py` (11 explainable components), `pipeline.py` (LLM routing + usage tracking),
`sources/base.py` (metadata/health/next_run), `dashboard.py` (5 new routes + evidence
detail), `cli.py` (doctor Phase 2 checks + `backfill`), `db.py` (6 tables + 19 columns,
idempotent migration, zero data loss).

Key constraints honored: LLM budget default 4/cycle (local Qwen ~1 tok/s); rules carry
bulk; `contact_manually` added as feedback decision (no autonomous outreach anywhere);
every commercial field labeled OBSERVED / INFERRED / UNKNOWN.

See: REVENUE_SIGNAL_ENGINE.md, DEMAND_ENGINE.md, ARABIC_SOURCES.md, LEAD_INTELLIGENCE.md,
COMMERCIAL_ANALYSIS.md, PHASE_2_VALIDATION.md.
