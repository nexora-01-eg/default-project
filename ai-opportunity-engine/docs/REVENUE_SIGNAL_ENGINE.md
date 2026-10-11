# docs/REVENUE_SIGNAL_ENGINE.md

`oppengine/revenue.py` — deterministic classifier, AR/EN + Arabizi first-class.

Levels: `high` (payment observed, or hiring + business/urgency), `medium` (hiring, or
tool-want + business/automation), `low` (single weak signal), `unknown` (no signals),
`not_commercial` (news/tutorial/opinion markers AND zero revenue signals).

Signal kinds (all OBSERVED with matched phrase stored): payment (ادفع/ميزانية/budget/$…),
hiring (محتاج حد/looking for a developer/3ayez 7ad…), business (شركتي/manually/clients…),
tool_want (فيه برنامج/is there a tool…), automation (أتمتة/integrat…).
Flags: payment_language, hiring_language, business_context, urgency.
Level itself is INFERRED; absence of data stays UNKNOWN — never proof of payment.
Stored per request in `revenue_signals` + denormalized `normalized.revenue_level`.
Dashboard: /revenue-signals (fresh med/high), /revenue filtered view.
