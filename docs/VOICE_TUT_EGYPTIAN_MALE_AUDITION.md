# VoiceTut-TTS — Egyptian Male Narrator Audition Report

**Date**: 2026-09-22
**Status**: AUDITION_PARTIAL (see §12)
**Method**: Official public Space API (`mohammedaly22-voicetut-tts.hf.space/gradio_api`), endpoint `/run_b_oneshot`, identical settings for all voices (language Egyptian, steps 32, guidance 2.0, speed 1.0, normalize on). No installation, no local inference, no pipeline changes.
**Model source**: `mohammedaly22/VoiceTut-TTS` (Space app revision not version-pinned by host; model card as researched 2026-09-21).

---

## 1. Controlled audition script (identical for every voice)

"بص يا جماعة، الموضوع مش مجرد hype عابر. الذكاء الاصطناعي بدأ يدخل فعليًا في الـworkflow بتاع صناعة الفيديو، وده معناه إن الشغل اللي كان بياخد ساعات ممكن يخلص في وقت أقل بكتير. لكن في النهاية، الـcreative decision لسه عند الإنسان، والتكنولوجيا دي مجرد tool في إيده."

Coverage: Egyptian opening ✓ / low-key authoritative statement ✓ / technology-documentary sentence ✓ / AR→EN (hype, workflow) ✓ / EN→AR ✓ / embedded terms (AI, workflow, creative decision, tool) ✓ / calm conclusion ✓. ~25–40 s intended; actual Sayed output 16.53 s (brisk delivery).

## 2. Generation results (Phase 4)

| Voice | Generated | WAV | Duration | Note |
|-------|-----------|-----|----------|------|
| Sayed | YES | `tools/tts/voicetut-audition/wavs/voicetut_Sayed.wav` (775 KB) | 16.53 s, 24 kHz mono s16 | Full script completed |
| Abdelrahman, Abdullah, Kamal, Hossam, Mohamed, Omar, Zaki, Aly, Essam, Ahmed | NO | — | — | `run_b_oneshot` → instant `error/data:null` across ~2 h window (5 attempts incl. Sayed retest); `run_b_stream` probe same result |

Backend diagnosis: metadata endpoint (`preview_reference`) serves normally (11/11 voice metadata harvested, §3); both GPU generation endpoints reject instantly. Interpretation: Space GPU worker unavailable during the window (Sayed succeeded once at window start, then outage). Not voice-specific (Sayed retest also fails). Derivative third-party Spaces exist but were deliberately NOT used (untrusted mirrors). Local install was NOT attempted (task forbids huge local install; VoiceTut is GPU-gated anyway — see §9).

## 3. Author-documented style metadata (harvested live via preview_reference)

All genders filed male (ذكر ♂), matching `references.json`. Style chips are author documentation, NOT acoustic measurements:

| Voice | Style chips (author) | Reading for target |
|-------|----------------------|--------------------|
| Abdelrahman | محترف professional, حماسي enthusiastic | Professional fits; enthusiastic conflicts with calm |
| Abdullah | رسمي formal, محترف professional | Formal/professional adjacent to authoritative |
| Kamal | جاد serious, واضح clear | Serious fits restrained-authoritative |
| Hossam | دافئ warm, ودود friendly | Warm/friendly leans away from restrained |
| Mohamed | هادئ calm, عميق deep | **Direct tag match: calm + deep** |
| Omar | حكواتي storyteller, بطيء slow | Slow pace matches "من غير استعجال"; storyteller ≠ documentary |
| Sayed | شبابي youthful, معبّر expressive | Youthful conflicts with mature/old-school |
| Zaki | رزين dignified/grave, موثوق trustworthy | **Direct tag match: dignified + trustworthy** |
| Aly | هادئ calm, فخور proud | Calm fits; proud is neutral |
| Essam | (no tags documented) | Serious-register ref text only (INDIRECT) |
| Ahmed | (no tags documented) | Same shared text as Essam (INDIRECT) |

## 4. Sayed audition — technical evaluation (measured, not listened)

