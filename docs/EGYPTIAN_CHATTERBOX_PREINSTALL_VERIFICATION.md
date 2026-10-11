# Egyptian Chatterbox TTS — Pre-Install Safety Verification

**Date**: 2026-09-21
**Type**: READ-ONLY — no installation, no downloads, no inference, no modifications
**Candidate**: `AliAbdallah/egyptian-arabic-tts-chatterbox`
**Sources read**: `docs/EGYPTIAN_ARABIC_TTS_NEXT_ACTION.md`, `docs/EGYPTIAN_ARABIC_TTS_RESEARCH.md`, plus live metadata fetched read-only (HF model page, PyPI `chatterbox-tts` 0.1.7, `resemble-ai/chatterbox` repo + `pyproject.toml` at master)

---

## 1. Candidate identity

| Field | Value |
|-------|-------|
| Repository / model ID | `AliAbdallah/egyptian-arabic-tts-chatterbox` (https://huggingface.co/AliAbdallah/egyptian-arabic-tts-chatterbox) |
| Revision / commit | NOT PINNED — no commit hash recorded; Files page shows `README.md`, `app.py`, `model.safetensors`; branch `main` |
| Checkpoint files | `model.safetensors` (fine-tuned T3 only; loaded with `strict=False` over base), `README.md`, `app.py` |
| Model format | safetensors, F32, 0.5B params (~2 GB) |
| Required companions | Base Chatterbox Multilingual weights (auto-downloaded by `from_pretrained`, ~2 GB) + `chatterbox-tts` 0.1.7 package + torch stack |
| Base engine | `resemble-ai/chatterbox` (26.5k stars, active; Multilingual V3 now latest — checkpoint predates V3, see §9 Risks) |

## 2. Repository / checkpoint evidence

- Model card explicitly describes Egyptian fine-tune: 120 h / 43,711 clips, single speaker, partial fine-tune (prosody predictors + late acoustic decoder, 1 epoch to step 2000, loss 6.0→4.57).
- Stated license on card: **Apache 2.0** ("following Chatterbox base model license").
- Training pipeline repo linked: `AliAbdallah21/Chatterbox-Multilingual-TTS-Fine-Tuning`; live demo Space linked (2 Spaces use the model).
- No dataset identifier, no dataset license, no per-voice license file. Confidence on *identity*: HIGH. Confidence on *license chain*: MEDIUM (see §3).

## 3. License matrix

| Component | License | Evidence | Commercial |
|-----------|---------|----------|------------|
| `resemble-ai/chatterbox` runtime (code) | **MIT** | CONFIRMED — repo footer "MIT license" + PyPI `chatterbox-tts` 0.1.7 "License: MIT License" | Allowed (code) |
| `chatterbox-tts` 0.1.7 package | **MIT** | CONFIRMED (PyPI) | Allowed |
| EG checkpoint `model.safetensors` | **Apache-2.0 (stated)** | Stated on HF card; no LICENSE file sighted in repo listing | Likely allowed — VERIFY file at install time |
| Base Multilingual weights | Inherited from base repo (MIT-era project) — ASSUMED permissive, NOT separately sighted | UNKNOWN until checked | Unknown |
| Voice / speaker | No license found | UNKNOWN | Unknown |
| Training dataset ("120 h clean Egyptian") | No identifier, no license | UNKNOWN | Unknown |
| PyTorch / torchaudio | BSD-3-Clause | Well-established, HIGH confidence | Allowed |
| transformers / diffusers / safetensors / gradio / conformer / omegaconf | Apache-2.0 | Well-established, HIGH confidence | Allowed |
| librosa | ISC | Well-established | Allowed |
| `resemble-perth` (watermarker, git dep) | License file NOT read | UNKNOWN — must read before install | Unknown |
| `pykakasi` / `spacy-pkuseg` / `s3tokenizer` / `pyloudnorm` | NOT individually verified | UNKNOWN (CJK-only code paths for Arabic use, but still installed) | Unknown |

**Rule applied**: "open source repo" ≠ "all weights/voices/datasets permissive." No RED license found (nothing CPML, nothing NC), but the chain has UNKNOWN links → cannot be PREINSTALL_SAFE on license alone.

**Perth watermark note**: every Chatterbox output carries an imperceptible neural watermark (detectable via `perth` + `librosa`). Provenance-positive (outputs are attributable as AI-generated); no action needed, recorded for QC honesty.

## 4. Dependency matrix (pinned, from upstream `pyproject.toml` @ master)

| Package | Pin for our Python (3.11) | License (known) | Notes |
|---------|---------------------------|-----------------|-------|
| `torch` | `==2.6.0` | BSD-3 | CPU wheel exists for cp311/win64; default pip pulls CUDA build (~2.5 GB) — must use CPU index |
| `torchaudio` | `==2.6.0` | BSD-3 | Same wheel logic as torch |
| `numpy` | `>=1.24.0,<2.0.0` (py<3.13) | BSD-3 | **CONFLICT: Al-Montier venv has numpy 2.4.6** → separate venv mandatory |
| `transformers` | `==5.2.0` | Apache-2.0 | Major-version 5 line; pin as given |
| `diffusers` | `==0.29.0` | Apache-2.0 | — |
| `librosa` | `==0.11.0` | ISC | — |
| `safetensors` | `==0.5.3` | Apache-2.0 | — |
| `conformer` | `==0.3.2` | Apache-2.0 | — |
| `resemble-perth` | git master (unpinned!) | UNKNOWN | Needs git at install; unpinned moving target — pin commit at install time |
| `gradio` | `==6.8.0` | Apache-2.0 | Only needed for demo UI; skippable for headless test |
| `spacy-pkuseg`, `pykakasi`, `pyloudnorm`, `omegaconf` | as pinned | Mixed/UNVERIFIED individually | CJK paths unused for Arabic but installed regardless |
| `s3tokenizer` | unpinned | UNVERIFIED | Small audio tokenizer package |

`requires-python = ">=3.10"` → Python 3.11.9 compatible. Package itself is a pure-Python wheel (`py3-none-any`) → Windows-installable.

## 5. Windows / Python compatibility

| Check | Result |
|-------|--------|
| Windows 10 x64 | PLAUSIBLE — pure-Python wheel; upstream dev/tested on Debian 11 (Linux-first, no Windows CI found) |
| Python 3.11.9 | COMPATIBLE — upstream developed/tested on Python 3.11; `requires-python >=3.10` |
| torch 2.6.0 cp311 win_amd64 CPU wheel | EXISTS per PyTorch release matrix (verify with `pip index versions torch` at install time — read-only) |
| CUDA on 940MX | NOT VIABLE — 2 GB VRAM insufficient for 0.5B F32 + codec activations; modern torch/CUDA support for this GPU generation unverified; CPU-only is the only test path |
| CPU execution path | DOCUMENTED — upstream README: `device = "cuda"  # or "cpu" / "mps"`; multilingual loader accepts `device="cpu"` |

## 6. CPU / GPU feasibility

- **CPU (i7-7820HQ)**: technically possible (documented `device="cpu"`), practically SLOW. Author: "Requires GPU for real-time inference." Expect RTF > 1; test is a measurement, not production. → CPU worth a bounded single-sentence test: YES.
- **GPU (940MX 2 GB)**: UNSAFE for practical use (VRAM + driver/CUDA-generation doubt; even the card's own T4-class numbers assume real GPUs).

## 7. Disk / RAM analysis

| Item | Estimate |
|------|----------|
| C: free (measured, read-only) | **72.67 GB free** (114.69 GB used) |
| torch 2.6.0 CPU + torchaudio CPU | ~0.4 GB (via CPU index; default CUDA build would be ~2.5 GB — avoid) |
| Remaining pinned deps | ~1 GB |
| Base Chatterbox Multilingual weights | ~2 GB (HF cache) |
| EG checkpoint `model.safetensors` | ~2 GB |
| HF cache overhead / temp | ~1 GB |
| **Peak disk need** | **~6 GB** vs 72.67 GB free → **DISK_SAFE** |
| RAM working set (0.5B F32 CPU) | ~3–5 GB vs 16 GB → **RAM_POSSIBLE** (close other heavy apps during test) |
| VRAM | 2 GB, unusable → **GPU_UNSAFE** |

## 8. Isolation strategy (described, NOT created)

1. New venv: `tools/tts/chatterbox-eg/.venv` (Python 3.11, `--without-pip` avoided; standard venv).
2. Install torch CPU-first: `pip install --index-url https://download.pytorch.org/whl/cpu torch==2.6.0 torchaudio==2.6.0`, then `pip install chatterbox-tts==0.1.7 safetensors soundfile huggingface_hub` (skip `gradio`).
3. Pin `resemble-perth` to a recorded commit hash instead of `@master`.
4. Never install into Al-Montier `.venv` (numpy 2.4.6 vs required numpy<2.0 conflict). No PATH changes, no admin rights, no CUDA/driver changes, no touch to `tools/tts/piper/`, `F:\Arsenal`, or engine code.
5. Downloads restricted to: PyPI packages above + base weights + the single EG checkpoint file.

## 9. Risks

1. **Base-version drift**: upstream now ships Multilingual V3; the EG checkpoint (early-2026, V2-era T3) loads with `strict=False` — silent shape mismatch could degrade or break output. Mitigation: pin `chatterbox-tts` to a contemporary 0.1.x and record versions.
2. **Unpinned git dependency** (`resemble-perth@master`) — reproducibility + audit risk. Mitigation: pin commit hash.
3. **numpy conflict** with Al-Montier venv (2.4.6 vs <2.0) — mitigated by separate venv; installing into the project venv would break the video pipeline.
4. **CPU RTF unknown** — expected > 1; single-sentence test bounds the cost.
5. **License UNKNOWN links** (base weights file, voice, dataset, perth, CJK pkgs) — acceptable for a local validation test, must clear before any production/commercial use.
6. **Single-speaker, EG-only** checkpoint — weak on non-Egyptian text per card; test sentences must be Egyptian (Tests A–D).
7. **Default pip pulls CUDA torch (~2.5 GB)** — must use CPU index-url or disk/time wasted.

## 10. Unknowns

- Actual CPU RTF on i7-7820HQ (no published CPU numbers).
- Whether V2-era checkpoint loads cleanly under current `chatterbox-tts` 0.1.7 (strict=False masks mismatches).
- `resemble-perth`, `s3tokenizer`, `pykakasi`, `spacy-pkuseg` exact licenses.
- Base-weight file license text (assumed MIT-lineage, not sighted).
- Listening truth (no audio generated per task rules).

## 11. GO / NO-GO decision

**PREINSTALL_CONDITIONAL**

Rationale: no hard blocker found — disk is ample (72.67 GB free), RAM fits, Windows/Python compatibility is plausible with documented CPU path, isolation is straightforward, and no license is affirmatively prohibitive (nothing CPML, nothing non-commercial). But material uncertainties remain (checkpoint/base-version drift, UNKNOWN license links, unknown CPU RTF, Linux-first upstream), so a bounded, isolated validation test — not a production commitment — is the reasonable next step.

## 12. Exact next action

1. (Read-only, pre-install) Record the checkpoint repo's current commit hash and sight a license file for `resemble-ai/chatterbox` base weights + `resemble-perth`.
2. Then, only if step 1 is clean: create isolated venv `tools/tts/chatterbox-eg/.venv`, install torch 2.6.0 CPU via CPU index + `chatterbox-tts==0.1.7` (no gradio), download base weights + the single EG checkpoint, synthesize Test A only, measure wall-clock RTF and probe the WAV, and STOP for review before any further sentences or any pipeline work.

---

DECISION: PREINSTALL_CONDITIONAL
NEXT ACTION: Read-only license/revision sighting (base weights + perth + checkpoint commit), then bounded isolated install-test of Test A only.
INSTALLATION: NO
DOWNLOADS: NO
AL-MONTIER MODIFIED: NO
ARSENAL MODIFIED: NO
