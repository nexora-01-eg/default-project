# docs/LEAD_INTELLIGENCE.md

`oppengine/leads.py` — preserve, never enrich.

Extracted ONLY from the request row: public_username/author, public_profile_url,
email/website/social links appearing verbatim in text (platform/post URLs excluded from
website candidates), source post URL. Phones are detected and REDACTED, never stored.
contactability high/medium/low/none with OBSERVED reasons; no contact → UNKNOWN.
Stored in `leads` (request UNIQUE, linked to opportunity on clustering).

Contact Brief (`/brief?id=`, also `leads.contact_brief`): problem, why-it-may-help,
offer sketch, evidence bullets, public profile/contact, source links, and a suggested
first message marked DRAFT in AR/EN. The system has no sending capability by design —
no SMTP/API outreach code exists. New feedback decision `contact_manually` records
manual outreach intent.
