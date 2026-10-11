# docs/ARABIC_SOURCES.md

Arabic is first-class: revenue patterns cover MSA + Egyptian + Arabizi; adapters declare
`languages`; Reddit subs configurable (`reddit_subs`, defaults include Egypt/arabic/Arabs);
RSS defaults include r/Egypt + r/arabic public feeds; filters/views support `flang=ar`.

Honesty rules enforced in code: login/CAPTCHA/anti-bot/private content never bypassed.
Unsupported sources carry machine-readable `support_status`:
NOT_SUPPORTED (x, facebook, tiktok, instagram), CONFIG_REQUIRED (youtube key, telegram
channels, discord token, marketplace feeds), BLOCKED/RATE_LIMITED (computed from errors).
Validation reports real per-source numbers; zeros reported as zero (see
PHASE_2_VALIDATION.md). No synthetic Arabic demand exists anywhere in the system.
