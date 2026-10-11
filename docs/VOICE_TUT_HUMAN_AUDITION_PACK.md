# VoiceTut Human Audition Pack — Egyptian Male Narrator Candidates

**Date**: 2026-09-22
**Status**: AUDITION_PACK_PARTIAL (reference-audio fallback; generation backend blocked — see §1)
**Target**: Egyptian male, mature, deep/low, calm, authoritative, confident, restrained, old-school documentary/technology narrator with natural Egyptian↔English code-switching.

---

## 1. Backend status + limitation (read first)

- Generation endpoints (`run_b_oneshot`, `run_b_stream`) on the official Space returned instant `error/data:null` for every request in this window (Mohamed probe + prior session incl. Sayed retest). Metadata endpoint healthy.
- Per task instruction, no hours-long retrying. This pack therefore uses **official public reference clips** (`reference_speakers/` from `MohammedAly22/VoiceTuT-TTS`, GitHub raw), NOT the controlled test script below.
- Consequence: each voice speaks **different text** (its own reference sentence). Cross-voice character comparison is valid (same speaker identity per file); code-switch smoothness against the controlled script is NOT testable from this pack — that requires generation once the backend recovers.
- Optional control (existing, different script): `tools/tts/voicetut-audition/wavs/voicetut_Sayed.wav` (Sayed, youthful/expressive per tags — use only as a contrast reference, not a candidate).

## 2. Controlled test script (for generation once backend recovers — NOT yet recorded)

"بص، الذكاء الاصطناعي دلوقتي مش مجرد tool بيساعدك تخلص الشغل أسرع. هو بدأ يغيّر الـworkflow نفسه، من أول الفكرة لحد الـfinal result. بس الـcreative decision في الآخر لسه محتاجة إنسان فاهم هو عايز يوصل لإيه. وعشان كده، استخدام الـAI صح مش معناه إنك تختفي من الصورة، بالعكس، معناه إنك تركز أكتر على القرار."

## 3. Pack contents

Dir: `tools/tts/voicetut-audition/audition/`

| File | Voice | Documented tags | Source | Duration | Format | Mean / Max level | Clipping | Long silences | ASR (tiny, positional only) |
|------|-------|-----------------|--------|----------|--------|------------------|----------|---------------|------------------------------|
| `voice_mohamed.wav` | Mohamed | calm (هادئ), deep (عميق) | official ref clip | 7.81 s | 44.1 kHz mono s32 | −19.3 / −3.1 dB | None | None ≥0.5 s | Continuous EG; "meeting→ميتين", "budget→البادجت" recovered — clip itself code-switches |
| `voice_zaki.wav` | Zaki | dignified (رزين), trustworthy (موثوق) | official ref clip | 7.20 s | 44.1 kHz mono s32 | −18.7 / −1.4 dB | None | None ≥0.5 s | Continuous EG colloquial |
| `voice_kamal.wav` | Kamal | serious (جاد), clear (واضح) | official ref clip | 8.24 s | 24 kHz mono s16 | −14.1 / −0.8 dB | 3 full-scale samples (negligible) | None ≥0.5 s | Continuous EG colloquial |
| `voice_aly.wav` | Aly | calm (هادئ), proud (فخور) | official ref clip | 8.53 s | 24 kHz mono s32 | −18.1 / −2.3 dB | None | None ≥0.5 s | Continuous EG, formal register |
| `voice_omar.wav` | Omar | storyteller (حكواتي), slow (بطيء) | official ref clip | 11.73 s | 44.1 kHz mono s32 | −22.3 / −1.6 dB | None | None ≥0.5 s | Continuous EG colloquial |

All files: valid WAV, finite samples, decode clean. ASR is Whisper-tiny (noisy) — used only to confirm continuous speech + English-term presence, never as quality evidence. Full transcripts: `audition/audition_asr.json`.

## 4. Human evaluation sheet (listener fills; agent filled nothing subjective)

"Listen with headphones if possible. Do not judge the voice from metadata. Judge only what you actually hear."

Specifically watch for:
- Does the voice actually sound mature?
- Does it feel naturally low/deep rather than artificially bass-heavy?
- Does it sound calm without becoming sleepy?
- Does authority come from the voice naturally?
- Does it sound like a serious Egyptian narrator?
- Does English remain natural inside Egyptian Arabic?
- Does the voice become noticeably different when switching languages?
- Does it sound synthetic or overly expressive?
- Could you listen to this voice for 60–90 seconds without fatigue?

