# Capability matrix — audited 2026-09-23

| Capability | Classification | Evidence / test status | Production usability | Limitation and next action |
|---|---|---|---|---|
| FFmpeg trim, concat, crop, mux | IMPLEMENTED_BUT_UNVERIFIED | `rendering/ffmpeg.py`; historical MP4s; current review failed because configured FFprobe path is absent | Cannot freshly verify today | Repair tool-path configuration, then smoke render |
| EDL + deterministic manifests/cache | IMPLEMENTED_AND_VERIFIED | `execution.py`, tests and historical manifests | Editing workflows | Not a voice-first timeline |
| Scene/silence/filler analysis | IMPLEMENTED_BUT_LIMITED | analysis modules and tests | Useful for supplied footage | No semantic understanding |
| Local Whisper STT | IMPLEMENTED_BUT_LIMITED | `speech.py`, CLI | Existing local models only | no demonstrated Arabic word-timing accuracy on the target voice |
| Arabic RTL captions / ASS burn | IMPLEMENTED_BUT_LIMITED | `subtitles/*`, historical ASS | Basic burned captions | midpoint timing in production; no production-grade kinetic word highlighting |
| B-roll overlays/provenance pins | PARTIAL | `approval.py`, render plans | Local clip insertion | matching is manual/filename-adjacent, licenses/provenance incomplete |
| Asset semantic matching | MISSING | no embedding/model configured | Not usable | build local visual index plus human verification queue |
| Voice-first plan/render | PARTIAL | custom `narr_assemble_v1.py`, contract added | Bespoke test only | no reusable contract-to-render executor |
| Egyptian TTS | BLOCKED_BY_EXTERNAL_CAPABILITY | VoiceTut `SPACE_STILL_BLOCKED`; no retry | unavailable | human-approved local voice or recovered legal service |
| Audio gain/fade/mix/loudness analysis | IMPLEMENTED_BUT_LIMITED | ffmpeg helpers, `analysis/audio.py` | Basic mix | no measured side-chain ducking, LUFS render verification currently blocked |
| SFX / ambience timing | MISSING | no production subsystem | unavailable | licensed local catalogue + timed mixer |
| Motion/keyframes | PARTIAL | ASS fade/rise/slide; punch module | titles and static punches | no generalized keyframe/easing/compositor/masks/tracking |
| Transitions | PARTIAL | hard cuts/fade primitives | hard cuts in test | no reusable editorial transition execution |
| Independent creative review | PARTIAL | `creative/review.py`; historical report | rules-based evidence | no visual-semantic or human review; current rerun cannot probe video |
| Repair routing/checkpoints | PARTIAL | autonomy controller, new public contract checkpoint | phase state persistence | controller has no complete production executors |
| QC / deterministic render validation | IMPLEMENTED_BUT_UNVERIFIED | validation functions and prior manifests | blocked today | fix FFprobe path and rerun render/QC |

Classifications reflect executed evidence, not names of functions.
