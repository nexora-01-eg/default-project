# Blind Autonomous Production Report

**Final status**: CREATIVE_PASS_WITH_LIMITATIONS
**Final video**: `projects/blind_social_v1_20260925/renders/blind_social_20260925_024502.mp4`
**Duration**: 72.51 s (60–90 ✓) · **Resolution**: 1080×1920 · **FPS**: 30 · H.264 + AAC 44.1 kHz stereo.

## Concept → story (director-owned)

Concept (hook-vs-scroll) → 8 beats (HOOK/QUESTION/PROBLEM/EXPLANATION/EXAMPLE/ESCALATION/PAYOFF/ENDING) → narration timed first (measured Piper physics), headlines/visuals carry interstitial meaning. No human storyboard/script/shot-list input.

## Voice / narration

Strongest validated LOCAL narrator: Piper ar_JO kareem (TEMPORARY, NOT_EGYPTIAN — VoiceTut not retried per instructions). Narration-first edit around measured timing: S1 "أول ثانية تحسم." 34.187 s @1.5, S2 "الفضول يكسب." 28.37 s @36.2. Both peak 0.0 dB (full-scale touches noted; mix dilutes; final peak −6.4 dB).

## Shots / assets / motion / camera

18 shots from plan_shots_diverse (seed 11) + 1 pre-render hook repair (montage split) = 20 timeline segments; 16 motion/camera decisions logged (push/hold/cut/slide × static/push/pan, state-mapped, no mechanical rotation); 8 distinct Arsenal files (neon/code/keys/macbook/startup/handshake/dubai/planning), all verified clean by multi-frame inspection; 0 mismatches across 20 manifest entries (cover/zoompan/zoompan-x executed from planner records).

## Captions / headlines / graphics

Verbatim narration cues (midpoint split, documented) + 6 keywords + title/endcard; max 2 layers; RTL verified correct incl. mixed-script frame; no tofu. Headlines carry story beats. Procedural: title/key/end cards (Pillow) + hook montage. No SVG-raster/stat-card in this cut (capability noted, unused by director choice).

## Music / SFX

Aitech bed (CC-BY) with story-state ducking; one hook sting −12 dB with documented purpose. Mean −26.6 dB / peak −6.4 dB, no clipping, no ≥1 s silences, A/V offset 0.25 s.

## QC results

Streams/duration/codecs PASS; sync PASS; levels PASS (quiet-but-safe); black frames intentional-only; 7 frames inspected (title/hook/problem/code/payoff/closing/endcard all correct).

## Reviewers

- reviewer2: REVIEW (hook PASS post-repair; residual 2× reuse REVIEWs).
- creative: REVIEW (repetition heuristic only).
- quality_score: 1.0 PASS, zero critical FAILs.

## Repair rounds

Pre-render: 1 (hook montage split, logged). Post-render: 0. One false alarm handled honestly: two frames initially misread as Polish UI contamination; re-inspection + source verification (macbook/code/startup clips across timestamps) proved all sources clean — no repair needed, recorded here instead of a phantom fix.

## Planner decisions / consistency

16 logged keep/swap records with floors/leaders/reasons; manifest trace per shot (requested vs executed, effective source); PLAN_DETERMINISTIC true (seed-11 re-derivation identical); RENDER_DETERMINISTIC not claimed (single render).

## Limitations (with reasons)

1. Voice MSA/Jordanian, sparse 5-word narration (validated voice physics ~2.4 s/char) — structural, pending Egyptian TTS track.
2. Narration intelligibility unverified by human/ASR (tiny-Whisper incapable at this rate) — HUMAN_LISTENING_REQUIRED.
3. 2× file reuse residual (reviewer REVIEW) — accepted; pool depth is the bound.
4. Caption cues midpoint-split (word timings unfabricatable).
5. B-roll provenance UNKNOWN; music CC-BY attribution required on publication.
6. No stat-card/SVG-raster/UI-animation in this cut (director did not select them; capabilities exist but unused — not faked).
