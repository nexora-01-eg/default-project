# docs/COMMERCIAL_ANALYSIS.md

`oppengine/commercial.py` + `oppengine/opp_types.py` + extended `oppengine/scoring.py`.

Opportunity types (multi-tag): AI automation/content/video/audio/transcription/
translation/document-processing/customer-support/lead-processing/research/data-extraction/
developer-tooling/workflow/integration/local-business-solution/productivity, custom AI
software, non-AI automation, not suitable. Rule tags in `opp_types.py`, stored JSON.

Commercial row per opportunity: revenue_intent (max member level), demand_strength,
urgency, buyer_context (business/unknown), competition_level (from solution count),
solution_gap (identified/partial/unknown), local_buildability, estimated_complexity
(requirements + feasibility heuristic), evidence_confidence (mean member confidence) —
each with OBSERVED/INFERRED/UNKNOWN provenance in `commercial_analysis.provenance`.

Score (weights sum 1.0): demand .20, freshness .12, growth .10, feasibility .10,
**revenue .15**, urgency .08, gap .07, competition .05, local .05, ease .03,
confidence .05, ± feedback. Dashboard shows all components. Service ideas per type
(one-time build, setup, automation service, maintenance, tool, API integration,
micro-SaaS, productized service) with pricing UNKNOWN unless source-backed.
Language: "commercial signal / evidence / potential / confidence" — never guarantees.
