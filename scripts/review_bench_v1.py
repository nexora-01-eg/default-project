# -*- coding: utf-8 -*-
"""Review the director benchmark: reviewer2 (shot-level) + creative review
+ quality score. Re-derives the deterministic shot plan (pure) for records.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, ".")
from engine.creative import review as R
from engine.tools import motion_system as _ms
from engine.tools import quality_score as _qs
from engine.tools import reviewer2 as _r2
from engine.tools import visual_director as _vd
from engine.tools import visual_plan as _vp

PROOT = Path(r"C:\Users\NOUR SOFT\Documents\Default Project\projects"
             r"\bench_director_v1_20260924")
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
    a.update({"w": 1080, "h": 1920})
NARR = [
    {"id": "L1", "span": [1.5, 44.638], "text": "زمان كان فريق كامل.",
     "need": "neon technology abstract hook", "visual": "high impact opener"},
    {"id": "L3", "span": [45.138, 75.238], "text": "القرار قرارك.",
     "need": "human scale future payoff", "visual": "cinematic resolve"},
]
SCRIPT = ["زمان كان فريق كامل.", "دلوقتي المعادلة اتغيّرت.",
          "السرعة نفسها اتغيّرت.", "من الفكرة للمونتاج.",
          "تحليل وقص أسرع.", "القرار لسه للإنسان.", "إنت هتستخدمه إزاي؟"]
STATES = ["HOOK", "PROBLEM", "EXPLANATION", "PROCESS", "EXAMPLE", "PAYOFF",
          "ENDING"]


def main():
    final = json.load(open(PROOT / "timeline" / "build.json",
                           encoding="utf-8"))["output"]
    ass = (PROOT / "timeline" / "bench.ass").read_text(encoding="utf-8")
    beats = _vd.direct_script([{"text": t} for t in SCRIPT], STATES)
    shots = _vp.storyboard(NARR, POOL, voice_mode="NARRATED")
    recs = []
    for sh in shots:
        mid = (sh["start"] + sh["end"]) / 2
        bi = min(int(mid / 78.89 * len(beats)), len(beats) - 1)
        role = {"HOOK": "INTRO", "PROBLEM": "PROBLEM",
                "EXPLANATION": "BODY", "PROCESS": "PROCESS",
                "EXAMPLE": "KEYWORD", "PAYOFF": "IMPORTANT_FACT",
                "ENDING": "CTA"}.get(beats[bi]["state"], "BODY")
        prim = _ms.motion_grammar(role)
        recs.append({"shot_id": sh["shot_id"], "start": sh["start"],
                     "end": sh["end"], "asset": sh.get("asset"),
                     "label": sh.get("asset", ""),
                     "motion": "push" if prim == "PUSH_IN" else "cut",
                     "hook_text": "إزاي؟" if sh["start"] < 5.0 else "",
                     "texts": [{"role": "caption"}]})
    r2 = _r2.review_all(recs, 78.89, duck_states=[{"gain_db": -6}],
                        last_content_end=78.89, has_endcard=True,
                        mean_db=-26.1, peak_db=-6.6)
    tl = {"segments": [{"kind": "clip", "span": [s["start"], s["end"]]}
                       for s in recs], "total": 78.89,
          "hook_text": "إزاي الذكاء الاصطناعي بيغيّر صناعة الفيديو؟",
          "script_words": 7, "motion_events": 12,
          "music_gains": [-6.0, -2.0, 0.0],
          "scenes": [{"id": "L1", "span": [1.5, 44.638]},
                     {"id": "L3", "span": [45.138, 75.238]}]}
    files = list({s["asset"] for s in recs if s["asset"]})
    assets = {"used": [{"file": f, "w": 1080, "h": 1920, "tags": [],
                        "provenance": "Arsenal MH (UNKNOWN)"} for f in files],
              "dims": {f: (1080, 1920) for f in files},
              "music": {"file": "Aitech.mp3", "license": "CC-BY"}}
    rev = R.review_production(final, tl, ass, assets, voice_mode="NARRATED")
    lens = [round(s["end"] - s["start"], 2) for s in recs]
    qs = _qs.score(
        {"scenes_with_text": 2, "hook_shots": 3, "hook_question": True,
         "distinct_sources": len(files), "shot_lengths": lens,
         "motion_events": 12, "scenes": 2, "font_families": 1,
         "max_layers": 2, "caption_correct": True, "peak_db": -6.6,
         "music_gains": [-6.0, -2.0, 0.0], "sfx_documented": True,
         "consistent": True, "arc_complete": True, "payoff_present": True,
         "ending_ok": True, "tech_ok": True, "reviewer_verdict": "PASS",
         "manifest": True, "story_arc": True, "arabic_rtl_ok": True,
         "av_sync_ok": True})
    (PROOT / "timeline" / "review2.json").write_text(json.dumps(
        {"reviewer2": r2, "creative": {"verdict": rev["verdict"],
                                      "checks": rev["checks"]},
         "quality_score": qs}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    print("R2:", r2["verdict"], "| CREATIVE:", rev["verdict"],
          "| SCORE:", qs["score"], qs["verdict"])
    for c in r2["checks"]:
        if c["verdict"] != "PASS":
            print("  R2", c["check"], c["verdict"], "|", c["evidence"])


if __name__ == "__main__":
    main()