Agent limitation stated plainly: no human listened; this agent cannot audition audio. All character criteria below are UNKNOWN for acoustic reasons; technical criteria are measured.

| # | Criterion | Verdict | Evidence |
|---|-----------|---------|----------|
| 1 | Egyptian authenticity | UNKNOWN (acoustic) / PARTIAL (objective) | ASR (Whisper tiny, CPU) transcribed continuous Egyptian colloquial 0–16.4 s; author EG fine-tune |
| 2 | Male identity | PARTIAL | Gender filed male; voice acoustics unauditioned |
| 3–8 | Maturity, depth, calmness, authority, confidence, old-school | UNKNOWN | Documented tags say youthful/expressive (conflicts with target); unauditioned |
| 9–10 | Documentary / technology suitability | UNKNOWN | No use-case labels; unauditioned |
| 11 | Egyptian pronunciation | PARTIAL | ASR recovered Egyptian words (فعاليًا، بتاع، الشغل); tiny-model noise |
| 12 | English pronunciation | PARTIAL | ASR recovered "workflow→الورك الفلوب", "creative decision→الكرياتف دسجن", "tool→تول" at script-correct positions; "hype→حيب" misrecognized |
| 13–14 | AR→EN / EN→AR smoothness | PARTIAL (completion) / UNKNOWN (smoothness) | All 4 EN terms emitted in place (no skips/collapse); prosodic smoothness requires listening |
| 15 | Naturalness | UNKNOWN | Requires listening |
| 16 | Artifacts | PARTIAL | Levels clean (mean −17.1 dB, max −3.0 dB, 56 full-scale samples — minor edge touches, no sustained clipping); all samples finite |
| 17 | Robotic behavior | UNKNOWN | Requires listening |
| 18 | Overacting | UNKNOWN | Requires listening |
| 19 | Consistency | UNKNOWN | Single sample |

ASR transcript (Whisper tiny, noisy, positional evidence only): "وسجماع الموضوع مش مغارض حيب عبر / الزكاء الاستناء بدأ يدخل فعلياً في الورك الفلوب تاصنات الفيديو / وضمعنا ان الشغل اللي كان بياخت سعات ممكن يخلص فوات اقل بكتير / لكن في النهاية الكرياتف دسجن لسعاً للإنسان / والتكنولوجيا دي مغارض تول في إيضو" (5 segments, 0.0–16.4 s, lang ar p=1.0).

## 5. Other 10 voices — documentation-only evaluation

No audio generated (backend outage). Per-voice verdicts rest on filed gender + reference texts (all colloquial Egyptian, 6/11 natively code-switched) + style chips (§3). Character criteria: UNKNOWN (acoustic) except where tags speak: Mohamed calm/deep, Zaki dignified/trustworthy, Kamal serious, Aly calm — tag-level PARTIAL at most; tags describe intended character, not measured voice.

## 6. Target match per voice (Phase 6 — capability finding, NOT a ranking)

| Voice | Verdict | Basis |
|-------|---------|-------|
| Mohamed | PARTIAL_MATCH | Documented calm + deep tags directly match 2 target traits; Egyptian male filed; vocal realization unauditioned |
| Zaki | PARTIAL_MATCH | Documented dignified + trustworthy match authority-adjacent traits; unauditioned |
| Kamal | PARTIAL_MATCH | Documented serious; unauditioned |
| Aly | PARTIAL_MATCH | Documented calm; unauditioned |
| Omar | PARTIAL_MATCH | Documented slow pace matches unhurried feel; storyteller ≠ documentary |
| Sayed | PARTIAL_MATCH | Audio-confirmed Egyptian male + code-switch completion; documented youthful/expressive conflicts with mature/old-school |
| Abdullah | PARTIAL_MATCH | Formal/professional adjacent; unauditioned |
| Abdelrahman | PARTIAL_MATCH | Professional fits; enthusiastic conflicts with calm; unauditioned |
| Hossam | PARTIAL_MATCH | Male Egyptian confirmed; warm/friendly neutral-to-mismatched; unauditioned |
| Essam | UNKNOWN | Male Egyptian filed; no tags; serious-register ref text is INDIRECT only |
| Ahmed | UNKNOWN | Same as Essam |

