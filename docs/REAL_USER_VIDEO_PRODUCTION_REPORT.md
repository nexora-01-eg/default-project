# REAL_USER_VIDEO_PRODUCTION_REPORT.md (2026-09-20)

Project: `project_20260920_121544_869371` (dedicated; prior projects untouched).

## 1. Source
- `C:\Users\NOUR SOFT\Downloads\document_5873164930269587412.mp4`
- 113,556,953 bytes, SHA256 B973A51C747B08F49918A368715495D7DFEA6CF6EA2614FBD95412D9299B3D79
- 720×1280 vertical 9:16 phone footage, 276.85 s, h264, VFR ~20.7 fps,
  stereo AAC 48 kHz; source A/V skew 0.75 s IN THE FILE (video 276.849 /
  audio 276.096). Readable. Untouched after run (size+mtime+hash verified).

## 2. Content Understanding
Egyptian-dialect Arabic talking-head monologue: the speaker gives feedback
on a video/system — video itself is good ("الفيديو نفسه كويس") but flags
repetition, mentions Al-Montier/data-center/transition/X-code review
workflow. Single static scene, no cuts. Evidence: transcript + EDL + scenes.

## 3. Transcript
Local tiny-model pipeline (only cached model; no downloads): Arabic
(p=0.974), 110 segments / 574 words / 3 fillers, 36 ts-issues flagged.
Quality: ROUGH on dialect (garbled tokens) — fidelity limitation recorded;
timestamps/pauses usable.

## 4. Editing Decisions
- EDL: 29 decisions, silence REMOVEs (plan only).
- Intel: 8 SAFE / 6 UNSAFE (6 reverted), 18 repetitions, 14 jump-cuts.
- Brain (talking_head): 2 cuts approved (edl_0008 [54.1,54.9],
  edl_0012 [63.1,64.2], silence, ~1.9 s), 11 rejected, UNSAFE excluded.
- Pacing: 7 SAFE TRIMs found but correctly REFUSED at execution approval
  (base approval covers only the 2 brain cuts — hierarchy held, logged).
- No plan file hand-edited at any point.

## 5. Assets
- Director: 3-act plan, abstract backgrounds suggested (generic, no topic pack).
- Arsenal-X live: 9 requirements planned; background search returned 16:9
  images (PARTIAL, UNKNOWN provenance); verify → CAUTION.
- Decision: NO_SUITABLE_LOCAL_ASSET for insertion (static images, unknown
  provenance, no motivated placement in a talking head; music unjustified
  for feedback monologue — absence preferred). No downloads (0 sources).

## 6. Captions
54 Arabic cues (clean style, Arial, sidecar SRT+VTT), max cps 26.35,
0 warnings; UTF-8 verified (2219 Arabic chars); timing/overlap/empty/
readspeed all PASS in review. Text fidelity bounded by tiny-model
transcript (stated, not hidden).

## 7. Audio
Source stereo AAC preserved through render (aac). No mixing/normalization
(new policy forbidden). Sync: see render QC below.

## 8. Visual Processing
Visual polish plan (54 placed, 34 conflicts) approved; burned-in path not
used (sidecar approved). No reframing/crop/effects supported for this
content — none applied. Faces/embeddings honestly unavailable.

## 9. Render
`render-plan --captions` (h264_qsv): output
`projects/project_20260920_121544_869371/renders/plan_20260920_152540.mp4`
(29.9 MB) + .srt/.vtt + manifest. ffprobe: h264 High 640×360 30p +
audio, 261+ frames, readable. **Base QC verdict: FAIL** —
`duration got=275.498 want=274.975 tol=0.4`, `av_sync 0.720 tol=0.5`,
`av_duration_delta 0.720 tol=0.5`. Root cause: source's own 0.75 s A/V
skew + ~0.55 s concat padding on VFR phone media. No manifest/captions
written (pipeline correctly halted before caption layer).

## 10. Independent Review
Verdict **REVIEW**: 10/14 PASS (output exists/non-empty, EDL, all caption
checks, both approvals, visual approval); 4 REVIEWs (Phase-25 stream-depth
placeholders + correct note that pacing execution never ran). Reviewer
rules untouched.

## 11. Repair Loop
1 cycle via `plan_repair`: 4 routes, ALL `REVIEW_AGAIN`, zero FAIL →
no re-render warranted (deterministic engine would reproduce the identical
QC failure; re-rendering without a code/config change is churn, not
repair). Budget untouched (0/2). No manual overrides.

## 12. Before / After
SOURCE 276.85 s, 720×1280, stereo AAC, monologue + pauses.
FINAL: valid 275.50 s render (~1.9 s approved silence removed + full
Arabic sidecars) that FAILS release QC on duration/sync tolerance →
not shippable as FINAL. Why each edit: the 2 cuts = approved long
silences; everything else kept per brain/approvals; pacing TRIMs blocked
by hierarchy (correct).

## 13. Limitations
1. VFR phone media + concat padding breaks 0.4 s/0.5 s QC thresholds —
   needs a VFR-aware render path (future development, NOT implemented here).
2. Tiny-model Arabic transcription is rough; small/large models not cached,
   downloads forbidden.
3. Faces/embeddings/B-roll-grade semantic search unavailable.
4. Reviewer stream depth is placeholder REVIEWs.
5. `input/` empty — this run used the supplied Downloads path directly
   (`analyze <path>`), which is the supported workflow.

## 14. Regression
Engine 385 passed / 3 skipped / 0 failed (incl. all render suites);
speech_real 7/7; arsenal-x untouched. No new dependencies. Completed
projects untouched (only new project + its artifacts created).
