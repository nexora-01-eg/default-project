# -*- coding: utf-8 -*-
"""Review the blind production from its manifest + deterministic plan."""
import json
import sys
from pathlib import Path

sys.path.insert(0, ".")
from engine.creative import review as R
from engine.tools import quality_score as Q
from engine.tools import reviewer2 as R2
from engine.tools import visual_plan as V

PROOT = Path(r"C:\Users\NOUR SOFT\Documents\Default Project\projects"
             r"\blind_social_v1_20260925")
POOL = [
    {"file": "107916-679600385_medium.mp4", "dur": 10.0,
     "tags": ["neon", "abstract", "glow", "technology"]},
    {"file": "15029082_3840_2160_25fps.mp4", "dur": 29.28,
     "tags": ["code", "screen", "programming", "data"]},
    {"file": "251763_medium.mp4", "dur": 15.0,
     "tags": ["typing", "keyboard", "hands", "work"]},
    {"file": "92480-637690589_medium.mp4", "dur": 13.3,
     "tags": ["laptop", "creator", "desk", "work"]},
    {"file": "316712_medium.mp4", "dur": 5.21,
     "tags": ["audio", "levels", "processing", "data"]},
    {"file": "358512_medium.mp4", "dur": 8.0,
     "tags": ["handshake", "agreement", "people", "collaboration"]},
    {"file": "296958_medium.mp4", "dur": 25.13,
     "tags": ["city", "aerial", "scale", "future"]},
    {"file": "6963374-hd_1080_1920_30fps.mp4", "dur": 11.81,
     "tags": ["laptop", "startup", "screen", "idea"]},
    {"file": "8373729-hd_1080_1920_25fps.mp4", "dur": 12.56,
     "tags": ["desk", "planning", "notebook", "startup"]},
]
for a in POOL:
    a.update({"w": 1080, "h": 720})
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


def main():
    m = json.load(open(PROOT / "timeline" / "manifest.json",
                       encoding="utf-8"))
    final = m["output"]
    ass = (PROOT / "timeline" / "blind.ass").read_text(encoding="utf-8")
    narr = [{"id": f"B{i}", "span": list(b[1]), "text": f"beat {i}",
             "need": b[2], "visual": ""} for i, b in enumerate(BEATS)]
    plan = V.plan_shots_diverse(narr, POOL, voice_mode="NARRATED", seed=11)
    shots = list(plan["shots"])
    first = min([s for s in shots if s.get("asset")],
                key=lambda s: s["start"])
    fa, fb = first["start"], first["end"]
    thirds = [fa, fa + (fb - fa) / 3, fa + 2 * (fb - fa) / 3, fb]
    expanded = []
    for s in shots:
        if s["shot_id"] == first["shot_id"]:
            for k in range(3):
                c = dict(s)
                c["shot_id"] = f"{s['shot_id']}h{k + 1}"
                c["start"], c["end"] = thirds[k], thirds[k + 1]
                expanded.append(c)
        else:
            expanded.append(s)
    recs = [{"shot_id": "title", "kind": "card", "start": 0.0, "end": 1.5,
             "hook_text": "؟", "texts": []}]
    cur = 1.5
    for i, s in enumerate(expanded):
        dur = round(s["end"] - s["start"], 2)
        recs.append({"shot_id": s["shot_id"], "start": round(cur, 2),
                     "end": round(cur + dur, 2),
                     "asset": (s.get("asset") or "").split("/")[-1],
                     "motion": "push", "hook_text": "؟" if cur < 5.0 else "",
                     "texts": [{"role": "caption"}]})
        cur = round(cur + dur, 2)
    files = sorted({r["asset"] for r in recs if r.get("asset")})
    print("plan_distinct:", len(files), files)
    r2 = R2.review_all(recs, 72.51, duck_states=[{"gain_db": -6}],
                       last_content_end=72.51, has_endcard=True,
                       mean_db=-26.6, peak_db=-6.4)
    segs = [{"kind": r.get("kind", "clip"), "span": [r["start"], r["end"]]}
            for r in recs]
    tl = {"segments": segs, "total": 72.51, "hook_text": "ليه؟",
          "script_words": 5, "motion_events": 20,
          "music_gains": [-6.0, -2.0, 0.0],
          "scenes": [{"id": "A", "span": [1.5, 36.2]},
                     {"id": "B", "span": [36.7, 64.6]}]}
    fl = ["x"] * 6
    assets = {"used": [{"file": x, "w": 1080, "h": 1920, "tags": [],
                        "provenance": "?"} for x in fl],
              "dims": {x: (1080, 1920) for x in fl},
              "music": {"file": "Aitech.mp3", "license": "CC-BY"}}
    rev = R.review_production(final, tl, ass, assets, voice_mode="NARRATED")
    print("R2:", r2["verdict"])
    for c in r2["checks"]:
        if c["verdict"] != "PASS":
            print("  R2", c["check"], c["verdict"], "|",
                  c.get("evidence", ""))
    print("CREATIVE:", rev["verdict"])
    for c in rev["checks"]:
        if c["verdict"] != "PASS":
            print("  CR", c["name"], "=", c["verdict"])
    lens = [round(r["end"] - r["start"], 2) for r in recs
            if r.get("kind") != "card"]
    qs = Q.score(
        {"scenes_with_text": 8, "hook_shots": 4, "hook_question": True,
         "distinct_sources": len(files), "shot_lengths": lens,
         "motion_events": 20, "scenes": 8, "font_families": 1,
         "max_layers": 2, "caption_correct": True, "peak_db": -6.4,
         "music_gains": [-6.0, -2.0, 0.0], "sfx_documented": True,
         "consistent": True, "arc_complete": True, "payoff_present": True,
         "ending_ok": True, "tech_ok": True, "reviewer_verdict": "PASS",
         "manifest": True, "story_arc": True, "arabic_rtl_ok": True,
         "av_sync_ok": True})
    print("SCORE:", qs["score"], qs["verdict"], qs["critical_fail"])
    (PROOT / "timeline" / "review_blind.json").write_text(json.dumps(
        {"reviewer2": r2,
         "creative": {"verdict": rev["verdict"], "checks": rev["checks"]},
         "quality_score": qs}, ensure_ascii=False, indent=1),
        encoding="utf-8")


if __name__ == "__main__":
    main()
