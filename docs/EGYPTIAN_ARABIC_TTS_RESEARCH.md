# Egyptian Arabic TTS Research

**Date**: 2026-09-21
**Type**: RESEARCH ONLY — no installation, no downloads, no code changes
**Baseline**: Piper 2023.11.14-2 / ar_JO-kareem-medium (validated: works offline, RTF ~0.17–0.22, MSA/Jordanian, NOT Egyptian)

---

## 1. Executive Summary

**No verified Egyptian Arabic TTS exists locally.** No Egyptian voice exists in the official Piper catalog. No Egyptian TTS assets exist in F:\Arsenal (only Cairo *fonts* — typography, not speech). No Egyptian TTS is installed on this machine.

Web research found **multiple explicitly-Egyptian open-source TTS projects**, but **every one of them requires PyTorch + GPU-class hardware** and is therefore a poor fit for this specific machine (i7-7820HQ CPU-only, 16 GB RAM, GeForce 940MX 2 GB — no usable CUDA, no PyTorch installed).

**Honest bottom line:**

- **CANDIDATES THAT MEET ALL REQUIREMENTS (Egyptian + offline + runnable on this CPU today): NONE.**
- **Strongest dialect evidence**: VoiceTut-TTS (MohammedAly22) — Egyptian-first, Apache-2.0, 17 voices, paper-grade docs — but 0.6B transformer, RTF ~1.13× on a T4 GPU, i.e. **slower than real-time even on GPU**; CPU-only inference on this machine would be very slow.
- **Strongest academic evidence**: NileTTS-XTTS (KickItLikeShika) — peer-reviewed paper (arXiv 2602.15675), WER 26.8%→18.8% — but 5.8 GB, XTTS-v2 base under CPML (non-commercial), GPU-required.
- **Lightest-weight Egyptian options**: Chatterbox-based fine-tunes (AliAbdallah, NAMAA — 0.5B params, Apache-2.0/MIT) — still GPU-gated per their own model cards.
- **Correction to prior work**: MeloTTS does **not** support Arabic at all (EN/ES/FR/ZH/JP/KR only) and StyleTTS2 is English-only — both are NOT_EGYPTIAN, not candidates.

No "winner" is declared. Section 14 gives the tradeoff comparison.

---

## 2. Current Local Baseline

| Item | Value |
|------|-------|
| Engine | Piper 2023.11.14-2 (Piper 1.0.0), `tools/tts/piper/` |
| Voice | ar_JO-kareem-medium (60.3 MB ONNX, 22 050 Hz, 1 speaker) |
| Provenance | Hugging Face `rhasspy/piper-voices` → `ar/ar_JO/kareem/medium/`; dataset `AliMokhammad/arabicttstrain`; fine-tuned from US-English `lessac` |
| Measured performance | RTF 0.167–0.222 on i7-7820HQ CPU (5–6× real-time), fully offline |
| Dialect | Jordanian / MSA phonology. Egyptian colloquial (دلوقتي، تقدر، تعمل، لحد، زمان، محتاج، علشان) rendered with MSA phonology — no ج→g, no ق→ʔ |
| Verdict | **ARABIC_BUT_NOT_EGYPTIAN**. Retained as a future MSA backend; NOT an Egyptian solution |
| Voice license | NEEDS VERIFICATION (model card references dataset URL without stating a license) |
| Egyptian assets locally | NONE. Local Piper dir contains only ar_JO. Arsenal contains no TTS models |

Machine profile (from prior discovery): Windows 10 Pro x64, i7-7820HQ (4C/8T), 15.9 GB RAM, Intel HD 630 + GeForce 940MX (2 GB, no usable modern CUDA), Python 3.11.9 venv, onnxruntime 1.30.0, **no PyTorch**, FFmpeg 9.0.1.

---

## 3. What Counts as Egyptian Arabic

A model is only called Egyptian-capable with **speech evidence or explicit dialect metadata**:

- Explicit model card / paper / repo statement of Egyptian dialect training or Egyptian voice (→ VERIFIED).
- Multiple credible sources agreeing on Egyptian capability without complete official docs (→ STRONG_EVIDENCE).
- Arabic support with plausible-but-unproven Egyptian use (→ INDIRECT). **Never upgraded to VERIFIED.**
- Another dialect identified (→ NOT_EGYPTIAN).

Dialect signals checked: Egyptian realization of ج (g) and ق (ʔ); Cairene lexicon (دلوقتي، مش، بتعمل، تقدر، لحد، علشان، عايز، محتاج، بيغيّر); Egyptian prosody; speaker metadata (language_id `arz`).

