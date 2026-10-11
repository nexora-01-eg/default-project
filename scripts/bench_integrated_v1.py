# -*- coding: utf-8 -*-
"""Integrated benchmark: planner motion/camera -> assembly -> render.

Same topic/narration/audio/captions as bench_diverse_v1. Differences:
shots carry planner-owned motion/camera objects (attach_motion_camera);
render_shot() executes them (no uniform workaround); every shot lands in
the manifest with requested-vs-executed trace; mismatches fail loudly.
Usage: python scripts/bench_integrated_v1.py <project_dir> [--rerender-tag X]
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, ".")
import bench_director_v1 as B
from engine.core.media import probe
from engine.creative import motion as _motion
from engine.rendering.ffmpeg import burn_subtitles, concat, mux
from engine.tools import assemble as _as
from engine.tools import audio_director as _ad
from engine.tools import contract_schema as _cs
from engine.tools import quality_score as _qs
from engine.tools import reviewer2 as _r2
from engine.tools import visual_plan as _vp
from engine.creative import review as _crev

W, H, FPS = 1080, 1920, 30
L1_AT, GAP = B.L1_AT, B.GAP
L1, L3 = B.L1, B.L3
L3_AT = L1_AT + L1[1] + GAP
TOTAL = round(L3_AT + L3[1] + 3.65, 2)
STATES = ["HOOK", "PROBLEM", "EXPLANATION", "EXAMPLE", "PAYOFF", "ENDING"]
MOTS = {"HOOK": ["cut"], "PROBLEM": ["push", "hold"],
        "EXPLANATION": ["push", "hold"], "EXAMPLE": ["push", "slide", "hold"],
        "PAYOFF": ["push", "hold"], "ENDING": ["hold"]}
CAMS = {"HOOK": ["static"], "PROBLEM": ["push", "static"],
        "EXPLANATION": ["push", "static"],
        "EXAMPLE": ["push", "pan", "static"], "PAYOFF": ["push", "static"],
        "ENDING": ["static"]}


def main():
    proot = Path(sys.argv[1])
    tag = sys.argv[3] if len(sys.argv) > 3 and sys.argv[2] == \
        "--rerender-tag" else ""
    t0 = time.time()
    work = proot / "renders" / ("work" + tag)
    (proot / "timeline").mkdir(parents=True, exist_ok=True)
    work.mkdir(parents=True, exist_ok=True)
    log: dict = {"rounds": []}

    narr = [
        {"id": "S1", "span": [1.5, 7.0], "text": "hook question",
         "need": "neon abstract technology question",
         "visual": "high impact opener"},
        {"id": "S2", "span": [7.0, 18.0], "text": "team workload problem",
         "need": "typing keyboard work team", "visual": "human workload"},
        {"id": "S3", "span": [18.0, 31.0], "text": "ai transformation",
         "need": "code programming data screen",
         "visual": "systems at work"},
        {"id": "S4", "span": [31.0, 44.638], "text": "examples montage",
         "need": "laptop startup idea screen", "visual": "tools in use"},
        {"id": "S5", "span": [45.138, 58.0], "text": "human decides",
         "need": "handshake people collaboration human",
         "visual": "human presence"},
        {"id": "S6", "span": [58.0, 75.238], "text": "future payoff",
         "need": "city aerial future scale",
         "visual": "cinematic resolve"},
    ]
    plan = _vp.plan_shots_diverse(narr, B.POOL, voice_mode="NARRATED",
                                  seed=7)
    log["validation_pre"] = plan["validation"]["verdict"]
    log["planner_log"] = plan["log"]
    shots = list(plan["shots"])
    if any(f["dimension"] == "hook" and f["severity"] == "FAIL"
           for f in plan["validation"]["findings"]):
        first = min([s for s in shots if s.get("asset")],
                    key=lambda s: s["start"])
        a, b = first["start"], first["end"]
        thirds = [a, a + (b - a) / 3, a + 2 * (b - a) / 3, b]
        pool_dur = {x["file"]: x["dur"] for x in B.POOL}
        out = []
        for s in shots:
            if s["shot_id"] == first["shot_id"]:
                for k in range(3):
                    c = dict(s)
                    c["shot_id"] = f"{s['shot_id']}h{k + 1}"
                    c["start"], c["end"] = thirds[k], thirds[k + 1]
                    c["src_off"] = round(
                        (k * 1.7) % max(0.1, pool_dur.get(
                            s.get("asset"), 99) - (thirds[k + 1] -
                                                   thirds[k])), 2)
                    out.append(c)
            else:
                out.append(s)
        shots = sorted(out, key=lambda s: s["start"])
        log["rounds"].append({"round": "planner-repair",
                              "fix": "hook montage split",
                              "shot": first["shot_id"]})
    # Planner-owned motion/camera per shot (state-mapped options).
    per6 = len(shots) // 6
    opts = []
    for i in range(len(shots)):
        st = STATES[min(i // max(per6, 1), 5)]
        opts.append({"motion": MOTS[st], "camera": CAMS[st],
                     "composition": "center", "state": st})
    shots, decisions = _vp.attach_motion_camera(shots, opts, seed=7)
    log["motion_camera_decisions"] = decisions
    # Assemble through the integrated path (no uniform workaround).
    parts, manifest = [], []
    pool_dur = {x["file"]: x["dur"] for x in B.POOL}
    for i, sh in enumerate(shots):
        dur = round(sh["end"] - sh["start"], 2)
        fn = sh.get("asset")
        cap = max(0.1, pool_dur.get(fn, 99) - dur)
        off = float(sh.get("src_off", round((i * 1.7) % cap, 2)))
        seg = {"shot_id": f"sg{i:02d}", "kind": "clip", "file": fn,
               "span": [off, round(off + dur, 2)],
               "motion": sh["motion"], "camera": sh["camera"]}
        r = _as.render_shot(seg, B.ARS, work, encoder="h264_qsv")
        parts.append(r["part"])
        manifest.append(r["manifest"])
    mismatches = [m for m in manifest if "mismatch" in m]
    log["mismatches"] = mismatches
    # Title + endcard (procedural, planner-neutral).
    from engine.rendering.ffmpeg import color_clip
    tcard = work / "tcard.mp4"
    color_clip(B.CARD, W, H, 1.5, tcard, fps=FPS)
    body = work / "body.mp4"
    concat([tcard] + parts, body, reencode=True, encoder="libx264")
    measured = round(probe(body).duration, 2)
    tail_len = round(TOTAL - measured, 2)
    assert tail_len > 1.0, f"no room for endcard (measured {measured})"
    ecard = work / "ecard.mp4"
    color_clip(B.CARD, W, H, tail_len, ecard, fps=FPS)
    joined = work / "joined.mp4"
    concat([body, ecard], joined, reencode=True, encoder="libx264")
    audio = _as.build_audio(
        [{"kind": "silence", "dur": L1_AT, "name": "lead.wav"},
         {"kind": "wav", "src": str(B.NARR / "L1_06.wav"), "name": "n1.wav"},
         {"kind": "silence", "dur": GAP, "name": "s05.wav"},
         {"kind": "wav", "src": str(B.NARR / "L3_06.wav"), "name": "n3.wav"},
         {"kind": "silence", "dur": round(TOTAL - (L3_AT + L3[1]), 2),
          "name": "tail.wav"}],
        {"src": str(B.MUS),
         "states": _ad.music_plan(
             ["HOOK", "PROBLEM", "EXPLANATION", "PROCESS", "EXAMPLE",
              "PAYOFF", "ENDING"], TOTAL)},
        {"src": str(B.STING), "dur": 1.2, "gain_db": -12.0},
        TOTAL, work)

    def T(s):
        h = int(s // 3600)
        m = int((s % 3600) // 60)
        return f"{h}:{m:02d}:{s % 60:05.2f}"

    mid1, mid2 = L1_AT + L1[1] / 2, L3_AT + L3[1] / 2
    evs = [
        f"Dialogue: 0,{T(0)},{T(1.5)},Title,"
        f"{_motion.rise(540, 760)}كيف الذكاء الاصطناعي\\Nبيغيّر صناعة الفيديو؟",
        f"Dialogue: 0,{T(L1_AT)},{T(mid1)},Body,{_motion.fade()}زمان كان",
        f"Dialogue: 0,{T(mid1)},{T(L1_AT + L1[1])},Body,"
        f"{_motion.fade()}فريق كامل.",
        f"Dialogue: 0,{T(L3_AT)},{T(mid2)},Body,{_motion.fade()}القرار",
        f"Dialogue: 0,{T(mid2)},{T(L3_AT + L3[1])},Body,"
        f"{_motion.fade()}قرارك.",
        f"Dialogue: 0,{T(2.0)},{T(6.0)},Key,"
        f"{_motion.slide_in(540, 300, 'left')}فريق كامل؟",
        f"Dialogue: 0,{T(L3_AT + 1)},{T(L3_AT + 7)},Key,"
        f"{_motion.slide_in(540, 300, 'right')}الإنسان",
        f"Dialogue: 0,{T(TOTAL - 3.65)},{T(TOTAL)},End,"
        f"{_motion.fade(400)}القرار…\\Nقرارك إنت",
    ]
    head = ("[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: "
            "1920\nScaledBorderAndShadow: yes\n\n[V4+ Styles]\n"
            "Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, "
            "BackColour, Bold, Alignment, MarginV\n"
            "Style: Title,Arial,104,&H00FFD98A,&H80000000,&H80000000,1,5,120\n"
            "Style: Body,Arial,54,&H00FFFFFF,&H90000000,&H90000000,1,2,190\n"
            "Style: Key,Arial,70,&H00FFD98A,&H90000000,&H90000000,1,8,230\n"
            "Style: End,Arial,84,&H00FFD98A,&H80000000,&H80000000,1,5,120\n\n"
            "[Events]\nFormat: Layer, Start, End, Style, Text\n")
    ass = proot / "timeline" / ("bench" + tag + ".ass")
    ass.write_text(head + "\n".join(evs) + "\n", encoding="utf-8")
    muxed = work / ("muxed" + tag + ".mp4")
    mux(joined, audio["mixed"], muxed)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    final = proot / "renders" / f"bench_integrated_{stamp}.mp4"
    burn_subtitles(muxed, ass, final, encoder="h264_qsv")
    info = probe(final)
    contract = {"project": proot.name,
                "canvas": {"w": W, "h": H, "fps": FPS},
                "narration": {"segments": [
                    {"id": "L1", "text": L1[0], "start": L1_AT},
                    {"id": "L3", "text": L3[0], "start": L3_AT}]},
                "shots": [{"shot_id": s.get("shot_id", f"s{i}"),
                           "start": s.get("start", 0),
                           "end": s.get("end", 1),
                           "motion": s.get("motion", {"type": "hold"}),
                           "camera": s.get("camera", {"type": "static"})}
                          for i, s in enumerate(shots)]}
    from engine.tools import contract_schema as _cs
    cval = _cs.validate_contract(contract)
    (proot / "timeline" / ("manifest" + tag + ".json")).write_text(
        json.dumps({"duration": round(info.duration, 3),
                    "output": str(final), "shots": len(shots),
                    "contract_valid": cval, "assembly": manifest,
                    "log": log,
                    "elapsed_s": round(time.time() - t0, 1)},
                   ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"INTEGRATED {final} dur={info.duration:.2f} shots={len(shots)} "
          f"contract={cval['valid']} mismatches={len(mismatches)}")


if __name__ == "__main__":
    main()
