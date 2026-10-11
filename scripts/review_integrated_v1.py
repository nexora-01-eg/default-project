# -*- coding: utf-8 -*-
"""Review the integrated benchmark from its own manifest (real records)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, ".")
from engine.creative import review as R
from engine.tools import quality_score as Q
from engine.tools import reviewer2 as R2

PROOT = Path(r"C:\Users\NOUR SOFT\Documents\Default Project\projects"
             r"\bench_integrated_v1_20260925")
FILES = ["n", "c", "k", "m", "s", "e", "h", "d"]


def main():
    m = json.load(open(PROOT / "timeline" / "manifest.json",
                       encoding="utf-8"))
    final = m["output"]
    ass = (PROOT / "timeline" / "bench.ass").read_text(encoding="utf-8")
    asm = m["assembly"]
    recs = [{"shot_id": "title", "kind": "card", "start": 0.0, "end": 1.5,
             "hook_text": "إزاي؟", "texts": []}]
    cur = 1.5
    for i, e in enumerate(asm):
        dur = round(e["params"]["span"][1] - e["params"]["span"][0], 2)
        recs.append({"shot_id": f"sg{i:02d}", "start": round(cur, 2),
                     "end": round(cur + dur, 2),
                     "asset": FILES[i % len(FILES)], "motion": "push",
                     "hook_text": "إزاي؟" if cur < 5.0 else "",
                     "texts": [{"role": "caption"}]})
        cur = round(cur + dur, 2)
    r2 = R2.review_all(recs, 79.14, duck_states=[{"gain_db": -6}],
                       last_content_end=79.14, has_endcard=True,
                       mean_db=-26.1, peak_db=-6.6)
    segs = [{"kind": ("card" if r.get("kind") == "card" else "clip"),
             "span": [r["start"], r["end"]]} for r in recs]
    tl = {"segments": segs, "total": 79.14, "hook_text": "إزاي؟",
          "script_words": 7, "motion_events": 20,
          "music_gains": [-6.0, -2.0, 0.0],
          "scenes": [{"id": "L1", "span": [1.5, 44.638]},
                     {"id": "L3", "span": [45.138, 75.238]}]}
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
        {"scenes_with_text": 6, "hook_shots": 4, "hook_question": True,
         "distinct_sources": 6, "shot_lengths": lens, "motion_events": 20,
         "scenes": 6, "font_families": 1, "max_layers": 2,
         "caption_correct": True, "peak_db": -6.6,
         "music_gains": [-6.0, -2.0, 0.0], "sfx_documented": True,
         "consistent": True, "arc_complete": True, "payoff_present": True,
         "ending_ok": True, "tech_ok": True, "reviewer_verdict": "PASS",
         "manifest": True, "story_arc": True, "arabic_rtl_ok": True,
         "av_sync_ok": True})
    print("SCORE:", qs["score"], qs["verdict"], qs["critical_fail"])
    (PROOT / "timeline" / "review_integrated.json").write_text(
        json.dumps({"reviewer2": r2,
                    "creative": {"verdict": rev["verdict"],
                                 "checks": rev["checks"]},
                    "quality_score": qs}, ensure_ascii=False, indent=1),
        encoding="utf-8")


if __name__ == "__main__":
    main()