Reference test sentences (conceptual only, never synthesized in this task):
- A: "دلوقتي تقدر تعمل فيديو كامل من مجرد فكرة."
- B: "الموضوع مش بس إن الذكاء الاصطناعي بيعمل الشغل أسرع."
- C: "لو عندك فكرة، تقدر تبدأ بيها وتحوّلها لفيديو."
- D: "أنا عايز أعمل فيديو بالمصري، مش بالعربي الفصحى."

---

## 4. Piper Investigation

**Verdict: NO_VERIFIED_EGYPTIAN_PIPER_VOICE_FOUND**

Evidence (authoritative):

- Official voice list `rhasspy/piper/VOICES.md`: Arabic entry is **only** `ar_JO` → `kareem` (low, medium). No `ar_EG`, no Egypt, no Cairo entry.
  - URL: https://github.com/rhasspy/piper/blob/master/VOICES.md
- `rhasspy/piper-samples/voices.json`: only key `ar_JO-kareem-low` (+ medium); region `JO`, country `Jordan`.
  - URL: https://github.com/rhasspy/piper-samples/blob/master/voices.json
- Official repo status: **archived Oct 2025**, development moved to `OHF-Voice/piper1-gpl`. No new official voices expected from rhasspy/piper.
- Community Piper-family voice found: `vadimbelsky/arabic-emirati-female-piper` (Hugging Face, MIT, 22050 Hz, Piper ONNX) — explicitly **Emirati** dialect, i.e. Gulf, NOT Egyptian.
  - URL: https://huggingface.co/vadimbelsky/arabic-emirati-female-piper
- Community anecdote (not evidence): a third-party `Siddiq-Sheikh/Piper-TTS-Test` repo calls ar_JO-kareem "the highest-quality Arabic model available for Piper" — confirms kareem's status as the Arabic flagship, not an Egyptian voice.

No Cairo/Egyptian/community-Egyptian Piper ONNX voice was found in the official catalog, Hugging Face search, or GitHub search.

---

## 5. Candidate Engines

| Engine | Arabic support | Egyptian support | Notes |
|--------|---------------|------------------|-------|
| Piper (VITS→ONNX) | ar_JO only | NONE (official) | CPU-native, MIT runtime. Only path that runs on this machine today |
| Coqui XTTS-v2 (GPT-style + voice cloning) | MSA/Gulf per NileTTS paper §5.1 | Via community fine-tunes only | Base: CPML (non-commercial). 1.8 GB base, GPU-gated |
| Chatterbox Multilingual (T3 + S3Gen, 0.5B) | Multilingual incl. Arabic | Via community fine-tunes (AliAbdallah, NAMAA) | Apache-2.0/MIT, GPU-gated per model cards |
| OmniVoice (Qwen3-0.6B + Higgs tokenizer) | Via VoiceTut fine-tune | VoiceTut-TTS (Egyptian-first) | Apache-2.0, GPU-gated (RTF 1.13× on T4) |
| F5-TTS (DiT flow-matching) | EN/ZH officially; community Arabic forks | Via MAdel121 fine-tune (research artifact) | MIT base; Egyptian ckpt CC BY-NC 4.0, GPU-gated |
| Fish Speech 1.4/1.5 (LLM-TTS) | Generic Arabic ~20k h | Only via voice-cloning reference | CC-BY-NC-SA-4.0 (non-commercial), GPU-gated |
| OpenVoice V1/V2 (tone converter) | No Arabic base speakers (MeloTTS EN/ES/FR/ZH/JP/KR) | Only via cloning an Egyptian reference | MIT, needs torch + base TTS + GPU |
| MeloTTS | **NONE — no Arabic at all** | NONE | MIT but irrelevant for Arabic |
| StyleTTS2 | English only | NONE | MIT but irrelevant |
| GPT-SoVITS | Via user fine-tune | No verified Egyptian checkpoint found | MIT, heavy, GPU-gated |
| Tacotron2 + HiFi-GAN (bluehybrid) | Egyptian-specific repo | Explicit Egyptian | 5 stars, Drive-hosted weights, CUDA-only code path |
| Qwen3-TTS 1.7B (hamdi-404) | Egyptian fine-tune | Explicit Egyptian | Apache-2.0, 1.7B params — far beyond this machine |

---

## 6. Candidate Models / Voices

### 6a. Explicitly Egyptian (VERIFIED or STRONG_EVIDENCE)

