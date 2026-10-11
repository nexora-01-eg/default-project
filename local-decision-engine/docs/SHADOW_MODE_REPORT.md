# SHADOW MODE REPORT (Phase 11)

Shadow = the engine observes and records, but **changes nothing**.
Harness: `scripts/shadow_benchmark.py` (stdlib only). Evidence: `logs/shadow_run_20260923_052907.jsonl`
(430 redacted records), `logs/shadow_summary_20260923_052907.json`.

## Non-interference guarantees (verified, not promised)

- Production DBs opened **read-only** (`sqlite3 ...?mode=ro`, single helper —
  grep the harness: zero INSERT/UPDATE/DELETE). Production code never imported.
- Orchestrator log files were permission-locked by their owner process — left
  alone, not forced. (Their task history came from `orchestrator.db` instead.)
- Every adapter stays **disabled by default**; `OPP_DECISION_GATE` was never set.
- No model downloaded, no GPU touched, LM Studio untouched, routing untouched.
- Note: both production DBs (and several `oppengine/*.py` files) show writes
  during the window from **another active process** — not from this harness
  (read-only handles cannot write; the harness writes only to its own `logs/`).

## Real cases used (nothing fabricated; 1000 unavailable)

| Source | n | Existing decision used as reference |
|---|---|---|
| AI-Agent-Orchestrator `tasks` table | 30 real tasks | `selected_agent` (Aider 18 / OpenCode 12) |
| ai-opportunity-engine `raw_requests`+`normalized` | 161 real rows | pipeline rule: LLM-worthy unless (`human_service`/`unclear` + relevance `none`) → 155 worthy / 6 filtered |
| Same 161 rows through the news lens | 161 | `ai_relevance` high/medium → keep (68) else drop-candidate (93). Proxy, labeled as such |
| Labeled project dataset | 78 | ground-truth labels (accuracy 93.6%) |
| **Total evaluations** | **430** | |

## Results @ threshold 0.6 (records: top-1, confidence, latency, timestamp, redacted text)

| Stream | Agreement with existing | Actionable (keep/drop) | Low-conf (review) | High-conf disagreement |
|---|---|---|---|---|
| orchestrator (30) | **56.7%** top-1 | 20% | 80% → existing router decides | **0** |
| opportunity (161) | **93.2%** | 18.6% | 81.4% → existing pipeline continues | **0** |
| news (161) | 45.3% vs `ai_relevance` proxy | 20.5% | 79.5% → human/LLM | **0** |

Reading: the gate is **conservative** — unsure means REVIEW_REQUIRED, never
auto-pass. Opportunity filtering already tracks the pipeline closely;
orchestrator routing on short task descriptions is mostly "ask the router"
(which is the safe answer); the news proxy disagrees often because
`ai_relevance=low` (87 rows) is a weak "drop" label — triage use only.

## Bug found BY shadow mode (fixed, no regression: 26/26 tests, dataset 93.6%)

Short task descriptions carried ~zero signal, and the instruction word
**"task"** ("Which agent should handle this **task**?") lexically boosted the
Gemini option ("internet research **task**") → 22/30 top-1 Gemini, agreement
20%. Fix: decision-meta words (`task, agent, handle, decision, output, input,
result…`) are now stopwords. Agreement rose to 56.7% with **zero**
high-confidence disagreements. Two more precision fixes from high-confidence
false drops on full page texts: `claim` and `empty` removed from spam cues
(legit tech writing triggers them).

## Safety rule (enforced in code and tests)

`confidence < threshold` → `REVIEW_REQUIRED`. Review is fail-open: it keeps
existing behavior (counts with "keep" in agreement math — see threshold doc
for why high-threshold "disagreements" are safe-direction).
