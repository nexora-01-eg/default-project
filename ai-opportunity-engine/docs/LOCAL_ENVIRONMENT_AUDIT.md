# LOCAL_ENVIRONMENT_AUDIT.md — AI Opportunity Engine (Phase 0)

**Date:** 2026-09-22 (UTC) · **Machine:** Windows 10 Pro for Workstations 64-bit, Build 19045
**Audit mode:** read-only inspection. Nothing installed, nothing modified outside `ai-opportunity-engine/`.
**Working root:** `C:\Users\NOUR SOFT\Documents\Default Project` (contains an unrelated
video-editing project — left untouched; this project lives in the `ai-opportunity-engine/` subfolder).

---

## 1. Hardware

| Component | Detail (verified) |
|---|---|
| CPU | Intel Core i7-7820HQ @ 2.90 GHz, 4 cores / 8 threads (Kaby Lake-H) |
| RAM | 16 GB total (16 555 028 KB visible) |
| iGPU | Intel HD Graphics 630, 1 GB, driver 31.0.101.2130 (Quick Sync available) |
| dGPU | NVIDIA GeForce 940MX, 2 GB VRAM, driver 553.46, CUDA driver 12.4 (Maxwell GM108, weak; ~1.8 GB currently in use by LM Studio) |
| Storage | C: 68.8 GB free / 201 GB · D: 370 GB free · E: 160 GB free · F: 140 GB free |
| Arch | x64 |

## 2. Operating system

- Windows 10 Pro for Workstations, 64-bit, Build 19045 (PowerShell 5.1).
- WSL: only `docker-desktop` distro registered, currently **Stopped**.
- Docker: **v29.8.0** client present (desktop-linux context). Daemon state not relied upon.
- Network: available (LM Studio localhost + internet assumed; public APIs reachable — verified indirectly via pip/npm ecosystem; collection adapters verify at runtime).

## 3. Development tools (verified)

| Tool | Version | Status |
|---|---|---|
| Python (real) | **3.11.9** at `...\Python\Python311\python.exe` (+ `Scripts\pip.exe`, pip 26.2.1) | ✅ usable (note: bare `python`/`python3`/`py` resolve to MS Store shim — always use full path or project `.venv`) |
| Project `.venv` (video project, do not touch) | Python 3.11 + numpy, Pillow, OpenCV 5, faster-whisper 1.2.1, scenedetect, pydantic, pytest, rich | ✅ exists, reusable pattern only |
| System pip packages | Flask 3.1.3, Flask-SQLAlchemy, SQLAlchemy 2.0.54, requests, pytest 9.1.1, uv 0.12.15 | ✅ |
| Node.js / npm | v24.14.1 / 11.11.0 (+ bun 1.4.2, pnpm, yarn, typescript globally) | ✅ |
| Git | 2.53.0.windows.2 | ✅ (working dir is **not** a git repo) |
| GitHub CLI (`gh`) | — | ❌ not installed |
| gcc / CUDA toolkit / conda | — | ❌ not installed (not needed) |
| sqlite3 CLI | — | ❌ not installed — **but** `sqlite3` stdlib module present (SQLite 3.45.1, verified) |

## 4. AI tools (verified versions + paths)

| Tool | Version | Path | Runs? | Auth | Local API | Usable by this project |
|---|---|---|---|---|---|---|
| OpenCode | 1.18.31 | `%APPDATA%\npm\opencode.ps1` | ✅ | providers optional | — | ✅ future `opportunity_spec.json` consumer (manual handoff in MVP) |
| Aider | 0.86.2 | `~\.local\bin\aider.exe` | ✅ | needs coder LLM | — | ✅ can point at LM Studio endpoint |
| Gemini CLI | 0.60.0 | `%APPDATA%\npm\gemini.ps1` | ✅ | needs OAuth | — | ⚠️ auth-gated, not used in MVP |
| Qwen Code | 0.24.0 | `%APPDATA%\npm\qwen.ps1` | ✅ | local-first | — | ✅ optional |
| LM Studio + `lms` CLI | app 0.4.14-4 / CLI commit 4ecb9cd | `~\.lmstudio\bin\lms.exe` | ✅ **server ON :1234** | none (localhost) | ✅ OpenAI-compatible | ✅ **primary reasoning + embeddings backend** |
| Ollama | — | — | ❌ not installed | — | — | ❌ do not install (LM Studio covers need) |

## 5. Local models (verified via `lms` + filesystem + live API probes)

| Model | Size | Format | Runtime | Loaded | API | Suitable for |
|---|---|---|---|---|---|---|
| `qwen2.5-coder-7b-instruct` (Q4_K_M GGUF, `~/.lmstudio/models/lmstudio-community/Qwen2.5-Coder-7B-Instruct-GGUF/`) | 4.68 GB | GGUF | LM Studio | ✅ yes | `POST http://localhost:1234/v1/chat/completions` (smoke-tested, replies correctly) | classification · extraction · reasoning · summarization · AR/EN · coding |
| `text-embedding-nomic-embed-text-v1.5` | bundled (~0.5 GB class) | GGUF | LM Studio | ✅ yes | `POST http://localhost:1234/v1/embeddings` (smoke-tested, real vectors returned) | embeddings · dedup · clustering · search |
| `gemma-4-E4B-it` (Q4_K_M + mmproj) | ~4.4 GB **incomplete** (`.part` download files only) | GGUF | — | ❌ | — | ❌ not usable until download finishes; ignore for MVP |

