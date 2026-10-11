# Motion System Architecture

## Vocabulary (`engine/tools/motion_system.py` over `engine/creative/motion.py`)

Parameterized presets: SPRING_IN, FADE_IN, SLIDE_LEFT/RIGHT, PUSH_IN, PULL_BACK, HOLD — each `{ass, camera, duration}`. `ass_tags()` maps presets to ASS overrides (rise/fade/slide); `camera_contract()` maps PUSH_IN/PULL_BACK to ffmpeg-adapter zoompan contracts (1.0↔1.12, 1080×1920@30, libx264). Grammar states (HOOK/SETUP/PROBLEM/EXPLANATION/CONTRAST/STATISTIC/EXAMPLE/ESCALATION/PAYOFF/CTA/ENDING) define shot density, motion intensity, typography, camera, SFX density, music, transition, graphics.

## Proven in smoke test

Camera push on 17 s dubai aerial (zoompan, frame-verified), fade in/out transitions, hard cuts on a beat-snapped boundary, ASS entrance animations on all cues. Punch reframes (static 1.15–1.2×) proven in narrated_tech v1.

## Not built (honest gaps)

Mask reveals, morphs, glitch/displacement shaders, motion blur, parallax/depth, particle systems, spring-physics overshoot (preset named SPRING_IN maps to rise — true spring dynamics need a web runtime), whip-pans, match cuts, speed ramps (FFmpeg setpts available, unwired), stabilization executions (detect-only via analysis), tracking-driven moves (no detector wired). Web-runtime motion (GSAP/Remotion contracts) specified but not installed.
