# -*- coding: utf-8 -*-
"""Independent creative review of the narrated v1 render (NARRATED mode)."""
import json
import sys

sys.path.insert(0, ".")

from engine.creative import quality as Q
from engine.creative import review as R

PROOT = (r"C:\Users\NOUR SOFT\Documents\Default Project"
         r"\projects\narrated_tech_v1_20260923")

SEGS = [
    {"kind": "card", "label": "title-card", "len": 1.5},
    {"kind": "clip", "label": "S1-neon", "span": [1.5, 3.2]},
    {"kind": "clip", "label": "S1-code", "span": [3.2, 4.9]},
    {"kind": "clip", "label": "S1-neon2", "span": [4.9, 6.6]},
    {"kind": "clip", "label": "S2-keys", "span": [6.6, 11.0]},
    {"kind": "clip", "label": "S2-macA", "span": [11.0, 13.2]},
    {"kind": "clip", "label": "S2-macB", "span": [13.2, 15.5]},
    {"kind": "clip", "label": "S2-startup", "span": [15.5, 20.0]},
    {"kind": "clip", "label": "S3-code", "span": [20.0, 24.0]},
    {"kind": "clip", "label": "S3-eq", "span": [24.0, 28.0]},
    {"kind": "clip", "label": "S4-code", "span": [28.0, 32.0]},
    {"kind": "clip", "label": "S4-mac", "span": [32.0, 36.0]},
    {"kind": "clip", "label": "S4-keys", "span": [36.0, 40.0]},
    {"kind": "clip", "label": "S4-code2", "span": [40.0, 45.1]},
    {"kind": "clip", "label": "S5-hsA", "span": [45.1, 49.0]},
    {"kind": "clip", "label": "S5-hsB", "span": [49.0, 53.0]},
    {"kind": "card", "label": "S5-keycard", "len": 2.0},
    {"kind": "clip", "label": "S6-dubai", "span": [55.0, 61.0]},
    {"kind": "clip", "label": "S6-neon", "span": [61.0, 67.0]},
    {"kind": "clip", "label": "S6-plan", "span": [67.0, 73.0]},
    {"kind": "clip", "label": "S6-dubA", "span": [73.0, 76.0]},
    {"kind": "clip", "label": "S6-dubB", "span": [76.0, 79.3]},
    {"kind": "card", "label": "end-card", "len": 3.2},
]
FILES = ["107916-679600385_medium.mp4", "15029082_3840_2160_25fps.mp4",
         "251763_medium.mp4", "92480-637690589_medium.mp4",
         "6963374-hd_1080_1920_30fps.mp4", "316712_medium.mp4",
         "358512_medium.mp4", "296958_medium.mp4",
         "8373729-hd_1080_1920_25fps.mp4"]

TL = {"segments": SEGS, "total": 82.5,
      "hook_text": "إزاي الذكاء الاصطناعي بيغيّر صناعة الفيديو؟",
      "script_words": 7, "motion_events": 24,
      "music_gains": [-6.0, -2.0, 0.0],
      "scenes": [{"id": "S1", "span": [0, 6.6]},
                 {"id": "S2", "span": [6.6, 20.0]},
                 {"id": "S3", "span": [20.0, 28.0]},
                 {"id": "S4", "span": [28.0, 45.1]},
                 {"id": "S5", "span": [44.6, 53.0]},
                 {"id": "S6", "span": [53.0, 82.5]}]}
ASSETS = {"used": [{"file": f, "w": 1080, "h": 1920, "tags": [],
                    "provenance": "Arsenal MH (UNKNOWN)"} for f in FILES],
          "dims": {f: (1080, 1920) for f in FILES},
          "music": {"file": "Aitech.mp3",
                    "license": "CC-BY Kevin MacLeod"}}
SCRIPT = {"hierarchy_ok": True, "motion_events": 24, "body_cues": [],
          "scenes": [
              {"id": "S1", "span": [0, 6.6],
               "text": "زمان كان فريق كامل.", "keyword": "فريق كامل؟"},
              {"id": "S2", "span": [6.6, 20.0],
               "text": "زمان كان فريق كامل.", "keyword": "المعادلة"},
              {"id": "S3", "span": [20.0, 28.0],
               "text": "زمان كان فريق كامل.", "keyword": "السرعة"},
              {"id": "S4", "span": [28.0, 45.1],
               "text": "زمان كان فريق كامل.", "keyword": "تحليل"},
              {"id": "S5", "span": [44.6, 53.0],
               "text": "إنت هتستخدمه إزاي؟", "keyword": "الإنسان"},
              {"id": "S6", "span": [53.0, 82.5],
               "text": "إنت هتستخدمه إزاي؟", "keyword": "قرارك"}]}


def main():
    build = json.load(open(PROOT + r"\timeline\build.json",
                           encoding="utf-8"))
    final = build["output"]
    ass = open(PROOT + r"\timeline\narr.ass", encoding="utf-8").read()
    rev = R.review_production(final, TL, ass, ASSETS,
                              voice_mode="NARRATED")
    print("REVIEW-VERDICT:", rev["verdict"])
    for c in rev["checks"]:
        print("  %s = %s | %s" % (c["name"], c["verdict"], c["evidence"]))
    q = Q.evaluate({"segments": SEGS, "total": 82.5,
                    "music_gains": [-6.0, -2.0, 0.0]}, SCRIPT, ASSETS,
                   voice_mode="NARRATED")
    fails = {k: v for k, v in q.items() if v["verdict"] == "FAIL"}
    revs = {k: v for k, v in q.items() if v["verdict"] == "REVIEW"}
    print("QUALITY-FAIL:", json.dumps(fails, ensure_ascii=False))
    print("QUALITY-REVIEW:",
          json.dumps({k: v["evidence"] for k, v in revs.items()},
                     ensure_ascii=False))
    import os
    os.makedirs(PROOT + r"\qc", exist_ok=True)
    json.dump({"review": rev,
               "quality_fail": fails,
               "quality_review": {k: v["evidence"] for k, v in revs.items()}},
              open(PROOT + r"\qc\independent_review.json",
                   encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
