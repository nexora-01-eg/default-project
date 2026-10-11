# VoiceTut Mohamed — Production Validation Report

**Date**: 2026-09-22
**Status**: MOHAMED_VALIDATION_BLOCKED (official generation backend unavailable; no audio generated)
**Voice**: Mohamed (author tags: calm هادئ + deep عميق; human reference-clip note: "Closest so far — heavy/deep and calm")
**Test script (exact, unmodified, 303 chars)**:
"بص، الذكاء الاصطناعي دلوقتي مش مجرد tool بيساعدك تخلص الشغل أسرع. هو بدأ يغيّر الـworkflow نفسه، من أول الفكرة لحد الـfinal result. بس الـcreative decision في الآخر لسه محتاجة إنسان فاهم هو عايز يوصل لإيه. وعشان كده، استخدام الـAI صح مش معناه إنك تختفي من الصورة، بالعكس، معناه إنك تركز أكتر على القرار."

---

## 1. Official path verification (Phase 1)

Official Space API (`mohammedaly22-voicetut-tts.hf.space/gradio_api`, endpoint `run_b_oneshot`, identical documented settings: Egyptian, steps 32, guidance 2.0, speed 1.0, normalize on). Derivative mirrors deliberately unused. Two generation attempts (~10 min apart): both instant `error / data:null` (~1 s). Metadata endpoint healthy. Same failure signature as the 2026-09-22 audition session (10 voices + Sayed retest). Conclusion: Space GPU worker unavailable; failure is backend-side, not voice-, script-, or settings-specific. Retrying stopped per instruction (no indefinite retries, no voice switching).

Recovery probe (one-shot, later same day): `run_b_oneshot` Mohamed, identical settings — instant `error/data:null` (1.2 s). Backend still unavailable. No further retries.

## 2. Generation (Phase 2)

NOT PRODUCED. File `audition/voice_mohamed_production_test.wav` does not exist — no file fabricated. Exact error captured above. No styles experimented, no post-processing (nothing to process).

## 3. Objective QC + code-switching (Phases 3–4)

NOT APPLICABLE — no generated audio. Prior objective reference (for context only, different script): Sayed's 16.53 s output showed full-script completion with English terms emitted in place (ASR positional evidence), clean levels, no sustained clipping. That evidence does not transfer to Mohamed.

## 4. Hardware measurement (Phase 5)

No local inference performed (no installation per task constraints). Known machine: Windows 10 Pro, i7-7820HQ, 16 GB RAM, 940MX 2 GB. Documented VoiceTut requirements (T4 fp16: RTF 1.13, VRAM 2.93 GB; install path CUDA-first, no CPU path documented) exceed this machine's GPU → local GPU inference is **LOCAL_HARDWARE_BLOCKED** in principle; CPU inference would be orders of magnitude slower than Chatterbox's measured RTF 37.6 and was not attempted. No CUDA hacks, no driver changes, no large CUDA stack installed.

## 5. Local-install preflight (read-only, no installation performed)

Model `mohammedaly22/VoiceTut-TTS` (0.6B, ~2.5 GB) + OmniVoice backbone from GitHub + `voicetut-tts` (PyPI) + torch cu121 + ~7 GB total footprint; Python 3.10 documented path; Windows plausible but no CI; licenses Apache-2.0 code/checkpoint, training data + studio-voice rights UNKNOWN. Preflight verdict: install is technically possible but practically pointless here (GPU-gated workload, no usable GPU) — installation NOT performed, NOT recommended on this machine.

## 6. License check (Phase 6)

Code + checkpoint Apache-2.0 (confirmed); base OmniVoice Apache-2.0 (confirmed); training data (~380 h podcasts) UNKNOWN; Mohamed studio-voice rights UNKNOWN → commercial use UNKNOWN. No prohibition found; nothing cleared for production either.

## 7. Human listening sheet (Phase 7 — human fills after successful generation)

MOHAMED PRODUCTION TEST — HUMAN LISTENING

Egyptian accent feels natural:
[ HUMAN ]

Still feels heavy/deep:
[ HUMAN ]

Still feels calm:
[ HUMAN ]

Mature/authoritative impression:
[ HUMAN ]

Documentary/technology narrator feel:
[ HUMAN ]

English terms sound natural inside Egyptian Arabic:
[ HUMAN ]

Voice changes noticeably at language switching:
[ HUMAN ]

Robotic artifacts:
[ HUMAN ]

Would I accept this voice for Al-Montier narration:
[ HUMAN ]

Human notes:
[ HUMAN ]

## 8. Next action

Retry generation when the official Space GPU recovers (single probe first); on success, run QC+ASR and hand the WAV to the human with §7. Do not integrate regardless of outcome. Mohamed's candidacy stands on the human-approved reference clip + documented calm/deep tags; this production test remains the missing gate.

---

STATUS: MOHAMED_VALIDATION_BLOCKED
REASON: Official Space generation backend unavailable (2 instant-error attempts); local path hardware-blocked in principle and not attempted per constraints
AL-MONTIER MODIFIED: NO
ARSENAL MODIFIED: NO
