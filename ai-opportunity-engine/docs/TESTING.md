# TESTING.md

Run with the real interpreter (bare `python` is a Store shim):

```powershell
cd ai-opportunity-engine
& "C:\Users\NOUR SOFT\AppData\Local\Programs\Python\Python311\python.exe" -m pytest tests -q
```

Coverage (all offline, no network/LM Studio — dead-port + monkeypatched adapters):
unit (normalize incl. Arabic/English, semantic), database (insert/dedup/backoff),
deduplication + clustering (AR video-request trio groups; non-AI never clusters),
AI classification (rules fallback honesty, feasibility enum), source adapters
(registry, stubs, politeness), scheduler semantics (10-min cycle config + per-source
`due()`/backoff), dashboard (page render AR/RTL + EN/LTR, i18n helpers, feedback values),
security (SSRF block-list, redaction, escaping), pipeline e2e (fake adapter cycle + spec shape).
Do not fake results: failures must be fixed, not mocked away (only external I/O is stubbed).
