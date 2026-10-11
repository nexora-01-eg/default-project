# REAL_USER_EDITORIAL_UPGRADE_REPORT.md (2026-09-20)

## Executive Summary
First real-user production with visible editorial transformation: 2 approved
silence cuts, 10 phrase-motivated punch-ins (129.4 s reframed), 53 Arabic
captions burned in with visual placement, U+FFFD sanitization, VFR fix
preserved (A/V offset 0.03 s). Review: 0 FAIL. Regression: engine 402/0,
arsenal-x 54/54.

## Source
`C:\Users\NOUR SOFT\Downloads\document_5873164930269587412.mp4` —
113,556,953 bytes, SHA256 B973A51C…3D79, 720×1280 9:16, 276.85 s, h264,
VFR ~20.7 fps, stereo AAC 48 kHz, source A/V skew 0.75 s. Untouched after
run (size+mtime+hash re-verified). Egyptian-dialect talking-head feedback
monologue (110 seg / 574 words, tiny-model Arabic, rough but timestamped).

## Previous Output
`.../project_20260920_121544_869371/renders/plan_20260920_143014.mp4`
(kept intact as baseline): 2 cuts, sidecar captions, no reframes.

## Root Cause
Minimalism was correct conservatism (brain: 11 reject, UNSAFE excluded;
repetition removal forbidden on uncertain tiny-model Arabic), PLUS two
missing capabilities: (1) no reframing engine, (2) captions sidecar-only.
Fixed additively: `engine/editing/punch.py` (planner + approved
post-process via trim/apply_vf/concat) and burned-in visual-ASS path
(already existed, now used). Aggressive brain mode yields identical
verdicts — conservatism is structural, not threshold tuning.

## New Editorial Strategy
Approved silence cuts + punch-ins on sentence-boundary phrases (≥8 s apart,
≤20 s each, 1.08/1.12 by phrase length, focus 0.5,0.41 from frame audit) +
burned Arabic captions + explicit non-goals (no B-roll/music: unmotivated
for talking head; no repetition deletion: transcription uncertainty).

## Edit Statistics
Cuts 2 (~1.9 s) · punch-ins 10 (129.4 s, 47%) · caption cues burned 53 ·
B-roll 0 · overlays 0 beyond captions · audio ops 0 (none exist; mix
preserved, loudness identical −24.3 LUFS) · caption coverage ~100%.

## Timeline Changes
276.849 s → 274.975 expected → base actual 275.257 → punched 275.422 →
final captioned 275.422 (video 275.373 / audio 275.403, offset 0.03 s).

## Silence/Filler/Repeat Changes
2 long-silence cuts via approvals. Fillers: 3 flagged, none removed
(confidence policy). Repetitions (18 flagged): preserved — tiny-model
Arabic too unreliable for meaning-destructive edits (documented decision).

## Punch-In Events
10 mapped, 0 dropped: [4.7–12.2] [19.2–29.2] [38–52.5] [69.9–83.8]
[90.6–102.3] [104.3–124.3] [139.1–144.7] [152.9–172.9] [237.5–250.6]
[266.8–273.0] (output coords), scales 1.08/1.12, face-safe center crop
verified on 8 inspected frames.

## Caption Rendering
54 cues → 53 mapped (1 consumed by cut); U+FFFD found in cue_0031 —
sanitized with `undecodable_chars` warning (new `_scrub_undecodable`,
text+refs consistent, tested); burned via visual ASS (54 placements
valid); frame-verified readable RTL at 5 timestamps; 1 cue >25 cps
flagged REVIEW (genuine readability note).

## B-Roll
Searched (dark tech backgrounds found, PARTIAL/UNKNOWN) → rejected:
static images, unknown provenance, no motivated placement.
NO_SUITABLE_LOCAL_ASSET recorded honestly.

## Graphics
None beyond captions (icons exist but unmotivated overlays = busy-work).

## Audio
No processing available in engine (extract/mix only) — preserved bit-exact
in mix (loudness −24.3 LUFS both, LRA 7.5→7.6). 2 AAC generations noted,
inaudible. No music/SFX (unjustified).

## QC
Base QC pass; caption QC pass; final streams: 720×1280 h264 + AAC,
container 275.422 / video 275.373 / audio 275.403. Frame accounting:
punch assembly exact (5686 in = 5686 out, regression-tested both encoders
after finding a QSV concat-re-encode drop quirk → copy-concat + a probe-rate
undercount bug → proxy-rate fix). The caption burn re-encode outputs 5562
frames: copy-concat joints carry duplicate-PTS packets that re-encoding
collapses; frozen-frame analysis of the final file shows no frozen run
except one 6 s natural stillness (speaker motionless, verified on frames),
durations exact, QC thresholds pass. Trim-level timestamp hygiene is
recorded future work; current outputs verified good.

## Independent Review
REVIEW, 0 FAIL: 10+ PASS (output, EDL, all caption checks incl. new
sanitization path, approvals, bindings); REVIEWs = Phase-25 placeholders
+ true notes. Rules untouched.

## Repair Attempts
1 cycle, all REVIEW_AGAIN, 0 FAIL → no re-render warranted. Budget 0/2.

## Before/After Comparison
Raw 276.85 static talking head, no text → final 275.42 with 2 cuts,
10 visible reframes (verified tighter framing on frames), permanent
Arabic captions throughout, identical audio mix. Duration −1.43 s;
47% runtime reframed; 100% caption coverage added.

## Remaining Limitations
Tiny-model Arabic fidelity (garbled tokens burned as-is where decipherable);
1 fast cue; no B-roll/music/audio-processing capabilities exist;
reviewer stream depth placeholder; vertical-only master.

## Final Verdict
PASS_WITH_LIMITATIONS (real transformation; listed capability bounds).

Final: `.../project_20260920_143434_526341/renders/editorial_v2_20260920_185641_captioned.mp4`
Manifest: `.../editing/editorial_upgrade_manifest.json`
