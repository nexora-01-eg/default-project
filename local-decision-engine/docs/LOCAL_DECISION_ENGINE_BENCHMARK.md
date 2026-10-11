# LOCAL DECISION ENGINE BENCHMARK — full report (Phase 13)

Canonical numbers live in `docs/BENCHMARK_RESULT.json` (written by
`decision-engine benchmark`, 78 cases, measured 2026-09-23 on i7-7820HQ).
Model-selection reasoning: `docs/LOCAL_DECISION_MODEL_BENCHMARK.md`.

## Headline

- Accuracy **93.6% (73/78)**; **100% (14/14)** when confidence ≥ 0.8
- Latency **p50 ~0 ms, p95 1 ms**; throughput **~2,300 decisions/s**
- RAM **~24 MB**, VRAM **0**, startup **instant**, offline **yes**
- Tests: **26/26 pytest pass** + **15/15 live API checks pass**

## Confidence calibration

| Confidence | n | Correct |
|---|---|---|
| ≥ 0.8 (act) | 14 | 14 (100%) |
| 0.6–0.8 (act with care) | — | threshold per project |
| < 0.6 (review/fallback) | — | all 5 misses live here |

## False positives / negatives (all 5, none hidden)

1. routing#36: tie OpenCode/Qwen (both cues legitimately fire) → review
2. news#52: ambiguous AI-relevance → review
3. noul#56, #57, #60: 0.506 coin flips on near-zero-signal inputs → review

No high-confidence error was observed. The first high-confidence error found
in production should trigger a scorer review (add a cue group, re-run).

## Resource usage

- CPU: negligible per decision (<1 ms); 20 concurrent HTTP requests, 0 errors
- RAM: 24.2 → 24.3 MB across the full benchmark (flat)
- GPU: untouched — safe to run alongside LM Studio / video rendering
- Disk: project < 1 MB + vendored local-jev source (~1 MB); **0 MB of model weights**

## Reproduce

```
decision-engine benchmark
python -m pytest tests -q        (from the project .venv)
python scripts/test_api.py       (needs the server running)
```
