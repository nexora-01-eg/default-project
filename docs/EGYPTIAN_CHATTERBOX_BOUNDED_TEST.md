# Egyptian Chatterbox TTS — Bounded CPU Test Report

**Date**: 2026-09-22
**Status**: VALIDATION_PASS_WITH_LIMITATIONS (bounded technical test succeeded; see limitations — this is NOT a quality endorsement)
**Candidate**: `AliAbdallah/egyptian-arabic-tts-chatterbox`
**Test sentence (exact, unmodified)**: "بص يا جماعة، النهارده هنتكلم عن حاجة مهمة جدًا."
**Scope**: ONE sentence, CPU-only, isolated venv. No pipeline integration, no video, no other voices.

---

## 1. License result

No concrete prohibition found. Verified read-only from authoritative pages:

| Component | License | Evidence |
|-----------|---------|----------|
| Checkpoint `model.safetensors` | Apache-2.0 (stated) | HF model page tag + card ("following Chatterbox base model license") |
| Base runtime `resemble-ai/chatterbox` (code) | MIT | CONFIRMED — repo license footer + PyPI `chatterbox-tts` 0.1.7 metadata |
| Base weights `ResembleAI/chatterbox` (HF) | MIT | CONFIRMED — model page "License: mit" |
| `resemble-perth` (watermarker) | MIT | CONFIRMED — repo license footer + LICENSE file present |
| torch/torchaudio/transformers/diffusers/safetensors/librosa | BSD / Apache-2.0 / ISC | Established (see pinned versions §4) |
| Voice / speaker, training dataset | UNKNOWN | No license or identifier on card — must clear before production/commercial use |

Commercial use: UNKNOWN (no prohibition, chain incomplete). Perth watermark note: all outputs carry an imperceptible neural watermark (PerthNet Implicit, step 250000, loaded at runtime).

## 2. Exact revision tested

- Repo HEAD: `5c2176d2f05964b35b3646c342d74dd0eeef76e8` ("Update README.md")
- Checkpoint blob commit: `ce4631f1cecfa649e5ad462c89d182794e617400` ("Initial upload - Egyptian Arabic TTS checkpoint")
- Files: `model.safetensors` **2,143,989,752 bytes**, `README.md`, `app.py`, `reference_audio.wav`, `sample_01/02/06.wav`, `requirements.txt`
- No LICENSE file in checkpoint repo; snapshot path pinned in local HF cache (see §13).

## 3. Installation environment

- Location: `tools/tts/chatterbox-eg/.venv` (isolated; Al-Montier venv, system Python, Arsenal, Piper install untouched)
- Python 3.11.9, pip 24.0 (stdlib bootstrap), no admin, no PATH changes, no drivers/CUDA changes
- torch installed from CPU index: `torch-2.6.0+cpu-cp311-cp311-win_amd64.whl` (206.5 MB — CUDA multi-GB build avoided)
- `torch.cuda.is_available()` → **False**; device explicitly `cpu`; torch threads 4 (default)
- Footprint: venv **2.04 GB** + HF cache **4.99 GB** = **7.02 GB** (+34.5 MB pkuseg tokenizer cache auto-downloaded to home dir `~/.pkuseg` — outside the isolated root, recorded here)

## 4. Dependency versions (as installed)

torch 2.6.0+cpu, torchaudio 2.6.0+cpu, chatterbox-tts 0.1.7, transformers 5.2.0, diffusers 0.29.0, safetensors 0.5.3, numpy 1.26.4, librosa 0.11.0, scipy 1.17.1, soundfile 0.14.0, huggingface_hub 1.32.0, resemble-perth 1.0.1 (PyPI wheel — not git master), gradio 6.8.0 (pulled by pin; unused headless).

## 5. Hardware used

Intel i7-7820HQ, 16 GB RAM, NVIDIA 940MX 2 GB (unused — no CUDA). Windows 10 Pro x64.

## 6. CPU benchmark

| Metric | Value |
|--------|-------|
| Base model load, first run (download-dominated) | 828.8 s (~13.8 min; 6 files incl. ~2 GB weights) |
| Base model load, cached | 35.6–46.0 s |
| Synthesis, Test A (foreground run) | **88.7 s** |
| Output duration | **2.36 s** (background run produced 2.92 s — durations are non-deterministic) |
| **RTF (synth/audio)** | **37.569** |
| T3 params | 535,989,248 |
| Checkpoint load | missing_keys 0, unexpected_keys 0 (clean strict=False load; installed 0.1.7 has no `t3_model` selector — its default base matches the checkpoint era) |
| Load vs synth dominance | Synthesis dominates (88.7 s vs 46.0 s cached load) |

RTF ≈ 38 means a 60 s narration would take ~38 min on this CPU. CPU production use is not viable; CPU remains a measurement path only.

## 7. RAM usage

- Peak working set during base-model load (Windows API, in-process): **≈ 6,960 MB (~7.0 GB)**, settling to ≈ 4.0 GB after load. (Raw `PROCESS_MEMORY_COUNTERS` fields read in swapped order during probing; corrected here: peak ≈ 7.0 GB, current ≈ 4.0 GB.)
- Verdict: **RAM_BORDERLINE** — fits in 16 GB but consumes >40%; close other heavy apps during any future run. System stayed stable throughout.

