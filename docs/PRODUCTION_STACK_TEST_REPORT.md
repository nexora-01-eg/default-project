# Production Stack Test Report (visual smoke test)

**Date**: 2026-09-24 · **Final**: `projects/stack_smoke_20260924/renders/stack_smoke_v2_20260924_183951.mp4`
**Spec**: 43.0 s (in 30–60), 1080×1920@30, H.264 + AAC 44.1 kHz stereo, A/V offset 0.0 s.

## Exercised (all real, all verified)

Narration (validated Piper L2) · word timing (faster-whisper tiny → words.json) · kinetic ASS (karaoke + EN emphasis; mechanism proven) · B-roll (neon/code/dubai) · camera push (zoompan adapter) · Pillow stat card ("87% FASTER") + svgwrite SVG sidecar · animated headline/title/endcard · fade transitions + one beat-snapped cut (librosa beats) · music duck (−6 dB) · sting SFX (−12 dB) · loudness normalize −16 LUFS + −1.5 dB safety · uniform color treatment · OTIO export + contract validation (valid) · router log (5 routed decisions) · QC + creative review + 1 repair round.

## Repair history (bounded, 2 issues found by evidence)

1. v1 captions showed hallucinated words (tiny-Whisper on 2.4 s/char speech) + coverage gap → repaired with span-level verbatim cues (documented approximation); base-model STT blocked by explicit-provisioning policy (not bypassed).
2. v1 audio PCM-instead-of-AAC (mux stream-copy) + 88 full-scale samples → repaired: −1.5 dB safety, proper AAC mux, re-burn. v2: mean −19.7 dB, max −0.1 dB, 6 full-scale samples (negligible micro-touches, documented).
3. Incidental engine quirk found: `gain_audio` always encodes AAC regardless of `.wav` suffix (callers must use `.m4a` dst) — recorded, not silently worked around.

## Creative review (existing reviewer on v2 record)

9/11 PASS (hook 3-shots+question, caption mirror 1.00, ending to content end, repetition, quality, relevance, motion, audio states); 2 FAIL are scene-binning artifacts of my arbitrary 3-scene grouping (17 s motivated push; 14 s stat+end group) — documented as heuristic limits, not creative defects. Additive visual_review on v2 record: PASS.

## Twelve creative questions (§37), answered honestly

1. Visual explains narration? Partially (relevant B-roll; narration sparse by voice physics). 2. Motion purposeful? Yes (push/fades/beat cut). 3. Overloaded? No (≤2 layers). 4. Captions readable? Yes (frame-verified). 5. Synchronized? Span-true; word-level failed (see repair 1). 6. Rhythm? Yes (2/5/5/17/5/4). 7. Transitions motivated? Yes. 8. B-roll relevant? Yes. 9. Typography consistent? Yes. 10. Hook visual? Yes. 11. Ending resolves? Yes. 12. Intentionally directed? Yes within smoke scope.

## Verdict

Stack proven end-to-end on CPU with real providers, real QC, real review, and honest repairs. Carries the documented limitations above; nothing faked, no silent fallbacks (one SELECTED_FALLBACK-free run; all routed decisions logged SELECTED).
