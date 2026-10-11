# AI_REASONING.md

Backend: LM Studio `qwen2.5-coder-7b-instruct` (`POST /v1/chat/completions`, temp 0.2,
compact JSON schema, code-fence tolerant). Every candidate passes this stage before
becoming an opportunity.

Extracted: original text, normalized request, language, country/region (only if explicit),
request type (explicit_ai|implicit_ai|automation|human_service|not_ai|unclear), problem,
desired outcome, requirements, constraints, urgency, pain points, mentioned solutions,
AI relevance, automation potential, feasibility, confidence, reasoning summary, cluster link.

Feasibility states: clearly_feasible, feasible_with_human, feasible_with_local_tools,
feasible_with_external, experimental, difficult, impractical, not_ai, insufficient_info.

Honesty rules: non-AI rows skip the LLM (stored as rules/0.5-0.7); LLM failures fall back
to rules with `ai_failure=true` + lower confidence; LLM feasibility outside the enum is
replaced by the rules value. Provider (`lmstudio`|`rules`) + confidence stored per row.

**Measured local budget (2026-09-22):** Qwen2.5-Coder-7B on this box generates at ~1 tok/s,
so a full analysis call costs 60-90s. The pipeline therefore caps LLM *attempts* per cycle
(`max_llm_per_cycle: 4`, `ai_timeout_s: 75`, `max_tokens: 220`); the deterministic rules
layer carries the bulk volume and every row is labeled honestly. Raise the budget only on
faster hardware. Arabic/Fusha + Egyptian dialect prioritized; other dialects/languages
extend `normalize.py`.
