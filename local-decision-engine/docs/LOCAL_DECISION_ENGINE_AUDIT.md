# LOCAL DECISION ENGINE — AUDIT (Phase 1)

Date: 2026-09-23. Method: direct inspection (systeminfo, CIM, nvidia-smi, netstat, repo reads). Nothing assumed, nothing deleted or modified.

## Machine

| Item | Finding |
|---|---|
| OS | Windows 10 Pro for Workstations, build 19045, x64 (Dell Precision 3520) |
| CPU | Intel i7-7820HQ @ 2.90GHz, 4 cores / 8 threads |
| RAM | 16 GB total, **only ~2.0–2.8 GB free at audit time** (most is in use) |
| Disk C: | 187 GB total, **~64 GB free** |
| GPU 1 | Intel HD Graphics 630 (1 GB) |
| GPU 2 | NVIDIA GeForce 940MX, 2 GB VRAM, driver 553.46, CUDA 12.4 runtime — **VRAM 1987/2048 MB already used by LM Studio** |
| nvcc (CUDA toolkit) | not installed |

## Toolchain

| Item | Finding |
|---|---|
| Python | 3.11.9 and 3.12.10 installed under `%LocalAppData%\Programs\Python\`, **not on PATH** (`python` resolves to the Store stub). pip 26.2.1 works via full path. pytest 9.1.1 present for 3.11 |
| uv | 0.12.15 available |
| git | 2.53.0 |
| WSL2 | present but **no Linux distro installed** (only `docker-desktop`, Stopped). local-jev's README requires WSL2 on Windows |
| Docker | 29.8.0 (Desktop, not running workloads) |
| Ollama | not installed |
| LM Studio | installed and running, holding ~2 GB VRAM; models on disk: `Qwen2.5-Coder-7B-Instruct-Q4_K_M` GGUF + a partial gemma-4 download |
| Ports | **8765 FREE** (chosen for the service). 1234 in use (LM Studio). 8000/8080/11434 free |

## Existing projects (found, not touched)

| Project | Path | Notes |
|---|---|---|
| AI-Agent-Orchestrator | `Documents\AI-Agent-Orchestrator` | Supervisor+router architecture, adapters: OpenCode/Aider/Qwen/Gemini/LMStudio. Integration point: new optional file `orchestrator/adapters/local_decision.py` (router untouched) |
| ai-opportunity-engine | `Documents\Default Project\ai-opportunity-engine` | Pipeline COLLECT→…→SCORE with rules pre-filter + LLM budget (4/cycle). Integration point: new optional `oppengine/decision_gate.py` (pipeline untouched) |
| News tool (الحمامة) | **no codebase found** | Only `n8n\n8n_data\news-data\feeds` (empty). No code modified; reusable `NewsGate` adapter provided + wiring doc |
| Default Project .venv | Python 3.11.9, ML-heavy (onnxruntime, hf_hub…) | **Not reused** — decision engine got its own empty venv to avoid breaking video work |

## Decisions derived from the audit

1. **No torch/transformers install, no model downloads now.** Free RAM (~2 GB) and full VRAM cannot host even the 0.87 GB NLI model stably alongside LM Studio; WSL has no distro for local-jev's Windows path. Installing would risk the machine for no proven gain.
2. **Default backend = `rules-tfidf`** (stdlib only, ~24 MB RAM, 0 VRAM, offline). It must earn its place by benchmark, not by claim — see `LOCAL_DECISION_MODEL_BENCHMARK.md`.
3. **local-jev (MIT, cloned shallow to `vendor/local-jev`) is kept as reference + future backend.** `HostedJevEngine` speaks its wire format, so swapping later needs no caller changes. The 0.87 GB NLI download stays behind a benchmark gate.
4. **Service binds 127.0.0.1:8765 only.** No telemetry, no cloud, no keys (see security tests).
