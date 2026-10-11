# VOICE_SELECTION_FORENSICS — hook_second_v1_20260924

**Status**: FORENSIC finding, read-only. No retries, no installs, no downloads performed.

## 1. Local Arabic voice inventory (measured, not assumed)

| Voice / engine | On disk? | Validated? | Dialect | Production-usable? | Blocker (if any) |
|---|---|---|---|---|---|
| Piper `ar_JO-kareem-medium` (`tools/tts/piper/`) | YES (exe + `.onnx` 60 MB + espeak data) | YES (`docs/PIPER_ARABIC_TTS_VALIDATION_REPORT.md`; re-verified 2026-09-24: 11 lines synthesized, isolated lines transcribe exactly) | Jordanian/MSA phonology | YES — the only one | None (working) |
| Chatterbox-EG `AliAbdallah/egyptian-arabic-tts-chatterbox` (`tools/tts/chatterbox-eg/`, isolated venv + 5 GB cache) | YES | BOUNDED-ONLY (`docs/EGYPTIAN_CHATTERBOX_BOUNDED_TEST.md`): one sentence, RTF **37.6** (88.7 s synth / 2.36 s audio) → CPU production unviable; Egyptian quality UNCONFIRMED (no listening); voice/dataset license UNKNOWN | claimed Egyptian, unverified | NO | R7 (38 min per 60 s narration) + R8/R9 (quality + rights unconfirmed) |
| VoiceTut "Mohamed" (remote HF Space) | NO local artifact; `audition_log.json`: 1 attempt → `error/data:null` in 1.0 s | NO (`docs/VOICE_TUT_MOHAMED_VALIDATION.md`: MOHAMED_VALIDATION_BLOCKED) | Egyptian (claimed) | NO | BLOCKED ×3: (a) Space GPU backend down; (b) local path hardware-blocked in principle (needs 2.93 GB VRAM, 940MX has 2 GB, no CPU path); (c) studio-voice rights UNKNOWN (audition-only) |
| VoiceTut "Sayed" (remote HF Space) | 1 WAV (`tools/tts/voicetut-audition/wavs/voicetut_Sayed.wav`, 16.53 s) | PARTIAL (audio exists; documented youthful/expressive tags conflict with mature target; rights unknown) | Egyptian (ASR-confirmed) | NO (rights + character + remote dependency) | R8 + remote-only |
| Windows SAPI | YES (David/Zira) | YES | en-US only | NO for Arabic | Wrong language |
| Any other Arabic TTS (Coqui/Melo/OpenVoice/Bark/…) | NO | NO | — | NO | Not installed |

**No engine/tts module exists** (`Test-Path engine\tts` → False). The only TTS
adapter in the codebase is `PiperAdapter` (`engine/tools/adapters/providers.py:87-112`),
hard-pinned to `tools/tts/piper/piper/piper.exe` + `ar_JO-kareem-medium.onnx`.
No Chatterbox adapter, no VoiceTut adapter, no voice-comparison function exists
anywhere (grep `voice` in adapters hits only PiperAdapter + VOICE_ACTIVITY).

## 2. Exact decision chain (reconstructed from `scripts/produce_hook_second_v1.py`)

1. Director hardcoded Piper: synthesis invoked via subprocess with fixed model
   path and `--length_scale 1.0`. No `router.resolve("TEXT_TO_SPEECH_AR")` call
   exists in the script (routing log records only CUT/MIX/BURN_CAPTIONS).
2. No voice enumeration step exists in the script, the planner
   (`engine/autonomy/director.py`), or the production contract. The planner
   never knew multiple voices existed: `plan_production()` takes
   `voice_source=""` as an opaque string and emits only BROLL + CAPTION_FONT
   requirement kinds.
3. Rate selection was empirical and logged in-session: `length_scale 0.6`
   output transcribed as Danish gibberish → rejected; `1.0` transcribed
   exactly (`ليه وقفت هنا`) → adopted for all 11 lines.
4. Mohamed was never a candidate at decision time: zero local audio, backend
   down, hardware-blocked locally, rights unknown. The production report states
   this explicitly; it is corroborated by `audition_log.json` and the
   validation report. "Ignoring the preferred Egyptian candidate" misdescribes
   the situation — there was no producible Mohamed artifact to ignore.
5. Chatterbox-EG was not evaluated by the production because its own validation
   report disqualifies it for CPU production (RTF 37.6 ⇒ ~43 min for this
   video's 69.24 s narration) with quality unconfirmed. Re-testing it would
   have changed nothing without a GPU (explicitly out of scope).

## 3. Findings

- **Why Kareem**: it is the intersection of {installed, validated, offline,
  Arabic-capable, production-speed}. The choice is correct given the inventory;
  the defect is that the choice was **hardcoded by the director, not routed**.
- **No fallback was logged** because no selection logic ran — there is no
  fallback to log. `classify_voice_mode()` only distinguishes NARRATED vs
  TEXT_DRIVEN; it knows nothing about voices.
- **Mohamed was explicitly BLOCKED in project docs**, never silently absent —
  but that BLOCKED state lives in markdown, not in any machine-readable voice
  registry the planner could read. A planner consulting only code/registry
  sees exactly one voice.
- **Human assessment verdict**: the complaint "ignored the larger voice
  arsenal / did not use Mohamed" is **factually incorrect** as a selection
  failure. The true gap is architectural: **no voice-selection capability
  exists** (R1), so future voices cannot be adopted without director
  hardcoding. Chatterbox-EG's non-use is justified by its own numbers, not
  oversight.
