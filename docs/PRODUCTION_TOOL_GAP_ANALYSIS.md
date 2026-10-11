# Production Tool Gap Analysis (verified gaps only)

1. **Word-timing quality**: tiny-Whisper hallucinates on slow/pathological speech; base+ needs explicit provisioning; torch/CUDA STT (WhisperX, stable-ts) hardware-blocked. Impact: kinetic karaoke gated on voice intelligibility.
2. **SVG rasterization**: no resvg/Chromium — SVG ships as sidecar only.
3. **Arabic raster text**: needs arabic_reshaper/python-bidi for Pillow path; Arabic stays in libass path.
4. **Web runtime (GSAP/Remotion/three)**: specified, not installed (npm + ~150 MB Chromium + Remotion company-license gate).
5. **3D/VFX execution**: contracts only; no Blender present (portable-detect ready).
6. **Voice**: Piper validated but MSA + ~2.4 s/char (sparse narration only); Egyptian voice blocked (VoiceTut Space outage; local path GPU-gated).
7. **Music/SFX generation**: no generative audio (all TIER 4); library-only + procedural Tone.js future.
8. **Stem separation/voice isolation**: torch-gated (Demucs/Spleeter TIER 4).
9. **Upscale/restore/face pipelines**: torch/GPU or NC/AGPL licenses (TIER 4).
10. **Semantic search**: no embedding runtime (no torch); Arsenal-X matching is tag/evidence-based.
11. **Reviewer vision**: reviewer reads records + human frames; no VLM auto-vision (all VLMs TIER 4).
12. **MoviePy**: dropped (pillow conflict + FFmpeg redundancy).
13. **Live/refreshable data graphics**: needs web runtime (gap 4).
14. **HDR/ACES end-to-end**: OCIO present; no HDR monitor chain or config.
15. **Loudness true-peak**: pyloudnorm + manual safety; no true-peak limiter stage.
16. **Planner diversity memory** (found 2026-09-24): plan_shots repeats one file per scene; repaired at fit stage, planner-level fix pending.
17. **Emoji font**: no color-emoji in libass chain (verified tofu); PNG-overlay alternative documented.
18. **Latin-in-Arabic affixes**: fixed via bidi isolates (verified by frame).
19. **Word-karaoke STT floor**: tiny hallucinates on pathological speech; base+ needs explicit provisioning; torch STT hardware-blocked.
20. **SVG raster / web runtime / 3D execution / GPU models / NC-viral licenses**: unchanged from stack phase (see arsenal doc).
21. **Planner diversity memory**: IMPLEMENTED 2026-09-25 (benchmark 2→6 files, 0 post-render rounds); residual: rank-swap gate strictness + unlogged keeps; motion/camera auto-alternation pending.
23. **Relative-floor ranking (3.1, 2026-09-25)**: IMPLEMENTED — configurable floor/delta/gain/tradeoff, logged keep/swap decisions, motion+camera selectors, combo warnings, contribution scores. Residual: benchmark swaps don't fire (alternatives below floor — correct per §9); motion/camera variety demonstrated at plan level, not yet wired into render assembly.
22. **Reviewer scene bins**: retired in reviewer2 (shot-level); legacy reviewers kept untouched.