## 8. WAV properties

File: `tools/tts/chatterbox-eg/tests/testA_eg.wav` — pcm_s16le, **24,000 Hz, mono, 16-bit**, 2.36 s, ~140 KB (run 1: 2.92 s).

## 9. Technical QC

| Check | Result |
|-------|--------|
| Valid WAV / decodes clean | PASS (ffprobe OK, 56,640 samples) |
| Continuous audio | PASS — no silence ≥ 0.3 s at −40 dB |
| Clipping | PASS — max −3.0 dB, zero full-scale samples; mean −17.1 dB |
| NaN / invalid samples | PASS — all finite, peak abs 0.7068 |
| Abnormal duration | NOTE — 2.36 s (run 2) vs 2.92 s (run 1) for the same sentence; diffusion-sampling non-determinism, not an error per se |
| Decode errors | None |

## 10. Egyptian-dialect evidence limitations

- One short sentence cannot confirm dialect. No listening test performed (no audition capability in this task).
- Author claims (ق→ء, ج→g, Egyptian prosody) are documentation only — untested by us.
- **HUMAN_LISTENING_REQUIRED: YES. EGYPTIAN_QUALITY_CONFIRMED: NO.**

## 11. Human listening requirement

YES — an Egyptian speaker must blind-listen to `testA_eg.wav` (Tests A–D on any follow-up) checking ج/ق realization, lexicon naturalness, and prosody against the Piper kareem MSA baseline before any quality claim.

## 12. Problems encountered

1. `t3_model="v2"` rejected by installed 0.1.7 (kwarg doesn't exist) — dropped it; default base matches checkpoint era (fortunate, recorded).
2. Background-launch harness misread process state (poll loop saw 3.3 MB); recovered via foreground run. That run's WAV (2.92 s) is kept as run 1.
3. RAM probe bugs (ctypes 64-bit handle truncation → err 6; swapped struct fields) — fixed; corrected peak ≈ 7.0 GB.
4. Slow network (~300–500 KB/s): pip package set timed out once at 10 min, resumed to success; total downloads ≈ 7 GB over several hours.
5. `~/.pkuseg/spacy_ontonotes.zip` (34.5 MB) auto-downloaded outside the isolated root on first load.
6. HF symlink warnings on Windows (degraded cache, extra disk) — cosmetic.
7. Cangjie-mapping warning (Chinese tokenizer path) — cosmetic, irrelevant to Arabic.

Attempts accounting: torch install 1/1; package-set install 2 invocations (timeout + success, no dependency conflict); synthesis 2/2 (both produced valid WAVs). No crashes, no instability, no surprise CUDA dependency, no RAM-unsafe event. Within stop-condition limits.

## 13. Reproducibility instructions

1. `python -m venv tools/tts/chatterbox-eg/.venv` (Python 3.11), ensurepip.
2. `pip install --index-url https://download.pytorch.org/whl/cpu torch==2.6.0 torchaudio==2.6.0`, then `pip install "chatterbox-tts==0.1.7" safetensors soundfile huggingface_hub`.
3. `set HF_HOME=<abs path>/tools/tts/chatterbox-eg/hf_cache`.
4. Run `cb_test.py load_base | fetch_eg | synth` (script embeds Test A; revision pinned by snapshot dir `.../snapshots/5c2176d2f05964b35b3646c342d74dd0eeef76e8/`).
5. Probe WAV with ffprobe + `volumedetect` + `silencedetect` as in §9.

## 14. Exact next action

Egyptian-speaker blind listening of `tools/tts/chatterbox-eg/tests/testA_eg.wav` (no further synthesis, no integration). In parallel, treat RTF 37.6 as disqualifying CPU for production: the follow-up decision is GPU acquisition vs shelving local Egyptian narration — not more CPU tuning. Al-Montier and Arsenal remain untouched.

---

STATUS: VALIDATION_PASS_WITH_LIMITATIONS
LICENSE: No prohibition (MIT runtime/weights/perth confirmed; Apache-2.0 stated checkpoint; voice/dataset unknown)
REVISION: HEAD 5c2176d / checkpoint ce4631f / model.safetensors 2143989752 bytes
INSTALLATION: Isolated venv tools/tts/chatterbox-eg/.venv (Al-Montier venv untouched)
CPU: i7-7820HQ, torch 2.6.0+cpu, cuda=False, device=cpu
RTF: 37.569 (88.7 s synth / 2.36 s audio — CPU production not viable)
RAM: Peak ~7.0 GB during load (RAM_BORDERLINE); system stable
WAV: testA_eg.wav, 24 kHz mono s16, 2.36 s, valid
TECHNICAL_QC: PASS (no clipping, finite, continuous; durations non-deterministic across runs)
HUMAN_LISTENING_REQUIRED: YES
EGYPTIAN_QUALITY_CONFIRMED: NO
NEXT_ACTION: Blind Egyptian-speaker listening of testA_eg.wav; decide GPU vs shelve (no more CPU work, no integration)
AL-MONTIER MODIFIED: NO
ARSENAL MODIFIED: NO