| Voice | Egyptian authenticity | Depth | Maturity | Calmness | Authority | Old-school character | Documentary feel | Technology narrator feel | English pronunciation | Arabic→English switching | English→Arabic switching | Naturalness | Robotic artifacts | Overall personal impression | Notes |
|-------|----------------------|-------|----------|----------|-----------|---------------------|------------------|--------------------------|----------------------|--------------------------|--------------------------|-------------|-------------------|-----------------------------|-------|
| Mohamed | [ HUMAN LISTENER ] | [ HUMAN LISTENER ] | [ HUMAN LISTENER ] | [ HUMAN LISTENER ] | [ HUMAN LISTENER ] | [ HUMAN LISTENER ] | [ HUMAN LISTENER ] | [ HUMAN LISTENER ] | [ HUMAN LISTENER ] | [ HUMAN LISTENER ] | [ HUMAN LISTENER ] | [ HUMAN LISTENER ] | [ HUMAN LISTENER ] | [ HUMAN LISTENER ] | [ HUMAN LISTENER ] |
| Zaki | [ HUMAN LISTENER ] | [ HUMAN LISTENER ] | [ HUMAN LISTENER ] | [ HUMAN LISTENER ] | [ HUMAN LISTENER ] | [ HUMAN LISTENER ] | [ HUMAN LISTENER ] | [ HUMAN LISTENER ] | [ HUMAN LISTENER ] | [ HUMAN LISTENER ] | [ HUMAN LISTENER ] | [ HUMAN LISTENER ] | [ HUMAN LISTENER ] | [ HUMAN LISTENER ] | [ HUMAN LISTENER ] |
| Kamal | [ HUMAN LISTENER ] | [ HUMAN LISTENER ] | [ HUMAN LISTENER ] | [ HUMAN LISTENER ] | [ HUMAN LISTENER ] | [ HUMAN LISTENER ] | [ HUMAN LISTENER ] | [ HUMAN LISTENER ] | [ HUMAN LISTENER ] | [ HUMAN LISTENER ] | [ HUMAN LISTENER ] | [ HUMAN LISTENER ] | [ HUMAN LISTENER ] | [ HUMAN LISTENER ] | [ HUMAN LISTENER ] |
| Aly | [ HUMAN LISTENER ] | [ HUMAN LISTENER ] | [ HUMAN LISTENER ] | [ HUMAN LISTENER ] | [ HUMAN LISTENER ] | [ HUMAN LISTENER ] | [ HUMAN LISTENER ] | [ HUMAN LISTENER ] | [ HUMAN LISTENER ] | [ HUMAN LISTENER ] | [ HUMAN LISTENER ] | [ HUMAN LISTENER ] | [ HUMAN LISTENER ] | [ HUMAN LISTENER ] | [ HUMAN LISTENER ] |
| Omar | [ HUMAN LISTENER ] | [ HUMAN LISTENER ] | [ HUMAN LISTENER ] | [ HUMAN LISTENER ] | [ HUMAN LISTENER ] | [ HUMAN LISTENER ] | [ HUMAN LISTENER ] | [ HUMAN LISTENER ] | [ HUMAN LISTENER ] | [ HUMAN LISTENER ] | [ HUMAN LISTENER ] | [ HUMAN LISTENER ] | [ HUMAN LISTENER ] | [ HUMAN LISTENER ] | [ HUMAN LISTENER ] |

No numbers, no ranking, no score, no winner — by instruction.

## 5. Suggested listening order (not a ranking)

Omar (longest sample, slow tag) → Mohamed (calm+deep tags) → Zaki (dignified+trustworthy tags) → Kamal (serious tag) → Aly (calm tag). Optional contrast last: Sayed control (youthful/expressive).

---

STATUS: AUDITION_PACK_PARTIAL
NEXT_ACTION: Human listens and fills §4; on Space GPU recovery, generate §2 script identically for all five voices and re-issue pack as AUDITION_PACK_READY
INSTALLATION: NO
DOWNLOADS: Reference-clip capture from official public repo only (no models, no packages)
AL-MONTIER MODIFIED: NO
ARSENAL MODIFIED: NO
