# Egyptian Arabic TTS — Next Action Decision

**Date**: 2026-09-21
**Type**: READ-ONLY DECISION — no installation, no downloads, no code changes, no inference
**Source**: `docs/EGYPTIAN_ARABIC_TTS_RESEARCH.md` (§6 V6, §7, §8, §12, §14, §16, §18)

---

## 1. Single candidate with the lowest practical installation and hardware risk

`AliAbdallah/egyptian-arabic-tts-chatterbox` (Chatterbox Multilingual fine-tune for Egyptian Arabic).

This is a scoping statement about test cost and risk, not a quality endorsement. No candidate in the report is GREEN on this hardware; this one has the smallest test footprint among the VERIFIED-evidence Egyptians and the fewest license red flags.

## 2. Exact repository / model

- Checkpoint: `AliAbdallah/egyptian-arabic-tts-chatterbox`
  - URL: https://huggingface.co/AliAbdallah/egyptian-arabic-tts-chatterbox
  - File: `model.safetensors` (fine-tuned T3 checkpoint, loaded over base Chatterbox Multilingual TTS)
- Base engine: Chatterbox Multilingual TTS (T3 transformer + S3Gen codec, 0.5B params, 24 kHz), installed via `chatterbox-tts` package
- Training claim: 120 h / 43,711 clips single-speaker Egyptian Arabic; partial fine-tune (prosody predictors + late acoustic decoder)

## 3. Egyptian dialect evidence: direct, indirect, or unverified?

**Direct by documentation, unverified by independent test.**

The model card explicitly claims Egyptian dialect training and Egyptian pronunciation features (ق→ء, ج→g, Egyptian prosody and colloquial patterns) — this is author-stated dialect metadata, which meets the report's VERIFIED bar for *documentation*. However, no independent listening test has been performed (research-only task, nothing downloaded or auditioned), so real dialect quality remains **unverified by us**. Vocabulary alone is not taken as proof.

## 4. Exact runtime license

**Not established.** The research did not confirm the license of the Chatterbox base runtime (`chatterbox-tts` package / `ResembleAI/chatterbox`). Recorded as CHECK-BASE in the report. Must be read from the base repository's license file before any installation.

## 5. Exact model / voice / dataset license

- Checkpoint: **Apache-2.0 (stated on the Hugging Face model card)** — stated, not yet independently verified against a license file in the repo.
- Voice/speaker: single speaker, no separate voice license found — UNKNOWN.
- Training dataset: described only as "120 hours of clean Egyptian Arabic," no dataset identifier or dataset license found — UNKNOWN.

## 6. Commercial use: allowed, prohibited, or unknown?

**UNKNOWN.** The checkpoint's stated Apache-2.0 points toward allowed, but commercial use cannot be confirmed until (a) the base runtime/base-model license is read and (b) base-weight inheritance is checked. It is *not* in the prohibited column (unlike XTTS-family CPML and CC BY-NC-SA / CC BY-NC 4.0 weights), which is part of why it is scoped first — but "not prohibited" is not "allowed."

## 7. Estimated download size

~4 GB total: checkpoint ~1–2 GB (0.5B params, safetensors F32) + PyTorch CPU ~2 GB + `chatterbox-tts` package and small dependencies. Per-report budget class: Chatterbox ~2–4 GB + torch ~2 GB.

## 8. Minimum RAM and GPU requirements

- RAM: ~4 GB working set (model + torch CPU), within the 16 GB available — YELLOW (feasible, unverified).
- GPU: the model card states **"Requires GPU for real-time inference."** The local 940MX (2 GB, no usable modern CUDA) does not qualify. Real-time GPU inference is therefore **not available**; only CPU-timed measurement is in scope.

## 9. Is CPU-only inference realistically worth testing on i7-7820HQ / 16 GB / 940MX 2 GB?

**Yes — as a bounded measurement, not as production use.** Expectation is SLOW (RTF > 1 on CPU, given the card's own GPU requirement). The test's value is a decisive number: one short sentence (Test A), wall-clock RTF, plus a planned Egyptian-speaker listening check. A single slow result rejects the CPU path cheaply; an unexpectedly usable result would change the hardware calculus. Either outcome is informative for under ~4 GB of disk and under an hour.

## 10. Precise reason to test this candidate before the others

It is the only candidate combining all four of: (a) VERIFIED-level documented Egyptian dialect claims with testable phonological predictions (ق→ء, ج→g); (b) smallest weight class among VERIFIED Egyptians (0.5B vs 0.6B–1.7B vs 5.8 GB XTTS); (c) no known license prohibition (Apache-2.0 stated, vs CPML-inherited XTTS family and CC non-commercial F5-TTS/Fish weights); (d) pip-installable base with no GitHub-source dependency (vs OmniVoice-from-GitHub), no Coqui/DeepSpeed stack, and no Drive-hosted weights. That makes it the cheapest decisive experiment: one install, one RTF number, one listening verdict, fastest reject-or-continue signal.

## 11. Conditions that would reject it without installation

- The Chatterbox base runtime or base weights license turns out to be non-commercial, copyleft-incompatible with our use, or otherwise restrictive.
- The checkpoint or its loader requires CUDA-only ops with no CPU execution path.
- No PyTorch CPU wheel is available for Python 3.11 on Windows 10.
- Free disk on the project drive is under 8 GB at check time.
- The checkpoint revision disappears, is replaced by an MSA-oriented file, or the author corrects the dialect claim.
- Commercial narration is required and base-license inheritance cannot be documented as permissive.

## 12. Next single safe action

Read-only verification, no download: open the Chatterbox base repository license file, the checkpoint repository's license file and pinned revision, and the PyTorch CPU-wheel availability for Python 3.11 / Windows, and confirm ≥ 8 GB free disk — then either proceed to a bounded install-test or record the rejection reason. Nothing else.

---

DECISION: AliAbdallah/egyptian-arabic-tts-chatterbox is the single lowest-risk candidate for a bounded validation test (direct-by-documentation Egyptian claims, ~4 GB footprint, Apache-2.0 stated, no known prohibition); all other Egyptians are heavier, license-blocked, or weaker-evidenced. No quality endorsement is made.
NEXT ACTION: Read-only license + dependency verification (base runtime license, checkpoint license/revision, torch CPU wheel for py3.11/Windows, disk space) before any installation.
INSTALLATION: NO
DOWNLOADS: NO
AL-MONTIER MODIFIED: NO
ARSENAL MODIFIED: NO
