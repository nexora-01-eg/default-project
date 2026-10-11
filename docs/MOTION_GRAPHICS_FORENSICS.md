# MOTION_GRAPHICS_FORENSICS — hook_second_v1_20260924

Read-only. Caption animation and kinetic typography are counted separately and
**never** counted as motion graphics.

## 1. Separation (final master `hook_second_20260925_022940.mp4`)

| Class | What exists in the video | Count |
|---|---|---|
| A) Caption animation (fade/move entrances on text) | ASS `\fad`/`\move` on Body/Key cues | 50 events (mechanism, not objects) |
| B) Kinetic typography | Title / headlines / keywords / endcard text | 50 cues, 4 styles |
| C) Motion graphics (constructed objects: arrows, circles, diagrams, counters, UI panels, icon compositions, charts, callouts, animated shapes) | **NONE** | **0** |
| D) Camera movement | None executed. `motion_grammar()` assigned FADE_IN/HOLD(×8)/SLIDE_RIGHT/SPRING_IN/PUSH_IN as **strings** stored in `rich["motion"]`; the render path (trim→fit→concat) never reads them. A working `camera_push` zoompan executor exists in `adapters/providers.py:39-46` and was proven in the 2026-09-24 smoke test — the director never called it | 0 executed / 19 available impls unused |
| E) Graphic overlays | None. Renderer has **no overlay/xfade op** (grep `engine/rendering/ffmpeg.py` → absent) → structurally impossible | 0 (R5) |
| F) Procedural graphics | 3 full-frame navy cards (title / rupture / endcard via `color_clip`). No generated charts/counters/diagrams although `graphics_kit` + svgwrite + pillow are all AVAILABLE | 3 cards, 0 data graphics |
| G) UI graphics | 1 found-footage analytics dashboard clip + phone/code screens as B-roll. Zero constructed UI | 0 constructed |
| H) Transitions | 20 hard cuts + 1 hard cut to navy rupture card. No xfade/dissolve/wipe-renders (no op); ASS text fades only | 0 rendered transitions |

**Verdict: effectively zero constructed motion-graphic objects.** The human
assessment is correct on this point. Partially incorrect on "visual
metaphors": 3+ metaphor-bearing clips ARE used (brain = judgment, traffic
light = stop/go, spiral = escalation) — but all are found footage, none
constructed. No before/after split-screen or comparison diagram was built.

## 2. Icon chain (5 story moments tested)

| Moment | Icon that could represent it (lucide, verified present as SVG set) | Chain story→requirement→search→candidate→render exists? |
|---|---|---|
| Hook: tap/stop decision (sh_01) | `pointer` / `hand` / `octagon-pause` | NO |
| Brain judges in 1 s (sh_06) | `brain` | NO |
| Pacing/cuts demo (sh_09) | `scissors` / `clapperboard` | NO |
| Clear promise (sh_12) | `target` / `badge-check` | NO |
| Stop-vs-go contrast (sh_15) | `scale` (balance) / `arrow-left-right` | NO |

`visual_plan.py`, `visual_director.py`, `diversity.py`, `director.py` contain
**zero** references to icons/SVG/Lottie. `plan_production()` emits only BROLL
+ CAPTION_FONT requirement kinds. **The chain does not exist → capability gap
(R2), documented.**

## 3. Motion-asset chain

- Indexed? Lottie JSON present (`lottie-library`, `lottie-mega`) but no index.
- Semantically searchable? No.
- Planner-aware? No (no requirement kind, no search call).
- Renderer support? No Lottie→frames path; Chromium exists on disk but the
  probe (`shutil.which("chrome")`) reports MISSING — detection gap.
- License block? Remotion LICENSE_BLOCKED; Lottie files themselves unexamined.
- **Conclusion: simply never considered (R2+R3), with R5/R8 behind it.**

## 4. SFX chain

- Vocabulary: 4 kinds in `SFX_RULES`; only `sting` resolves to a real file.
  `tick`/`transition_tick`/`accent` have **no audio files** (03_SFX: 0 WAVs).
- No scroll/notification/click/whoosh/UI/tension/reveal category exists in the
  director's vocabulary at all — moments abound (phone tap sh_01, rupture
  sh_14, dashboard reveal sh_17, endcard sh_19) but the director cannot request
  what has neither name nor file.
- Production used 1 kind × 3 hits. **Minimal-predefined-vocabulary confirmed;
  deeper cause is the empty SFX shelf (genuine shortage) + no search layer.**
