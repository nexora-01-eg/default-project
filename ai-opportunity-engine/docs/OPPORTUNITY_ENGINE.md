# OPPORTUNITY_ENGINE.md

An Opportunity = evidence-weighted cluster, not a mention count.

**Dedup:** `source_url` UNIQUE at storage; semantic grouping via embeddings (Nomic, cached)
blended 0.7 cosine + 0.3 Jaccard, fallback pure Jaccard. Thresholds configurable
(`cluster_threshold` 0.60, calibrated on live nomic vectors 2026-09-22: genuinely related
pairs score 0.53-0.61). Members shown with counts, unique sources, time distribution,
links, public contacts.

**Score:** `0.30·demand(log) + 0.20·freshness(1/(1+age/3d)) + 0.15·growth(48h share) +
0.15·feasibility + 0.10·severity(urgency) + 0.10·commercial(intent hints)`,
+0.05 per positive feedback, −0.15 per reject (cap 2). No invented revenue — commercial
is a keyword signal, surfaced as evidence.

**Learning (real, no fake ML):** feedback table drives score adjustments; repeated requests
grow demand; rejected clusters are excluded from lists; embeddings cache + scoring breakdown
in `evidence` give a future ranker clean labels. Custom model training explicitly deferred.

**Human control:** interesting / ignore / already_solved / too_difficult / investigate /
build / archive — via dashboard form, CLI, or API. AI never auto-marks "build".