No DOCUMENTED_MATCH (would require per-voice maturity/depth/authority documentation, absent) and no AUDITION_MATCH (would require listened audio) were reached.

## 7. Code-switching observations

Sayed's output emits all script English terms at correct positions inside Egyptian flow with no skips, long pauses (no ≥0.5 s silence), or collapse (ASR §4). Whether English keeps English phonetics vs Arabic-phonetic rendering, and whether prosody stays smooth across switches, is UNKNOWN without listening. Do not confuse this completion evidence with naturalness evidence.

## 8. Hardware reality (Phase 7)

No local inference attempted (Space path used; task forbids huge local install). Machine: Windows 10 Pro, i7-7820HQ, 16 GB, 940MX 2 GB. VoiceTut documented needs: ~2.93 GB VRAM fp16 on T4-class GPU; install path is CUDA-first; no CPU path documented → local GPU inference on 940MX is **LOCAL_HARDWARE_BLOCKED** in principle (2 GB < 2.93 GB need; CUDA-generation support unverified). Space-side: their GPU served 1 generation then errored for ~2 h (transient outage, not quota-verified). No CUDA hacks attempted; no drivers touched.

## 9. License observations (Phase 8)

No voice reached "promising audio" in the character sense (Sayed's audio exists but its documented character conflicts with target), so no per-voice clearance was triggered. Chain carries over from research: Apache-2.0 code + checkpoint (confirmed), training data + studio-voice rights UNKNOWN → commercial UNKNOWN. Sayed's WAV inherits the same unknown voice-rights status — audition use only, no production use.

## 10. Limitations

1. 10/11 voices unauditioned (transient Space GPU outage; Sayed control retest also failed → not voice-specific).
2. Zero human listening by anyone in this task — every character criterion is acoustic-UNKNOWN.
3. ASR evidence is Whisper-tiny-class (noisy) and positional only.
4. Space app revision unpinned (host-side; endpoints + model ID recorded).
5. One script, one settings set, one sample per voice design (Sayed n=1) — no consistency data.
6. Derivative Spaces unused (untrusted mirrors); local install not attempted per constraints.

## 11. Answer to the task question

"Did the actual VoiceTut male voices give us credible evidence of a mature, deep, calm, authoritative, old-school Egyptian male narrator who can naturally code-switch?" — **Partially, and only on paper**: Mohamed (calm+deep) and Zaki (dignified+trustworthy) carry author-documented tags matching core target traits; Sayed's audio objectively proves Egyptian male speech with same-utterance English-term completion. No listened evidence exists for any voice's actual vocal character, and 10/11 voices produced no audio in this window. The acoustic target remains unresolved pending human audition.

---

STATUS: AUDITION_PARTIAL
TIMESTAMP: 2026-09-22
SOURCE: Space mohammedaly22/VoiceTut-TTS (gradio_api run_b_oneshot/preview_reference), model mohammedaly22/VoiceTut-TTS, settings {Egyptian, steps 32, guidance 2.0, speed 1.0, normalize on}
VOICES_TESTED: Sayed (full audio+QC+ASR); 10 attempted with server-side instant errors (transient outage, Sayed retest also failing)
GENERATED_AUDIO: tools/tts/voicetut-audition/wavs/voicetut_Sayed.wav (16.53 s, 24 kHz mono s16) + sayed_asr.json
HUMAN_LISTENING: NONE (agent cannot listen; no human involved) — required before any character claim
EGYPTIAN_QUALITY_CONFIRMED: NO
NEXT_ACTION: Human audition of Sayed WAV + public demos (prioritize Mohamed, Zaki for documented calm/deep/dignified tags) with code-switched probes; retry generation when Space GPU recovers; clear data/voice rights before any production use
INSTALLATION: NO
DOWNLOADS: Project downloads NO (only generated-audio capture from public demo + pip-free stdlib calls)
AL-MONTIER MODIFIED: NO
ARSENAL MODIFIED: NO