**V1. mohammedaly22/VoiceTut-TTS** — Evidence: VERIFIED
- Egyptian-first fine-tune of `k2-fsa/OmniVoice` on ~380 h Egyptian podcast speech (language_id `arz`); 17 built-in studio voices (male/female + style tags); zero-shot cloning; AR↔EN code-switching; Egyptian text normalization pipeline; true streaming.
- Metrics (self-reported, T4 GPU fp16): RTF mean 1.13× / best 0.49×; TTFA 1.68 s; peak VRAM 2.93 GB; WER Egyptian 0.40; UTMOS 3.47; 24 kHz.
- Size: HF repo ~7.38 GB (incl. optimizer); model.safetensors ~2.45 GB.
- License: Apache-2.0 (model + code). Provenance: GitHub `MohammedAly22/VoiceTuT-TTS`, PyPI `voicetut-tts`, HF Space demo + audio samples page.
- Deps: `pip install voicetut-tts` + OmniVoice from GitHub + PyTorch. No ONNX/CPU path documented.
- URLs: https://github.com/MohammedAly22/VoiceTuT-TTS · https://huggingface.co/mohammedaly22/VoiceTut-TTS · https://mohammedaly22.github.io/VoiceTuT-TTS

**V2. KickItLikeShika/NileTTS-XTTS** — Evidence: VERIFIED (peer-reviewed)
- XTTS-v2 fine-tune on NileTTS dataset (38 h, 2 speakers, medical/sales/conversation). Paper: "LLM-to-Speech" (arXiv 2602.15675, AbjadNLP 2026). WER 26.8%→18.8% (−29.9%), CER 8.1%→4.1% (−49.4%), speaker-sim +5.9%.
- Size 5.82 GB. License stated Apache-2.0 **but base `coqui/XTTS-v2` is CPML (non-commercial)** — commercial use is BLOCKED until clarified. Flag: LICENSE NEEDS VERIFICATION.
- Deps: `pip install TTS` (coqui-ai) + PyTorch + CUDA for practical use.
- URLs: https://huggingface.co/KickItLikeShika/NileTTS-XTTS · https://arxiv.org/abs/2602.15675 · https://github.com/KickItLikeShika/NileTTS

**V3. OmarSamir/EGTTS-V0.1** (`joejoe03/Egyptian-Text-To-Speech`) — Evidence: STRONG_EVIDENCE
- XTTS-v2 fine-tune explicitly for Egyptian Arabic (2024). 12 downstream Spaces. Inference via Coqui TTS + CUDA + DeepSpeed in docs.
- License: inherits CPML from XTTS-v2 base. Hardware: GPU-gated.
- URLs: https://huggingface.co/OmarSamir/EGTTS-V0.1 · https://github.com/joejoe03/Egyptian-Text-To-Speech

**V4. Mahmoudkandiel/EgyptianXTTSv2** — Evidence: STRONG_EVIDENCE
- XTTS-v2 fine-tune on ~15 h Egyptian YouTube speech (فيلم فى الخمسينة), 18k steps. Explicit Egyptian. Small repo (0 stars, 19 commits).
- License: CPML-inherited. Hardware: GPU-gated (Colab notebook flow).
- URL: https://github.com/Mahmoudkandiel/EgyptianXTTSv2

**V5. MoeEldouma/arabic-tts-xtts-v2** (+ `aungmoe/arabic-tts-xtts-v2` fork) — Evidence: STRONG_EVIDENCE
- XTTS-v2 fine-tune on `MAdel121/arabic-egy-cleaned` (72 h Egyptian ASR dataset); 4.9 h train subset documented; Egyptian speaker vs built-in-speaker ablations. Project MIT, **base CPML**.
- Hardware: GPU-gated. URLs: https://github.com/MoeEldouma/arabic-tts · https://huggingface.co/Moeeldouma/arabic-tts-xtts-v2

**V6. AliAbdallah/egyptian-arabic-tts-chatterbox** — Evidence: VERIFIED (explicit dialect features)
- Partial fine-tune of Chatterbox Multilingual (567M) on 120 h / 43.7k clips single-speaker Egyptian; card explicitly claims Egyptian pronunciation (ق→ء, ج→g), prosody, colloquial patterns. 24 kHz. Apache-2.0.
- Card states: "Requires GPU for real-time inference." Single speaker; weak on non-Egyptian text.
- URL: https://huggingface.co/AliAbdallah/egyptian-arabic-tts-chatterbox

**V7. NAMAA-Space/NAMAA-Egyptian-TTS** — Evidence: STRONG_EVIDENCE
- Chatterbox-based, MIT, Egyptian conversational dialect via configuration/prompting; reference-audio style transfer; GPU-accelerated inference documented. Community org (NAMAA).
- URL: https://huggingface.co/NAMAA-Space/NAMAA-Egyptian-TTS

