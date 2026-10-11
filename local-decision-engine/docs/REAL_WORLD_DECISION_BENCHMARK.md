# REAL-WORLD DECISION BENCHMARK (Phase 11)

430 evaluations on real local data. Method: `python scripts/shadow_benchmark.py`
(read-only shadow). Full numbers: `logs/shadow_summary_20260923_052907.json`.
Stream design and non-interference: `SHADOW_MODE_REPORT.md`. Thresholds:
`THRESHOLD_ANALYSIS.md`. **No winner declared anywhere.**

## By confidence band (threshold 0.6)

- HIGH (≥0.8): 14 dataset cases + 7 opp + 3 news + 0 orch — **100% agreement
  with reference, 0 high-confidence disagreements in any stream**
- MEDIUM (0.6–0.8): acted on with the counts in the threshold doc
- LOW (<0.6): REVIEW_REQUIRED — 79–81% of production rows (correct: short
  texts carry little signal; the gate says so instead of guessing)

## Requested metrics (measured, this machine)

| Metric | Value | Notes |
|---|---|---|
| Real cases used | **430 evals** (30 tasks + 161 opp rows + 161 news views + 78 labeled). 1000 unavailable locally; nothing fabricated | §4 honest count |
| Agreement rate | orch 56.7% top-1; opp 93.2%; news 45.3% (weak proxy) | vs existing, not vs truth |
| Accuracy by confidence | ≥0.8: 100%; <0.6: not acted on | calibration holds |
| False positives | opp 6 (fail-open reviews, constant); news 83 incl. reviews-as-keep | vs pipeline reference |
| False negatives | opp 5 @0.6 → 0 @0.8; news 5 @0.6 → 0 @0.7 | dropped-but-worthy, all surfaced for rescue |
| p50 / p95 latency | **~1 ms / ~2 ms** (max 3 ms, incl. logging) | in-process scoring is <0.5 ms |
| Decisions/sec | **~935** end-to-end with DB reads + JSONL logging | ~2,300 pure scoring |
| Memory | **24.8 → 26.8 MB** across 430 evals (flat) | 0 VRAM, CPU only |
| Filterable pre-LLM @0.6 | **20/322 (6.2%)**; of LLM-worthy 5/155 (3.2%) | "estimated reduction in LLM invocations", no money claim |
| Determinism | **true** (two full passes, identical digests) | |

## Blockers for Shadow Mode?

None found. Shadow is read-only, dependency-free, ~27 MB, and cannot alter
outcomes (adapters default OFF; harness imports no production code). Two
observations, not blockers: (1) orchestrator log files are permission-locked
by their owner — shadow used the DB instead; (2) production DBs receive
writes from another active process during any window — shadow's read-only
handles are unaffected, but schedule heavy shadow runs off-peak on principle.

## What changed in this phase (production: nothing)

- `src/decision_engine/scorer.py`: meta-words → stopwords; `claim`/`empty`
  out of spam cues (shadow-found false-positive sources). No regression.
- New: `scripts/shadow_benchmark.py`, `tests/test_shadow.py`, 3 docs, 2 log
  artifacts. `OPP_DECISION_GATE` never set; no gate enabled anywhere.
