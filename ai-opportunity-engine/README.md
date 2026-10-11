# AI Opportunity Engine — Phase 3.5: validated opportunities

Revenue-first opportunity discovery: collect real public demand → analyze with local AI →
cluster → score → dashboard. Stdlib-only runtime, SQLite store, LM Studio backend.
Phase 3 adds: Mostaql + GitHub-Arabic LIVE sources, 7-dialect Arabic engine, explicit-only
regions, 12 buyer-evidence categories, source qualification ledger, /arabic views.
Phase 3.5 adds: cross-domain guards, validation states, FIRST-MONEY view.

## Quickstart (Windows PowerShell 5.1)

```powershell
cd ai-opportunity-engine
& "C:\Users\NOUR SOFT\AppData\Local\Programs\Python\Python311\python.exe" -m oppengine.cli doctor
& "C:\Users\NOUR SOFT\AppData\Local\Programs\Python\Python311\python.exe" -m oppengine.cli cycle
& "C:\Users\NOUR SOFT\AppData\Local\Programs\Python\Python311\python.exe" -m oppengine.cli serve
# dashboard: http://127.0.0.1:8765/?lang=ar&theme=dark
```

Requires LM Studio server on `:1234` (optional — rules fallback works offline).
Tests: `...python.exe -m pytest tests -q` (uses project pytest).

## Layout

`oppengine/` (config, db, normalize, arabic_lang, region, ai_reasoning, revenue, demand,
leads, opp_types, commercial, semantic, cluster, domains, validation, scoring, feasibility,
solutions, qualification, pipeline, cli, dashboard,
sources/*) · `tests/` · `docs/` · `data/` (sqlite, gitignored) · `logs/` (JSONL, gitignored)

See `docs/`: README, ARCHITECTURE, DATA_MODEL, SOURCE_ADAPTERS, AI_REASONING,
OPPORTUNITY_ENGINE, LOCAL_FEASIBILITY, SECURITY, TESTING, ROADMAP,
PHASE_2, REVENUE_SIGNAL_ENGINE, DEMAND_ENGINE, ARABIC_SOURCES, LEAD_INTELLIGENCE,
COMMERCIAL_ANALYSIS, PHASE_2_VALIDATION,
PHASE_3, ARABIC_SOURCE_DISCOVERY, ARABIC_LANGUAGE_ENGINE, BUYER_SIGNAL_ENGINE,
ARABIC_DEMAND_VALIDATION.
