# THRESHOLD ANALYSIS (Phase 11)

Sweep: 0.60 / 0.70 / 0.80 / 0.90. **No winner is declared** — the table only.
Higher threshold = fewer auto-decisions, fewer wrong auto-decisions. Pick per
project after your own review of the disagreement lists in the shadow log.

## Opportunity filter (161 real rows; reference = existing pipeline rule)

| Threshold | Coverage (auto) | Agreement | FP (kept, ref drops) | FN (dropped, ref keeps) | FNR |
|---|---|---|---|---|---|
| 0.60 | 18.6% | 93.2% | 6 | 5 | 3.2% |
| 0.70 | 13.7% | 93.8% | 6 | 4 | 2.6% |
| 0.80 | 4.4% | 96.3% | 6 | **0** | **0%** |
| 0.90 | 0% | 96.3% | 6 | 0 | 0% |

FP=6 is constant: 6 rows the pipeline filtered are never auto-dropped, only
reviewed (fail-open). FPR vs reference is degenerate (tn=0) for the same
reason — reported for completeness, not as a quality signal.

## News triage (161 rows; reference = `ai_relevance` proxy, weak label)

| Threshold | Coverage | Agreement | FN (dropped, ref keeps) |
|---|---|---|---|
| 0.60 | 20.5% | 45.3% | 5 (FNR 7.4%) |
| 0.70 | 13.0% | 45.3% | **0** |
| 0.80 | 1.9% | 44.1% | 0 |
| 0.90 | 0% | 42.2% | 0 |

## Orchestrator routing (30 real tasks)

Top-1 agreement 56.7% at every threshold (threshold only changes keep vs
review, not top-1). Coverage: 20% → 6.7% → 0% → 0%. Zero high-confidence
disagreements at all thresholds: when confident, it matches history.

## Labeled dataset (78; accuracy independent of threshold)

Accuracy 93.6% throughout; coverage 47% → 31% → 18% → 4%. Calibration holds:
100% correct when confident (≥0.8).

## Cost simulation (counts only — "estimated reduction in LLM invocations", no money claims)

| Threshold | Filtered / total | Reduction | Of LLM-worthy (155) |
|---|---|---|---|
| 0.60 | 20 / 322 | **6.2%** | 5 (3.2%) |
| 0.70 | 9 / 322 | 2.8% | 4 (2.6%) |
| 0.80 | 3 / 322 | 0.9% | 0 (0%) |
| 0.90 | 0 | 0% | 0 |

Read with the FN column: at 0.60, ~6% fewer invocations at the price of 5
LLM-worthy items needing human rescue (they surface as drops for review, not
silent deletes — raw rows stay in DB). At 0.80 the rescue queue is empty and
so is most of the saving. This is the trade, stated plainly.
