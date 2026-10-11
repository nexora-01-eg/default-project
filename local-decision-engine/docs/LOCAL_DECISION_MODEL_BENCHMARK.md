# LOCAL DECISION MODEL BENCHMARK (Phases 3 + 5)

No invented numbers. Every figure below was measured on this machine
(i7-7820HQ, 16 GB RAM) on 2026-09-23. Raw machine output: `docs/BENCHMARK_RESULT.json`
(78 cases). Method: `decision-engine benchmark`.

## Model choice for this hardware

| Model (local-jev card) | Download | RAM need | Verdict for this machine |
|---|---|---|---|
| `rules-tfidf` (this project, stdlib) | 0 MB | ~25 MB, 0 VRAM | **default — measured below** |
| `nli-deberta-large` | 0.87 GB | ~0.9 GB + torch (~2 GB install) | **gated**: only ~2 GB RAM free and VRAM full; install only after freeing memory AND re-running this benchmark against it |
| `llm-qwen2.5-1.5b` | 3.09 GB | ~3 GB | not before the NLI gate passes |
| `llm-qwen3.5-4b` (local-jev default) | 9.32 GB | ~8.5 GB | no — exceeds free RAM today; would also fight LM Studio for VRAM |

The order above is the install order. Nothing larger downloads without a
benchmark proving the machine runs it stably.

## Results: `rules-tfidf` on `dataset/decisions_80.jsonl` (78 real cases)

| Metric | Measured |
|---|---|
| Accuracy | **93.6% (73/78)** |
| Accuracy when confident (conf ≥ 0.8) | **100% (14/14)** — calibration works: when it says it's sure, it's right |
| Latency p50 / p95 / max | **~0.0 / 1.0 / 1.0 ms** per decision |
| Throughput | **~2,300 decisions/s** (single process) |
| RAM (process) | **~24 MB**, flat across the run |
| VRAM | **0 (CPU/std-only, no GPU touched)** |
| Startup | instant (no weights to load; first decision warms caches) |
| Stability | 0 crashes, 0 errors across 78 cases + 20 concurrency requests |
| Offline | yes — airplane-mode capable; zero network calls in code (security test enforced) |

Accuracy by domain: opportunity 100% (30/30), routing 90%, gating 100%,
news 91.7%, score 100%, retry 100%, llm-gate 100%, noul 62.5% (5/8).

## The 5 misses — all low-confidence (routed to review, never acted on)

| Case | What happened | System behavior |
|---|---|---|
| routing #36 (Qwen expected) | honest 50/50 tie: planning cues (coordinate) + multi-file cues (feature) both legitimately fire | conf 0.30 → review |
| news #52 (smartphone, maybe) | genuinely ambiguous whether AI-involved | conf 0.04 → review |
| noul #56/#57/#60 | 0.506 coin flips on near-zero signal inputs | → review (threshold 0.6) |

Design consequence (kept): **the gate is conservative** — top-1 right 93.6% of
the time, and anything unsure goes to existing logic/human instead of acting.

## Honest limits

- This backend is lexical (TF-IDF + cue groups), not reasoning. Multi-step
  policy judgments are its weak tier — same pattern local-jev reports for the
  NLI model on hard items (54% JevBench). Low confidence is the signal to
  escalate, not a failure.
- Dataset is project-specific (78 cases), not JevBench. Don't compare 93.6%
  with local-jev's published 80.5%/54.1% — different tests, different hardware.
- If you free RAM/VRAM later, the fair next step is benchmarking
  `nli-deberta-large` (0.87 GB) head-to-head on this same dataset before
  switching anything.
