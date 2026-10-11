# Visual Director Report

Module `engine/tools/visual_director.py` (pure, deterministic). Input: script sentences + story states. Output per sentence: idea, intent, emotion (urgency/curiosity/calm/tension/optimism/surprise/neutral), info_type (STATISTIC/TECH_TERM/CONTRAST/PROCESS/STATEMENT), visual opportunity + metaphor category (15: TRANSFORMATION…FLOW), shot type, asset type, motion, typography, SFX, music state, transition intent, camera.

Demonstrated on benchmark: 7 sentences → 7 states (HOOK/PROBLEM/EXPLANATION/PROCESS/EXAMPLE/PAYOFF/ENDING) → beats drove shots, motion grammar, music states, SFX. `arc_for_duration` selects short-form arc by total (<45 s: 4 states, else 7).

Limitation found in vivo: downstream `plan_shots` ignores beat-level needs variety (same top scorer repeated) — repaired at fit stage with logged diversity re-pick; planner-level diversity memory is future work.