**V8. MAdel121/f5-tts-egyptian-arabic** — Evidence: VERIFIED but QUALITY-LIMITED (author's own words)
- F5-TTS fine-tune of Habibi-TTS EGY on ~16 h Egyptian conversational; 5k/22k steps; UTMOS 2.63, WER 20.4%. Author notes MSA-dominant prior (85% MSA) resists dialect adaptation ("research artifact, not production"). **CC BY-NC 4.0 — non-commercial.** Training used ~54 GB VRAM/GPU.
- URL: https://huggingface.co/MAdel121/f5-tts-egyptian-arabic

**V9. hamdi-404 Egyptian-Arabic-Qwen3-TTS (itshamdi404/Egy_Arabic_Qwen3-TTS-12Hz-1.7B)** — Evidence: STRONG_EVIDENCE
- Qwen3-TTS 1.7B fine-tune for Egyptian (Abnudi-inspired data). Apache-2.0. 1.7B params — 3× larger than Chatterbox, far beyond this machine.
- URL: https://github.com/hamdi-404/Egyptian-Arabic-Qwen3-TTS-Egyptian-Dialect-Voice

**V10. bluehybrid/TTS_EgyptianArabic_Tacotron2** — Evidence: STRONG_EVIDENCE
- Tacotron2 + HiFi-GAN on EGYARA (MASRY TTS paper) data; camel_tools diacritization; Buckwalter transliteration. Weights via Google Drive; inference code calls `.cuda()` unconditionally. 5 stars, last commits 2024. Smallest architecture of the Egyptian set, but still GPU-bound and weakly maintained.
- URL: https://github.com/bluehybrid/TTS_EgyptianArabic_Tacotron2

### 6b. Fail the Egyptian requirement (NOT_EGYPTIAN)

- Piper ar_JO-kareem (baseline; Jordanian/MSA — validated locally).
- `vadimbelsky/arabic-emirati-female-piper` (Emirati/Gulf female Piper voice — wrong dialect family).
- XTTS-v2 base (MSA/Gulf Arabic per NileTTS paper).
- MeloTTS (no Arabic support whatsoever — prior candidate table erroneously listed Arabic; corrected here).
- StyleTTS2 (English-only checkpoints).
- F5-TTS base (EN/ZH; `IbrahimSalah/F5-TTS-Arabic` is generic Arabic, not Egyptian).
- Fish Speech 1.4/1.5 (generic `ar` ~20k h; Egyptian only conceivable via cloning a reference — INDIRECT at best).
- OpenVoice V1/V2 (no Arabic base speakers; Egyptian only via cloning — INDIRECT at best).
- GPT-SoVITS (no verified Egyptian checkpoint found — UNKNOWN).

---

## 7. Egyptian Dialect Evidence

| Candidate | Claimed Egyptian signals | Evidence level |
|-----------|--------------------------|----------------|
| VoiceTut-TTS | `arz` language id; 380 h Egyptian podcasts; Egyptian normalization; demo page VoiceTut-vs-OmniVoice | VERIFIED |
| NileTTS-XTTS | Peer-reviewed paper; 38 h Egyptian; WER/CER deltas on Egyptian eval set | VERIFIED |
| AliAbdallah Chatterbox-EG | Card: ق→ء, ج→g, Egyptian prosody/colloquial; 120 h Egyptian | VERIFIED |
| EGTTS-V0.1 | Explicit Egyptian fine-tune; 12 Spaces | STRONG_EVIDENCE |
| EgyptianXTTSv2 | 15 h Egyptian YouTube; audio samples in repo | STRONG_EVIDENCE |
| arabic-tts-xtts-v2 | Egyptian dataset + speaker ablations; demo wavs | STRONG_EVIDENCE |
| NAMAA-Egyptian-TTS | Egyptian dialect config + demo Space | STRONG_EVIDENCE |
| MAdel121 F5-TTS-EG | 16 h Egyptian conversational; author admits MSA leakage | VERIFIED but QUALITY-LIMITED |
| Qwen3-TTS-EG | Egyptian fine-tune statement; Abnudi-voiced data | STRONG_EVIDENCE |
| Tacotron2-EG | EGYARA dataset; MASRY paper lineage | STRONG_EVIDENCE |
| Piper ar_JO | Region JO/Jordan in official catalog | NOT_EGYPTIAN |
| Fish/OpenVoice generic | No Egyptian training; cloning only | INDIRECT |

No candidate was auditioned (research-only, no downloads). All "quality" statements above are the authors' own reported metrics/demos, not independent verification.

---

## 8. Hardware Feasibility (this machine: i7-7820HQ CPU, 16 GB RAM, no CUDA, no torch)

| Candidate | CPU | GPU | RAM | Verdict |
|-----------|-----|-----|-----|---------|
| Piper ar_JO (baseline) | GREEN (RTF 0.17 measured) | N/A (ONNX CPU) | GREEN (~200 MB) | GREEN — the only runnable option today |
| VoiceTut-TTS (0.6B) | RED (RTF 1.13× on T4 GPU → far slower on CPU) | RED (no CUDA; needs ~3 GB VRAM fp16) | YELLOW (~4–6 GB with torch) | RED on this machine |
| NileTTS-XTTS (5.8 GB) | RED (XTTS CPU RTF ≫ 1) | RED (no CUDA) | RED (6 GB weights + torch) | RED |
| EGTTS-V0.1 / EgyptianXTTSv2 / arabic-tts-xtts-v2 (XTTS family) | RED | RED | RED | RED |
| Chatterbox-EG / NAMAA (0.5B) | YELLOW→RED ("requires GPU for real-time" per card) | RED | YELLOW | RED for production use |
| F5-TTS-EG | RED | RED | RED | RED |
| Qwen3-TTS-EG 1.7B | RED | RED | RED | RED |
| Tacotron2-EG | YELLOW (small arch, CPU-possible in principle) | RED (code path `.cuda()`) | GREEN–YELLOW | YELLOW code-port needed; effectively RED as-is |
| Fish Speech (generic ar) | RED (RTF 1:5 needs RTX 4060) | RED | RED | RED |
| OpenVoice cloning | YELLOW (converter is light) but needs base TTS + torch | RED | YELLOW | YELLOW–RED, and INDIRECT evidence only |

Net: **no Egyptian-capable candidate is GREEN on this hardware.** The CPU-only ONNX envelope that makes Piper viable (~60 MB, no torch) has no Egyptian member.

---

## 9. Windows Feasibility

| Candidate | Windows |
|-----------|---------|
| Piper ar_JO | GREEN (verified: official `piper_windows_amd64.zip` runs) |
| VoiceTut-TTS | YELLOW (pure-Python + torch; Windows torch-CPU wheels exist, but OmniVoice GitHub dep + 7 GB weights + no Windows CI evidence) |
| XTTS family (Coqui TTS) | YELLOW–RED (Coqui TTS is Linux-first; Windows installs exist but fragile; +DeepSpeed/CUDA assumptions in EGTTS docs) |
| Chatterbox family | YELLOW (torch-based; Windows plausible, no Windows-specific docs found) |
| F5-TTS | YELLOW (pip package exists; docs assume CUDA/Linux/Docker) |
| Fish Speech | YELLOW (Windows GUI/API claimed; needs GPU to be useful) |
| Tacotron2-EG | RED (Linux-oriented training repo, Drive weights, `.cuda()` code) |

---

## 10. Offline Feasibility

All shortlisted candidates are architecturally offline-capable (local checkpoints, no API keys): Piper GREEN (verified); VoiceTut, NileTTS-XTTS, EGTTS, Chatterbox-EG, NAMAA, F5-TTS-EG, Qwen3-TTS-EG, Tacotron2-EG all GREEN *in principle* once weights are local. Fish Audio's hosted playground/API is online-only and out of scope — only the open weights count, which are CC-BY-NC-SA-gated anyway.

---

## 11. Quality Evidence

- VoiceTut-TTS: self-reported WER-Egyptian 0.40, UTMOS 3.47, speaker-sim 0.83; public demo page (VoiceTut vs base OmniVoice) and HF Space. Not independently verified.
- NileTTS-XTTS: peer-reviewed WER/CER deltas (29.9%/49.4% relative). Strongest independent-grade evidence in the set.
- AliAbdallah Chatterbox-EG: author-reported dialect feature list + demo Space. No numeric eval found.
- EGTTS-V0.1 / EgyptianXTTSv2 / arabic-tts-xtts-v2: repo audio samples + Space demos; no formal eval.
- MAdel121 F5-TTS-EG: UTMOS 2.63, WER 20.4% at 5k steps — author-declared research artifact.
- Piper kareem: locally validated intelligibility (MSA), RTF 0.17–0.22 — the only first-hand evidence in this whole report.

---

## 12. License / Provenance

| Candidate | Runtime | Model/Voice | Commercial use |
|-----------|---------|-------------|----------------|
| Piper ar_JO (baseline) | MIT (CONFIRMED) | NEEDS VERIFICATION (dataset URL only, no license stated) | UNKNOWN until voice cleared |
| VoiceTut-TTS | Apache-2.0 (CONFIRMED) | Apache-2.0 (CONFIRMED) | ALLOWED (per license text; still verify OmniVoice base terms) |
| NileTTS-XTTS | Coqui TTS (CPML) | Stated Apache-2.0 over CPML base — CONFLICT, NEEDS VERIFICATION | **BLOCKED until resolved** |
| EGTTS-V0.1 / EgyptianXTTSv2 / arabic-tts-xtts-v2 | Coqui TTS (CPML) | CPML-inherited | BLOCKED for commercial use |
| AliAbdallah Chatterbox-EG | Chatterbox (check base) | Apache-2.0 (stated) | LIKELY ALLOWED, verify base |
| NAMAA-Egyptian-TTS | Chatterbox (check base) | MIT (stated) | LIKELY ALLOWED, verify base |
| MAdel121 F5-TTS-EG | MIT (F5-TTS) | CC BY-NC 4.0 (CONFIRMED non-commercial) | BLOCKED for commercial use |
| Qwen3-TTS-EG | Apache-2.0 (Qwen3-TTS) | Apache-2.0 (stated) | LIKELY ALLOWED, verify |
| Tacotron2-EG | torch (BSD) + repo (unstated) | Drive weights, no license file found — LICENSE_UNKNOWN | UNKNOWN |
| Fish Speech weights | Apache-2.0 code | CC-BY-NC-SA-4.0 weights — non-commercial | BLOCKED for commercial use |
| Emirati Piper voice | MIT (Piper) | MIT (stated on HF) | ALLOWED but wrong dialect |

Rule applied throughout: an open-source *repository* does not make its *voice weights* commercially usable. Every commercial path above needs per-artifact clearance.

---

## 13. Arsenal Findings

**NO_EGYPTIAN_TTS_FOUND_IN_ARSENAL**

- Filename search (`egypt|ar_eg|ar-eg|cairo|masri`) over F:\Arsenal returned only **Cairo fonts** (Google Fonts `Cairo[slnt,wght].ttf` + webfont copies in lottie-hub / arsenal-gallery) — typography, not speech.
- No `tts|piper|melo|xtts|vits|openvoice|styletts|fish|sovits` model directories; no `.onnx` TTS voices; the only `.onnx` files remain `rembg` segmentation models; the only speech models remain Whisper `ggml-*.bin` (ASR).
- Local Piper dir contains only ar_JO (+ the new validation WAVs). Nothing Egyptian.
- Arsenal untouched (read-only inspection).

---

## 14. Candidate Comparison

| Candidate | Engine | Model / Voice | Dialect | Egyptian Evidence | Evidence Level | Offline | Windows | CPU | GPU | RAM | Speed | Quality Evidence | Long Form | WAV | License | Provenance | Integration Complexity | Validation Needed |
|-----------|--------|---------------|---------|-------------------|----------------|---------|---------|-----|-----|-----|-------|------------------|-----------|-----|---------|------------|------------------------|-------------------|
| Piper ar_JO (baseline) | Piper/VITS-ONNX | ar_JO-kareem-medium | Jordanian/MSA | Official catalog: JO | NOT_EGYPTIAN | Yes (verified) | GREEN (verified) | GREEN (RTF 0.17) | N/A | ~0.2 GB | FAST | Local validation | Yes | Yes | Runtime MIT; voice UNVERIFIED | HF rhasspy/piper-voices | LOW (already runs) | Voice-license clearance |
| VoiceTut-TTS | OmniVoice-finetune | mohammedaly22/VoiceTut-TTS | Egyptian (arz) | 380 h EG podcasts; demos | VERIFIED | Yes (in principle) | YELLOW | RED (RTF>1 on GPU) | RED (needs ~3 GB VRAM) | ~6 GB | SLOW on this hw | Self-reported + demos | Yes (streaming) | Yes | Apache-2.0 | GitHub+HF+PyPI, 2026 | MEDIUM (pip + torch + GH dep) | Install test; CPU RTF; listening; base-terms check |
| NileTTS-XTTS | XTTS-v2-finetune | KickItLikeShika/NileTTS-XTTS | Egyptian | Peer-reviewed paper + eval | VERIFIED | Yes (in principle) | YELLOW–RED | RED | RED | ~8 GB | SLOW | Paper WER/CER | Yes | Yes | CONFLICT (Apache claim over CPML base) | HF + arXiv 2602.15675 | HIGH (Coqui TTS + torch + CUDA) | License resolution; CPU RTF; listening |
| EGTTS-V0.1 | XTTS-v2-finetune | OmarSamir/EGTTS-V0.1 | Egyptian | Explicit EG fine-tune; Spaces | STRONG | Yes (in principle) | YELLOW–RED | RED | RED | ~8 GB | SLOW | Demos | Yes | Yes | CPML-inherited | HF + GitHub 2024 | HIGH | Listening; license; CPU RTF |
| EgyptianXTTSv2 | XTTS-v2-finetune | Mahmoudkandiel/EgyptianXTTSv2 | Egyptian | 15 h EG YouTube; samples | STRONG | Yes (in principle) | YELLOW–RED | RED | RED | ~8 GB | SLOW | Samples | Yes | Yes | CPML-inherited | GitHub 2025, tiny | HIGH | Listening; maintenance risk |
| arabic-tts-xtts-v2 | XTTS-v2-finetune | MoeEldouma (+aungmoe) | Egyptian | EG dataset + ablations | STRONG | Yes (in principle) | YELLOW–RED | RED | RED | ~8 GB | SLOW | Repo wavs | Yes | Yes | Project MIT / base CPML | GitHub+HF 2026 | HIGH | Listening; license |
| Chatterbox-EG | Chatterbox-finetune | AliAbdallah/egyptian-arabic-tts-chatterbox | Egyptian | Card: ق→ء, ج→g, prosody | VERIFIED | Yes (in principle) | YELLOW | YELLOW→RED | RED (GPU for RT) | ~4 GB | SLOW–MODERATE | Demos | Yes | Yes | Apache-2.0 (verify base) | HF 2026 | MEDIUM–HIGH | CPU RTF; listening; base terms |
| NAMAA-EG | Chatterbox-config | NAMAA-Space/NAMAA-Egyptian-TTS | Egyptian | EG dialect config + demo | STRONG | Yes (in principle) | YELLOW | YELLOW→RED | RED | ~4 GB | SLOW–MODERATE | Demo Space | Yes | Yes | MIT (verify base) | HF community 2026 | MEDIUM–HIGH | CPU RTF; listening |
| F5-TTS-EG | F5-TTS-finetune | MAdel121/f5-tts-egyptian-arabic | Egyptian (MSA leakage admitted) | 16 h EG conversational | VERIFIED but LIMITED | Yes (in principle) | YELLOW | RED | RED | ~8 GB | SLOW | UTMOS 2.63 / WER 20% | Yes | Yes | CC BY-NC 4.0 (non-commercial) | HF 2026 | HIGH | Quality; license blocks commercial |
| Qwen3-TTS-EG | Qwen3-TTS-finetune | hamdi-404 / itshamdi404 | Egyptian | EG fine-tune statement | STRONG | Yes (in principle) | YELLOW | RED (1.7B) | RED | ~10 GB | SLOW | None found | Yes | Yes | Apache-2.0 (stated) | GitHub/HF 2025–26 | HIGH | Listening; size |
| Tacotron2-EG | Tacotron2+HiFiGAN | bluehybrid | Egyptian | EGYARA/MASRY lineage | STRONG | Yes (in principle) | RED | YELLOW (small arch) | RED (`.cuda()`) | ~2 GB | MODERATE (?) | None found | Yes | Yes | LICENSE_UNKNOWN (Drive weights) | GitHub 2024, tiny | MEDIUM (code port) | License; port; listening |
| Fish Speech ar | Fish-LLM-TTS | fishaudio generic `ar` | Generic Arabic | ~20k h `ar`, no EG split | INDIRECT | Weights yes; API no | YELLOW | RED (needs RTX-class) | RED | large | SLOW | Benchmarks (EN/ZH) | Yes | Yes | CC-BY-NC-SA-4.0 | HF + GitHub | HIGH | Dialect; license blocks commercial |
| OpenVoice V2 | Tone-converter | Cloning only | None native | Cloning an EG ref only | INDIRECT | Yes | YELLOW | YELLOW | RED | ~4 GB | MODERATE | None for EG | Yes | Yes | MIT | GitHub myshell-ai | HIGH | Prove EG transfer |
| MeloTTS | — | — | None (no Arabic) | — | NOT_EGYPTIAN | — | — | — | — | — | — | — | — | — | MIT (irrelevant) | myshell-ai/MeloTTS | — | — |
| StyleTTS2 | — | — | English only | — | NOT_EGYPTIAN | — | — | — | — | — | — | — | — | — | MIT (irrelevant) | yl4579/StyleTTS2 | — | — |

---

## 15. Unknowns

1. Whether any **Egyptian Piper ONNX voice** exists outside the official catalog (community-trained VITS→ONNX ar_EG) — none found, but absence of evidence is not proof of nonexistence.
2. Actual **CPU RTF** of VoiceTut-TTS / Chatterbox-EG on an i7-7820HQ — no published CPU numbers; GPU numbers (1.13× / GPU-required) suggest impractical.
3. Whether **kareem's dataset license** permits production use — the single cheapest unblocking action in the whole report.
4. Whether the **NileTTS Apache-2.0 claim** can legally cover weights derived from CPML-licensed XTTS-v2.
5. Whether **Habibi-TTS EGY** (the base under MAdel121's ckpt) is itself a cleaner Egyptian starting point — noted but not investigated (out of minimum scope).
6. Listening-test truth for every candidate — no audio was downloaded or auditioned per task rules.

---

## 16. Validation Required Before Installation

For any candidate, in order:

1. **License clearance** — runtime + weights + dataset + base-model inheritance (especially XTTS family CPML, F5-TTS-EG/Fish non-commercial, kareem voice terms).
2. **Disk/RAM budget** — 8–12 GB free for torch + weights (VoiceTut ~7 GB repo; XTTS ~6 GB; Chatterbox ~2–4 GB + torch ~2 GB).
3. **Dependency audit** — PyTorch CPU wheel on Python 3.11/Windows; Coqui TTS Windows viability; OmniVoice GitHub dependency pinning.
4. **CPU RTF measurement** — Test A–D sentences, wall-clock RTF on this exact CPU; reject if RTF > 1 for narration workloads.
5. **Blind listening test** — Test A–D by an Egyptian speaker; check ج/ق realization, lexicon naturalness, prosody; compare against Piper kareem MSA baseline.
6. **QC compatibility** — 24 kHz outputs need `aresample` into the 44.1/48 kHz Al-Montier chain; duration non-determinism must feed probe-measured (not estimated) timeline spans.
7. **Provenance freeze** — record commit hash / revision of weights before any production use.

---

## 17. Integration Considerations

No integration is proposed. For the record, the existing architecture already accepts the shape any of these would produce:

- Director `classify_voice_mode(tts_available=True, tts_languages=("arz",))` → `NARRATED`; `plan_shots` caption behavior flips to narration-mirror; creative reviewer already checks the ~1.0 caption-density ratio for NARRATED mode.
- Renderer `mux()` + `gain_audio`/`fade_audio` consume any FFmpeg-decodable WAV; only addition needed is `aresample=48000` for 24 kHz/22.05 kHz TTS outputs and probe-measured durations.
- Estimated adapter effort IF a candidate validates: LOW for a WAV-producing CLI (Piper-class), MEDIUM for a Python-API model (VoiceTut/Chatterbox), HIGH for Coqui-TTS-stack models.

---

## 18. Final Research Conclusion

- **CANDIDATES THAT MEET REQUIREMENTS (Egyptian + offline + this CPU): NONE.** Stated plainly so no one misreads this report as an approval.
- **CANDIDATES WITH PARTIAL EVIDENCE (Egyptian, but blocked on hardware and/or license):** VoiceTut-TTS, NileTTS-XTTS, EGTTS-V0.1, EgyptianXTTSv2, arabic-tts-xtts-v2, AliAbdallah Chatterbox-EG, NAMAA-EG, MAdel121 F5-TTS-EG (also quality-capped by its own author), Qwen3-TTS-EG, Tacotron2-EG.
- **CANDIDATES THAT FAIL EGYPTIAN DIALECT REQUIREMENTS:** Piper ar_JO-kareem, Emirati Piper voice, XTTS-v2 base, MeloTTS, StyleTTS2, F5-TTS base, Fish Speech generic Arabic, OpenVoice (cloning-only hypothesis), GPT-SoVITS (no checkpoint).
- **CANDIDATES REQUIRING FURTHER VALIDATION:** every partial-evidence candidate above — license first, then CPU RTF, then blind Egyptian listening test (§16).

Practical reading: the cheapest genuine progress available is (a) clearing the **kareem voice license** for MSA work and (b) a single **CPU RTF + listening validation** of the lightest Egyptian claimants (Chatterbox-EG / NAMAA-EG, then VoiceTut-TTS) before spending any effort on the 6-GB XTTS family. A GPU remains the actual unblocker for production-grade Egyptian narration on this desk.

---

*End of report — research only. No installations, no downloads, no modifications performed.*
