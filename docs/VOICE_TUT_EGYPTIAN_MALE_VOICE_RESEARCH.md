# VoiceTut-TTS — Egyptian Male "Old-School / Authoritative" Narrator Research

**Date**: 2026-09-22
**Type**: RESEARCH ONLY — no installation, no downloads, no audio generated, no audition performed
**Target**: male Egyptian/Cairene narrator — mature, deep/low register, authoritative, confident, calm, restrained, old-school documentary/technology character; natural Egyptian↔English code-switching
**Authoritative sources used**: HF model card `mohammedaly22/VoiceTut-TTS`, GitHub repo `MohammedAly22/VoiceTuT-TTS` (Apache-2.0, 27 stars), `reference_speakers/references.json` (raw), base repo `k2-fsa/OmniVoice` (Apache-2.0, 13.7k stars). Note: `oaattia/VoiceTut-TTS` is marked "Duplicated from mohammedaly22/VoiceTut-TTS" — the mohammedaly22 lineage is authoritative.

---

## 1. Target Voice Definition

Egyptian (Cairene) male narrator: mature presence, naturally low register, authoritative + confident + calm, restrained intensity, experienced documentary/technology character. Explicitly NOT: cheerful, childish, energetic, assistant-like, robotic, MSA-generic, Levantine, Gulf, caricature, or imitation. Must code-switch Egyptian Arabic → English technical terms → Egyptian Arabic without collapse, accent-switch artifacts, or character change. Reference feeling: "راجل مصري كبير وهادي، صوته تقيل وواثق، بيتكلم من غير استعجال، عنده حضور، وكلامه محسوب."

## 2. VoiceTut Overview

Egyptian-Arabic TTS fine-tuned from `k2-fsa/OmniVoice` (Qwen3-0.6B text backbone + Higgs audio tokenizer) on ~380 h Egyptian-Arabic YouTube podcasts (`language_id = arz`); 20,000 steps, LR 3e-5, bf16. 0.6B params, safetensors, 24 kHz. Ships built-in studio voices (17 names on card; repo About text says 15 — discrepancy noted, not resolved), zero-shot cloning, Egyptian normalization pipeline (numbers/dates/currency/phones/emails/URLs/abbreviations, diacritics override table, EN→AR name map), true sentence streaming, `speed`/`num_step`/`guidance_scale` generation params, CLI (`voicetut --list-speakers`), Gradio UI with gender + style-tag dropdown. Install path is CUDA-first (`torch --index-url .../cu121` + OmniVoice from GitHub + `pip install voicetut-tts`).

## 3. Complete Male Voice Inventory

Source: card voice table + `references.json` (speaker_id, name, gender, reference clip, reference text). No age, pitch, or character fields exist per voice. Style tags (e.g. شبابي، حيوي، هادي) are documented only as Space-UI examples, not mapped to individual voices in any readable doc. Demos: DEMO_AVAILABLE for every voice (reference clip in repo + per-voice samples on demo page + live Space) — none downloaded or played in this task.

| Voice ID | Gender | Egyptian Evidence | Mature/Old-School Evidence | Deep/Low Evidence | Authority Evidence | Code-Switch Evidence | Style Controls | Evidence Level |
|----------|--------|-------------------|----------------------------|-------------------|--------------------|----------------------|----------------|----------------|
| Abdelrahman (spk_01_male) | Male (filed) | Egyptian ref text w/ EN mix ("appointment", "ابعتها") | None documented | None documented | None documented | Ref text itself code-switches | Fixed ref voice; speed param; cloning alt | STRONG_EVIDENCE (identity) / UNKNOWN (character) |
| Abdullah (spk_02_male) | Male (filed) | Egyptian ref text ("meeting", "التاسكات") | None | None | None | Ref text code-switches | Same | STRONG / UNKNOWN |
| Kamal (spk_03_male) | Male (filed) | Egyptian ref text, no EN in clip | None | None | None | Model-level only | Same | STRONG / UNKNOWN |
| Hossam (spk_04_male) | Male (filed) | Egyptian ref text, no EN in clip | None | None | None | Model-level only | Same | STRONG / UNKNOWN |
| Mohamed (spk_05_male) | Male (filed) | Egyptian ref text ("meeting", "budget") | None | None | None | Ref text code-switches | Same | STRONG / UNKNOWN |
| Omar (spk_06_male) | Male (filed) | Egyptian ref text, no EN in clip | None | None | None | Model-level only | Same | STRONG / UNKNOWN |
| Sayed (spk_07_male) | Male (filed) | Egyptian ref text ("location", "WhatsApp") | None | None | None | Ref text code-switches | Same | STRONG / UNKNOWN |
| Zaki (spk_08_male) | Male (filed) | Egyptian ref text, no EN in clip | None | None | None | Model-level only | Same | STRONG / UNKNOWN |
| Aly (spk_14_male) | Male (filed) | Formal-patriotic Egyptian text (no EN in clip) | Register reads serious — text only, NOT voice evidence | None | Register reads serious — text only | Model-level only | Same | STRONG / UNKNOWN (register is INDIRECT at most) |
| Essam (spk_16_male) | Male (filed) | Serious-register Egyptian text ("مفيهوش هزار يا جماعة") | Register reads grave — text only | None | Register reads grave — text only | Model-level only | Same | STRONG / UNKNOWN (register is INDIRECT at most) |
| Ahmed (spk_17_male) | Male (filed) | Same text as Essam (shared clip text) | Same as Essam | None | Same as Essam | Model-level only | Same | STRONG / UNKNOWN |

