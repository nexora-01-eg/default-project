# -*- coding: utf-8 -*-
"""Re-derive the blind production plan (deterministic) for repair mapping."""
import json
import sys

sys.path.insert(0, ".")
from engine.tools import visual_plan as V
import bench_director_v1 as B

BEATS = [
    ("HOOK", [0.0, 7.0], "neon abstract technology question"),
    ("QUESTION", [7.0, 15.0], "typing keyboard wonder question"),
    ("PROBLEM", [15.0, 25.0], "laptop work repetitive scroll"),
    ("EXPLANATION", [25.0, 35.0], "code programming data screen"),
    ("EXAMPLE", [35.0, 45.0], "screen cuts montage fast"),
    ("ESCALATION", [45.0, 55.0], "city aerial scale night"),
    ("PAYOFF", [55.0, 64.557], "handshake people collaboration human"),
    ("ENDING", [64.557, 68.46], "desk planning resolve calm"),
]

if __name__ == "__main__":
    sys.path.insert(0, "scripts")
    narr = [{"id": f"B{i}", "span": list(b[1]), "text": f"beat {i}",
             "need": b[2], "visual": ""} for i, b in enumerate(BEATS)]
    plan = V.plan_shots_diverse(narr, B.POOL, voice_mode="NARRATED", seed=11)
    for s in plan["shots"]:
        print(s["shot_id"], round(s["start"], 2), round(s["end"], 2), "|",
              (s.get("asset") or "").split("/")[-1], "|",
              s.get("reason", ""))
