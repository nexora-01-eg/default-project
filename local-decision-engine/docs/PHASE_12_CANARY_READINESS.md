# PHASE 12 — CANARY READINESS

Scope: readiness verification only. Default stays SHADOW. ACTIVE never
enabled. No model downloaded, no GPU, LM Studio untouched, `OPP_DECISION_GATE`
never set, production decisions unchanged, raw data intact.

Evidence: `scripts/canary_simulator.py` → `logs/canary_sim_20260923_055025.json`
(real shadow records sampled deterministically at 1/5/10/100%);
`src/decision_engine/modes.py`; `tests/test_modes.py`. **50/50 tests pass.**

## 1. Results (per class, threshold 0.6, HIGH_CONF=0.8)

### A. Agent Routing (30 real tasks)

| pct | sampled | agree | disagree | review |
|---|---|---|---|---|
| 1% | 2 | 2 | 0 | 2 |
| 5% | 3 | 3 | 0 | 3 |
| 10% | 4 | 3 | 1 | 3 |
| 100% | 30 | 17 (56.7%) | 13 | 24 |

### B. Opportunity Classification (161 real rows)

| pct | sampled | agree | disagree | review | FP | FN | LLM avoided |
|---|---|---|---|---|---|---|---|
| 1% | 2 | 2 | 0 | 1 | 0 | 0 | 0 |
| 5% | 11 | 11 | 0 | 7 | 0 | 0 | 0 |
| 10% | 17 | 17 | 0 | 13 | 0 | 0 | 0 |
| 100% | 161 | 150 (93.2%) | 11 | 131 | 6 | 5 | 5 |

### C. News Filtering (161 rows, weak `ai_relevance` proxy)

| pct | sampled | agree | disagree | review | FP | FN | LLM avoided |
|---|---|---|---|---|---|---|---|
| 1% | 1 | 0 | 1 | 1 | 1 | 0 | 0 |
| 5% | 6 | 2 | 4 | 6 | 4 | 0 | 0 |
| 10% | 12 | 3 | 9 | 11 | 8 | 1 | 1 |
| 100% | 161 | 73 (45.3%) | 88 | 128 | 83 | 5 | 15 |

Small samples at 1/5/10% are illustrative, not statistically strong — the
100% column (full shadow) is the authoritative one. No metrics were mixed
across classes.

## 2. Risks

- Routing top-1 agrees only 56.7% on short real descriptions; as a hint
  source it is weak — as a recorder it is harmless.
- News proxy disagreement (45%) reflects a weak reference label as much as
  the engine; never use NewsGate as a hard filter on this evidence.
- Opportunity FN=5 @0.6 (3.2% of LLM-worthy dropped) — each surfaces for
  human rescue, but the rescue queue must actually be staffed.
- Another process writes to production DBs during any window; canary reads
  stay read-only, but coordinate heavy runs off-peak.

## 3. Usage limits

- Lexical backend: clear-cut triage only. No multi-step policy judgments
  without human review. No sole-source-of-truth use.
- Confidence < threshold → REVIEW_REQUIRED, always (fail-open).
- 1–10% canary samples are too small for decisions; use 100% shadow numbers.

## 4. Suitable cases

Pre-LLM spam/irrelevant filtering (opportunity @0.8: 0 FN), urgency/priority
hints, retry/review flags, news triage (keep+maybe → LLM, never hard drop).

## 5. Unsuitable cases

Final routing authority, sole relevance judge for news, any auto-action on
low confidence, anything requiring reasoning over pages of policy.

## 6. Kill switch

`LOCAL_DECISION_ENGINE_ENABLED=0` → every mode behaves DISABLED: engine never
called, routing/filtering/decisions byte-identical to today. Tested
(`test_kill_switch`): with the switch off, the engine callable is never
invoked. Per-call override: `ModeGate.evaluate(DISABLED, …)`.

## 7. Rollback procedure

There is nothing to roll back: SHADOW/CANARY never write production state.
To fully remove: (1) set the kill switch to 0, (2) stop the service with
`stop-local-decision-engine.bat`, (3) delete the two added adapter files
(`orchestrator/adapters/local_decision.py`, `oppengine/decision_gate.py`) —
existing code never imports them, so deletion is a no-op for production.

## 8. Tests (50/50)

Modes DISABLED/SHADOW/CANARY (+ACTIVE config-only), kill switch, fail-open on
unavailable/malformed/timeout/exception/missing-model/corrupted-response,
configurable thresholds, determinism, no-network, no-secret-logging
(`tests/test_modes.py`, 15 tests). Failure tests assert the existing decision
is returned byte-identical.

## 9. Performance impact

| Layer | Baseline (measured) | Engine overhead |
|---|---|---|
| Orchestrator task | agent run median ~104 s (history) | +~1 ms shadow (0.001%) |
| Opportunity LLM step | local-LLM latency ~154–308 s (`llm_usage`) | +~1 ms gate check |
| Canary 1/5/10% | — | 1/5/10% × ~1 ms on sampled items only; 0 elsewhere |
| Shadow full | — | p50 ~1 ms, p95 ~2 ms, ~27 MB flat, 0 VRAM |

No visible regression possible at these ratios; canary sampling bounds even
that. Memory flat across 430 evals; determinism verified (identical digests,
two passes).

## Recommendation data (no winner — decide from the numbers)

| Threshold | Coverage (B/C) | Agreement (B/C) | FP (B/C) | FN (B/C) | Review rate (B/C) | LLM-invocation reduction |
|---|---|---|---|---|---|---|
| 0.60 | 18.6% / 20.5% | 93.2% / 45.3% | 6 / 83 | 5 / 5 | 81% / 80% | 6.2% overall |
| 0.70 | 13.7% / 13.0% | 93.8% / 45.3% | 6 / 88 | 4 / 0 | 86% / 87% | 2.8% |
| 0.80 | 4.4% / 1.9% | 96.3% / 44.1% | 6 / 90 | 0 / 0 | 96% / 98% | 0.9% |
| 0.90 | 0% / 0% | 96.3% / 42.2% | 6 / 93 | 0 / 0 | 100% / 100% | 0% |

(FP counts review-routed fail-open items, not wrong auto-actions; FNs are the
rescue queue.) **Not declared production-ready**: class A and C evidence is
too weak for auto-action; class B supports a 0.8-threshold canary with human
rescue staffing. ACTIVE mode was not enabled and no production behavior changed.