Female voices (excluded from target, listed for completeness): Asmaa, Esraa, Hanan, Sarah, Yasmin, Omnia — all gender-filed female with Egyptian code-switched reference texts.

No overall score. No ranking. No winner.

## 4. Voice/Style Evidence (per-dimension verdicts)

A. Egyptian dialect evidence: STRONG_EVIDENCE (Egyptian-first fine-tune on 380 h `arz` podcasts; all 11 male reference texts are colloquial Egyptian; `arz` language id). VERIFIED-grade paperwork, audio unauditioned by us.
B. Male voice evidence: VERIFIED (explicit `gender` field per voice in `references.json`; 11 male IDs).
C. Mature/old-school character evidence: UNKNOWN (no age/character metadata per voice; UI style tags unmapped).
D. Low/deep register evidence: UNKNOWN (no pitch metadata per voice).
E. Authority/confidence evidence: UNKNOWN (Essam/Ahmed/Aly reference *texts* are serious-register — text register is not vocal evidence: INDIRECT at most, not counted).
F. Calm delivery evidence: UNKNOWN (هادي appears only as an unmapped UI tag example).
G. Documentary suitability: UNKNOWN (no use-case labels per voice).
H. Code-switching evidence: VERIFIED at documentation level (same-utterance examples, see §6).
I. Voice consistency: UNKNOWN (no multi-sample consistency data read; speaker-similarity 0.83 reported for cloning, not for built-in voices).
J. Style/control capability: STRONG_EVIDENCE (fixed reference voices + `speed`/`num_step`/`guidance_scale` + zero-shot cloning path; base-model attribute instruct exists but is trained on Chinese+English only and flagged unstable for low-resource languages — NOT a reliable Egyptian character path).

## 5. Egyptian Dialect Evidence

Fine-tune data (~380 h Egyptian YouTube podcasts, `arz`), Egyptian normalization (colloquial clock: تلاتة و نص / تمانية الا ربع; Egyptian phone grouping; جنيه/دولار currency; EN→AR name map), Egyptian demo page and Space, 4 derivative Spaces. Counter-note: base OmniVoice covers 600+ languages with no Egyptian specialization — the Egyptian behavior comes entirely from the VoiceTut fine-tune. Dialect *quality* unauditioned by us.

## 6. Arabic-English Code-Switching Evidence

TRUE_CODE_SWITCHING at documentation level (not mere multilingualism): card shows same-utterance mixing (`عندي meeting بكرة`; `عندي meeting الساعة 3:30 ومعايا ال presentation`); 6 of 11 male reference texts natively mix English words (appointment, meeting, budget, location, WhatsApp); reported WER English 0.07 / Egyptian 0.40; normalization handles emails/URLs/names. Tokenizer/language-tag internals not documented — UNKNOWN at mechanism level. Whether English terms keep English phonetics inside Egyptian flow (vs Arabic-phonetic rendering) is undocumented in text and requires listening: STRONG_EVIDENCE on paper, unverified in audio by us.

## 7. Voice Cloning / Reference Audio Capability

Supported (documented, technical capability only — no real-person cloning instructions): 3–10 s reference clip per base docs ("a few seconds" per card), `ref_audio` + optional `ref_text` (Whisper fallback), identity + style carried by reference, dialect governed by fine-tuned text backbone, code-switching preserved insofar as the backbone handles it (unverified). Cloning path inherits the same GPU requirement below. Responsible-use guardrails documented (consent, no impersonation, disclosure).

## 8. Hardware Requirements

