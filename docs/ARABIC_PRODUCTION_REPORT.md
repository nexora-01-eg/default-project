# Arabic Production Report

## Rendering foundation (verified by 10-case burn + frame review)

Arabic headline/paragraph/mixed/numerals/punctuation/RTL/kinetic/SVG-text/over-video: PASS (correct shaping, ligatures, order, no tofu). Two real findings: (1) Latin runs need bidi isolates — fixed in `typography.isolate_latin`, wired into kinetic cue builder; (2) color emoji has no chain font — CAPABILITY_MISSING (omit or PNG overlay). Trailing Latin punctuation mirrors — typography rule (use Arabic stops).

## Timing intelligence

Confidence tiers (HIGH ≥0.7, MEDIUM ≥0.4, LOW below) from faster-whisper word probabilities; >35% LOW forces phrase mode (no karaoke). tiny-model hallucination on pathological speech documented with repair policy (span-level verbatim fallback). Egyptian/MSA handling unchanged (model-dependent); English-in-Arabic keeps emphasis color + isolates.

## Remaining Arabic gaps

Word-karaoke needs better-than-tiny STT (base+ blocked by explicit-provisioning policy; torch STT hardware-blocked). Raster Arabic (Pillow) needs reshaper/bidi (TIER 2). Narration voice MSA-only, ~2.4 s/char (structural).
