# SECURITY.md

- **Secrets:** no keys in code/config (LM Studio is keyless localhost); `scan_for_secrets()`
  runs in `doctor`; logs redacted via `redact_secrets()`; `.gitignore` covers `data/`, `logs/`.
- **SSRF:** `validate_public_url()` blocks non-http(s), credentials-in-URL, private/loopback/
  link-local/reserved IPs; localhost only allow-listed for the LM Studio endpoint.
- **Input:** `sanitize_text()` strips controls + caps length; all dashboard output HTML-escaped.
- **DB:** parameterized queries only; WAL file DB, no network exposure.
- **Subprocess:** none in the MVP path (FFmpeg/pip only in docs); when added, arg-lists only.
- **Dashboard:** binds 127.0.0.1 by default; never exposes filesystem paths or env.
- **Sources:** polite intervals + backoff; no auth/CAPTCHA bypass; public data only, no PII enrichment.
