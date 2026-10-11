# -*- coding: utf-8 -*-
"""3.1 benchmark checks: plan determinism + planner-owned motion/camera."""
import collections
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "scripts")
import bench_director_v1 as B
from engine.tools import diversity as D
from engine.tools import visual_plan as V

NARR = [
    {"id": "S1", "span": [1.5, 7.0], "text": "t", "need": "neon",
     "visual": ""},
    {"id": "S2", "span": [7.0, 18.0], "text": "t", "need": "typing",
     "visual": ""},
    {"id": "S3", "span": [18.0, 31.0], "text": "t", "need": "code",
     "visual": ""},
    {"id": "S4", "span": [31.0, 44.638], "text": "t", "need": "laptop",
     "visual": ""},
    {"id": "S5", "span": [45.138, 58.0], "text": "t", "need": "handshake",
     "visual": ""},
    {"id": "S6", "span": [58.0, 75.238], "text": "t", "need": "city",
     "visual": ""},
]
STATES = ["HOOK", "PROBLEM", "EXPLANATION", "EXAMPLE", "PAYOFF", "ENDING"]
MOTS = {"HOOK": ["cut"], "PROBLEM": ["push", "hold"],
        "EXPLANATION": ["push", "hold"], "EXAMPLE": ["push", "slide", "hold"],
        "PAYOFF": ["push", "hold"], "ENDING": ["hold"]}
CAMS = {"HOOK": ["static"], "PROBLEM": ["push", "static"],
        "EXPLANATION": ["push", "static"],
        "EXAMPLE": ["push", "pan", "static"], "PAYOFF": ["push", "static"],
        "ENDING": ["static"]}


def main():
    a = V.plan_shots_diverse(NARR, B.POOL, voice_mode="NARRATED", seed=7)
    b = V.plan_shots_diverse(NARR, B.POOL, voice_mode="NARRATED", seed=7)
    print("PLAN_DETERMINISTIC:",
          a["shots"] == b["shots"] and a["log"] == b["log"])
    print("dist:", dict(collections.Counter(
        s.get("asset", "").split("/")[-1] for s in a["shots"])))
    mem = D.DiversityMemory(seed=7)
    res = []
    for i, s in enumerate(a["shots"]):
        st = STATES[min(i // 3, 5)]
        m = D.select_motion(MOTS[st], mem, i, st)
        mem.record(i, {"motion": m["motion"]})
        c = D.select_camera(CAMS[st], "center", mem, i)
        mem.record(i, {"camera": c["camera"], "composition": "center"})
        res.append((s["shot_id"], m["motion"], m["decision"], c["camera"],
                    c["decision"]))
    print("motions:", dict(collections.Counter(m for _, m, _, _, _ in res)))
    print("cameras:", dict(collections.Counter(c for _, _, _, c, _ in res)))
    for row in res:
        print(" ", row[0], row[1], row[3])


if __name__ == "__main__":
    main()
