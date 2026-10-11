# docs/BUYER_SIGNAL_ENGINE.md

Phase 3 extends `revenue.py` with 12 Arabic buyer-evidence categories, each storing the
exact observed phrase: HIRING, SERVICE_REQUEST, TOOL_REQUEST, AUTOMATION_REQUEST,
SOFTWARE_REQUEST, PRICE_REQUEST, IMPLEMENTATION_REQUEST, BUSINESS_PROBLEM,
REPEATED_MANUAL_WORK, URGENT_NEED, ALTERNATIVE_REQUEST, COMPLAINT_WITH_SOLUTION_INTENT.
Orthography-normalized matching (أ/إ/آ→ا, ة→ه) for real web Arabic; evidence deduped by
phrase; result carries `categories[]` alongside the Phase 2 level/flags (unchanged
semantics — all 11 Phase 2 revenue tests still pass unmodified).

Level rule deltas: price+hire/implementation or implementation+business → high;
price/implementation alone → medium. Arabic text alone is never commercial
("الطقس جميل…" → unknown). Dashboard: /revenue-signals shows kinds+phrases;
 /arabic filters by intent; opp detail lists per-request evidence.
