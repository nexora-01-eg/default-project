# Local Decision Engine

> **This is a local open-source decision engine inspired by / compatible with the
> Jev/System One style of decision interface. It is NOT the original TypeSafe Jev
> model**, not affiliated with or endorsed by TypeSafe. Reference implementation
> vendored for wire-compatibility: `vendor/local-jev` (MIT © 2026 Amith Chandrappa).

## What is it?

A tiny localhost service your projects call for **fast, free, offline decisions**
instead of spending a big LLM on every judgment: choice, yes/no, score,
classification, routing, gating, filtering — with a confidence on every answer.

```
DATA → LOCAL DECISION ENGINE → should we spend expensive LLM compute?
        conf ≥ threshold → act / continue
        conf < threshold → fallback: existing logic, bigger model, or human
```

## Why / when to use it

- Pre-filtering before any LLM call (1000 news → 150 → summarize 20)
- Routing hints (which agent?), retry/fallback calls, priority, spam gates
- Anywhere a wrong answer is cheap **if** low confidence routes to review

## When NOT to use it

- Writing, coding, deep analysis, summarization, long reasoning, content creation → use the LLM/coding agent
- Multi-step policy judgments as sole truth → use as accelerator + review
- As the only source of truth → keep raw data; low confidence must fall back

## Run / stop

```
start-local-decision-engine.bat    (starts http://127.0.0.1:8765, localhost only)
stop-local-decision-engine.bat
decision-engine doctor | status | test | models | benchmark | serve | decide
```

No API key, no telemetry, no cloud. Optional `LOCAL_DECISION_API_KEY` env adds a
Bearer check on `/v1/*` if you ever need it.

## API (Jev-wire-compatible subset)

- `POST /v1/systemone` — `{state, model?, questions}` → `{model, answers, usage}`
- `GET /v1/models`, `GET /healthz`, `GET /` (pointer, API only, no UI/DB)
- Headers: `x-typesafe-request-id` always; `x-local-jev-truncated` when a long
  state was shortened. Errors: 422 detail list, 404 unknown model, 503
  `model_unavailable`, 401 bad/missing key (only if you set one).

Question types: `choice` (criteria map), `score` (ordered levels list),
`noul` (yes/no statement). Same validation rules as local-jev.

## Python

```python
import sys
sys.path.insert(0, r"C:\Users\NOUR SOFT\Documents\Default Project\local-decision-engine\src")
from decision_engine import LocalDecisionEngine

eng = LocalDecisionEngine()  # default backend, offline
ans = eng.decide("Someone is asking for a website for their restaurant.", {
    "opp": {"type": "choice", "instructions": "Is this a real service opportunity?",
            "criteria": {"A": "real service opportunity", "B": "maybe", "C": "irrelevant"}}})
# {"opp": {"type": "choice", "choice": "A", "confidence": 0.86, "probabilities": {...}}}

gated = eng.decide_with_fallback("Hello?", {...}, threshold=0.6)
# {"status": "ok" | "needs_review" | "fallback_used" | "backend_error", ...}

from decision_engine import HostedJevEngine  # real local-jev server (e.g. via WSL2)
eng2 = HostedJevEngine("http://127.0.0.1:8765")  # loopback only, enforced
```

Swap backends without touching callers: `create_engine("local" | "hosted" | "llm")`.
`LLMFallbackEngine` without credentials answers `AUTH_REQUIRED` — it never
invents keys or calls paid services.

## JavaScript (any project)

```js
const r = await fetch("http://127.0.0.1:8765/v1/systemone", {
  method: "POST", headers: {"Content-Type": "application/json"},
  body: JSON.stringify({ state: "Need an online store, budget $2000",
    questions: { opp: { type: "choice", instructions: "Real opportunity?",
      criteria: { A: "real service opportunity", B: "maybe", C: "irrelevant" } } } })
});
const { answers } = await r.json();
if (answers.opp.confidence < 0.6) { /* fallback: existing logic / human */ }
```

## Integrations (all opt-in, all default OFF)

| Project | File added (existing code untouched) | Enable |
|---|---|---|
| AI-Agent-Orchestrator | `orchestrator/adapters/local_decision.py` (`LocalDecisionEngineAdapter`: route_hint, classify_task, decide_retry, decide_fallback, needs_large_llm, needs_review) | construct with `enabled=True` after your own benchmark; router/factory unchanged |
| ai-opportunity-engine | `oppengine/decision_gate.py` (`prefilter_item`, `worth_deep_analysis`) | set `OPP_DECISION_GATE=1` + wire the 5-line block in the docstring into `pipeline.py` (not wired yet) |
| News tool (الحمامة) | no codebase found on disk — use `NewsGate` (`triage`, `filter_batch`) from this package when wiring | see `src/decision_engine/adapters/news.py` |

Both integration files degrade to `disabled/review` when the engine is
unreachable — they can never stop the host system.

## Change the model / add a backend

- Today: `rules-tfidf` (stdlib, 0 MB). `nli-deberta-large` (0.87 GB) is a
  **reserved name that refuses to load** until you approve the download.
- Install order (gated): NLI 0.87 GB → qwen2.5-1.5b → larger only with proof.
- To serve a real local-jev backend later (needs WSL2 distro + RAM/VRAM headroom):
  run `vendor/local-jev` per its README, then point `HostedJevEngine` at it.

## Benchmark

```
decision-engine benchmark   (writes docs/BENCHMARK_RESULT.json)
```

Latest: **93.6% on 78 project cases, 100% when confident, p95 1 ms, ~24 MB RAM,
0 VRAM**. Details: `docs/LOCAL_DECISION_ENGINE_BENCHMARK.md`,
`docs/LOCAL_DECISION_MODEL_BENCHMARK.md`. Residual misses are all low-confidence
→ review by design.

## Layout

```
local-decision-engine/
├── README.md  start/stop .bat  config/default.json
├── src/decision_engine/  primitives questions scorer engine server cli adapters/
├── vendor/local-jev/  (reference clone, MIT — not executed by default)
├── dataset/decisions_80.jsonl  scripts/  tests/  docs/  logs/
```