Authoritative numbers (T4 Colab, fp16, num_step=32): RTF mean **1.13×** (slower than real-time *on a T4*), best 0.49×, TTFA 1.68 s, peak VRAM **2.93 GB**, 0.6B params (~2.5 GB weights + torch stack ≈ 5–8 GB install). vs our context (Chatterbox measured RTF 37.6 / 7 GB peak on this CPU): VoiceTut is the heavier model class and starts slower even on GPU. Verdict for i7-7820HQ + 16 GB + 940MX: **GPU_REQUIRED** for practical use (2.93 GB VRAM need vs unusable 940MX); **CPU_POSSIBLE_BUT_LIKELY_SLOW** in principle (torch CPU + `device` mapping undocumented for VoiceTut; expected far slower than Chatterbox's 37.6×). Do NOT map T4 numbers onto the 940MX.

## 9. Windows/Python Compatibility

`pip install voicetut-tts` (PyPI) + OmniVoice from GitHub + torch cu121 per docs — all Windows-plausible (pure-Python packages), Python 3.10 path documented (3.11 likely fine, unverified), no Windows CI found, no CPU install path documented. UNKNOWN until a test install; must be isolated venv (OmniVoice pins torch 2.8.0 vs our sidenotes — keep away from Al-Montier venv regardless).

## 10. License Matrix

| Component | License | Status |
|-----------|---------|--------|
| VoiceTut code + checkpoint | Apache-2.0 | CONFIRMED (repo LICENSE + HF tag + PyPI badge) |
| Base `k2-fsa/OmniVoice` | Apache-2.0 | CONFIRMED (repo license footer) |
| Qwen3-0.6B lineage | Apache-2.0 | Well-established, HIGH confidence |
| Training data (~380 h YouTube podcasts) | UNKNOWN | No dataset identifier/license — must clear before commercial use |
| 17 studio voices (speaker rights/terms) | UNKNOWN | Consent/terms undocumented — must clear before commercial use |
| torch + deps | BSD/Apache/MIT-class | Standard, HIGH confidence |

Commercial use: UNKNOWN (permissive code/model licenses, but data + voice-rights links unresolved). "Open source" is not claimed for the data/voices.

## 11. Comparison With Chatterbox (documented facts only, no quality comparison, no winner)

| Fact | Chatterbox-EG (AliAbdallah, locally tested) | VoiceTut-TTS (this research) |
|------|----------------------------------------------|------------------------------|
| Egyptian evidence | Card-claimed features; 120 h; single speaker | 380 h `arz` podcasts; 17 studio voices; demos |
| Code-switching evidence | Not documented on card | Same-utterance examples + EN WER 0.07 |
| Male voices | 1 (single speaker) | 11 named + gender-filed |
| Style control | exaggeration/cfg/temperature | speed/num_step/guidance + fixed voices + cloning |
| Voice cloning | Audio-prompt cloning (generic) | Documented zero-shot path (3–10 s + optional text) |
| Model size | 0.5B | 0.6B |
| Measured/documented perf | RTF 37.6 CPU (measured), ~7 GB peak | RTF 1.13× on T4 GPU (documented); our-CPU unknown |
| License | No prohibition found; voice/data unknown | Apache-2.0 code+checkpoint; data/voices unknown |
| Windows/CPU | Runs on CPU (verified) | CPU path undocumented; GPU-first docs |

## 12. Unknowns

1. Per-voice age/pitch/character (no metadata; UI tags unmapped and unreadable without running the Space).
2. Actual vocal character of all 11 male voices (audition required; demos exist but unplayed per task rules).
3. English-phonetics preservation inside Egyptian utterances (listening required).
4. CPU RTF on i7-7820HQ; Windows install viability; exact install size.
5. Dataset license + studio-voice rights (commercial blockers until cleared).
6. 15-vs-17 voice count discrepancy (About text vs card table).
7. Whether `speed` < 1.0 + mature base voice can approximate the "unhurried" feel (speculative, untested).

## 13. Exact Next Action

Audition the existing public demos (demo page + Space, no install): shortlist male voices against the character brief (mature/low/calm/authoritative), with code-switched probes (the two task sentences), then clear dataset/voice-rights licensing before any install or production use. No installation, no cloning of real persons, no pipeline work.

---

STATUS: RESEARCH COMPLETE
TARGET VOICE: Egyptian male / mature / deep / calm / authoritative / old-school
VOICE TUT MALE VOICES: 11 named gender-filed voices (Abdelrahman, Abdullah, Kamal, Hossam, Mohamed, Omar, Sayed, Zaki, Aly, Essam, Ahmed), each with reference clip (DEMO_AVAILABLE, unauditioned); no per-voice age/pitch/character metadata
EGYPTIAN VOICE EVIDENCE: STRONG (380 h arz fine-tune, Egyptian refs/normalization/demos; audio unauditioned by us)
CODE_SWITCHING: TRUE_CODE_SWITCHING at documentation level (same-utterance examples, 6/11 male refs mix English, EN WER 0.07; phonetic preservation unverified)
VOICE_CLONING: Documented zero-shot path (3–10 s ref + optional text; GPU-gated like the rest; guardrails documented; no real-person instructions given)
HARDWARE: 0.6B; T4 fp16 RTF 1.13 / VRAM 2.93 GB documented → GPU_REQUIRED in practice; CPU_POSSIBLE_BUT_LIKELY_SLOW (expected worse than Chatterbox's measured 37.6×); 940MX not viable
LICENSE: Apache-2.0 code+checkpoint (confirmed); data + voice rights UNKNOWN → commercial UNKNOWN
KEY UNKNOWN: Which (if any) male voice actually sounds mature/deep/calm/authoritative — undocumented, listening required
MAIN QUESTION: PARTIALLY — male Egyptian voices AND code-switching are documented; the mature/deep/calm/authoritative character is NOT documented per voice
NEXT ACTION: Audition public demos/Space with character brief + code-switched probes; clear dataset/voice-rights licensing before install or production
INSTALLATION: NO
DOWNLOADS: NO
AUDIO GENERATED: NO
AL-MONTIER MODIFIED: NO
ARSENAL MODIFIED: NO