No Whisper model files found under LM Studio; but the sibling video project has faster-whisper in its `.venv` (CPU/int8 verified there) + FFmpeg 9.0.1 — reusable **pattern**, not a dependency.

## 6. Available APIs (live-verified 2026-09-22)

- `GET http://localhost:1234/v1/models` → 200, lists both models above.
- `POST /v1/chat/completions` (qwen2.5-coder) → 200, correct completion.
- `POST /v1/embeddings` (nomic-embed) → 200, real float vectors.
- No auth, localhost-only. No key management needed; endpoint is configurable.

## 7. Databases

- **SQLite** via Python stdlib (3.45.1) → ✅ MVP store. No server needed.
- PostgreSQL / Redis / Elasticsearch / vector DBs → ❌ none installed. **Not needed**: SQLite + local embeddings cover MVP scale (target: thousands of requests, not millions).

## 8. Crawling / search capabilities

- Python: `requests` + stdlib `urllib` available; `feedparser`, `praw`, `scrapy`, `beautifulsoup` → ❌ not installed → MVP uses stdlib `urllib` + `xml` for RSS/Atom and public JSON APIs (no new installs).
- Public JSON APIs usable without keys: **Hacker News (Firebase + Algolia)**, **GitHub Search (unauth, rate-limited)**, **StackExchange API (no key, quota-limited)**. Reddit public JSON implemented as opt-in adapter (rate-limited, may 429 — documented).
- robots.txt respected via adapter-level fetch + conservative intervals; no CAPTCHA/auth bypass anywhere.

## 9. Browser automation capabilities

- Playwright / Puppeteer / Selenium → ❌ none installed. No browser driver found.
- Decision: **no browser automation in MVP** (per scope limit). Adapter interface reserves a `browser` source kind for Phase 6.

## 10. Existing reusable projects (inspected, NOT modified)

- `Documents\Default Project\` (video engine): staged JSON pipeline, per-stage cache, `doctor` CLI, FFmpeg gateway pattern, faster-whisper CPU pattern, approval-gated execution. **Reuse: architectural patterns only.**
- `Documents\AI-Agent-Orchestrator\`: adapter/agent registry, orchestrator DB, agent-menu pattern. **Reuse: adapter-interface + doctor-report ideas.**
- `Documents\Codex`, `test-*` dirs, `*.bat` launchers: agent smoke-test scaffolds. No code copied.
- `templates/`, `assets/`, `scripts/make_test_media.py`: synthetic-fixture pattern → mirrored in our `tests/fixtures.py`.

## 11. Potential conflicts

1. Bare `python` resolves to MS Store shim — scripts must use the full `Python311\python.exe` path or a project venv.
2. `C:\` has 68 GB free — fine, but SQLite + logs go to project `data/`; large artifacts should prefer `D:` later.
3. 940MX VRAM nearly full (LM Studio resident) — all inference stays on the already-loaded models; no new model loads in MVP.
4. Gemma download in progress — do not depend on it.
5. Working dir hosts an unrelated project — **all new code stays under `ai-opportunity-engine/`**.

## 12. Recommended local architecture

Stdlib-only Python 3.11 service: SQLite store → source adapters (public JSON/RSS over urllib) → normalize + lang-detect (heuristic, AR/EN) → AI reasoning (LM Studio chat, deterministic fallback) → embeddings (LM Studio embeddings, token-Jaccard fallback) → dedup/cluster → rules+evidence scoring → local-feasibility check → stdlib `http.server` dashboard (AR/EN, RTL/LTR, dark/light). 10-minute pipeline cycle with per-source intervals/backoff/health. `opportunity_spec.json` export for future OpenCode handoff.

## 13. What should NOT be installed

Ollama (redundant), PostgreSQL/Redis/Elasticsearch/vector DBs (overkill), Playwright/Selenium (out of scope), CUDA toolkit (driver suffices), any paid API, Node service deps (dashboard is stdlib), `gh` CLI (no git remote needed yet), new pip packages for the MVP runtime (tests use existing pytest).

## 14. What should NOT be modified

The sibling video-engine project (`engine/`, `.venv/`, `projects/`, `input/`, `output/`, `docs/`, `*.md` at root), `AI-Agent-Orchestrator/`, `Codex/`, `test-*` dirs, user `*.bat` launchers, LM Studio settings/models, global npm packages.

## 15. Capabilities accelerating this project

1. Loaded local coder LLM (Qwen 2.5 Coder 7B) → free reasoning/classification/extraction, AR/EN capable.
2. Loaded local embedding model (Nomic v1.5) → free semantic dedup/clustering/search.
3. FFmpeg 9.0.1 + faster-whisper know-how next door → local-feasibility evidence for media/STT opportunities.
4. Python 3.11.9 + SQLite 3.45.1 + pytest → zero-install MVP runtime.
5. Docker 29.8 + Node 24 → deployment/packaging options later, unused in MVP.
6. Public no-key APIs (HN, GitHub, StackExchange, RSS) → real data from minute one.
