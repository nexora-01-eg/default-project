# docs/DEMAND_ENGINE.md

`oppengine/demand.py` — evidence-backed demand, never manufactured.

Per opportunity: request_count, unique_source_count, unique_author_count,
**independent_request_count** (distinct non-null authors + one group per distinct URL
among anonymous rows — same-author repeats never inflate demand), first/last_seen,
growth_48h_share, freshness, strength (`strong` ≥5 indep & ≥2 sources; `moderate` ≥3 or
2+multi-source; `weak` ≥2; else `single_observation`).
Single request → `demand_evidence = "single_observation"` explicitly.
Stored in `demand_signals` (+ `opportunities.demand_strength`). Dashboard: /demand table.
