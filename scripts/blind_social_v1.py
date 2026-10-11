# -*- coding: utf-8 -*-
"""Blind autonomous production: social-media hook concept → finished video.

Director derives everything from the concept: beats, shots, assets,
motion, camera, music, sfx. Planner-owned motion/camera drive assembly.
Narration: validated Piper lines measured first (S1 34.187s, S2 28.37s);
edit designed around actual timing.
Usage: python scripts/blind_social_v1.py <project_dir>
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, ".")
import bench_director_v1 as B
from engine.core.media import probe
from engine.creative import motion as _motion
from engine.rendering.ffmpeg import (burn_subtitles, color_clip, concat,
                                     mux)
from engine.tools import assemble as _as
from engine.tools import audio_director as _ad
from engine.tools import contract_schema as _cs
from engine.tools import quality_score as _qs
from engine.tools import reviewer2 as _r2
from engine.tools import visual_director as _vd
from engine.tools import visual_plan as _vp
from engine.creative import review as _crev

W, H, FPS = 1080, 1920, 30
NARR2 = Path("C:/Users/NOUR SOFT/Documents/Default Project/tools/tts/"
             "piper/tests/narr2")
S1_TXT, S1_DUR = "أول ثانية تحسم.", 34.187
S2_TXT, S2_DUR = "الفضول يكسب.", 28.37
S1_AT, GAP = 1.5, 0.5
S2_AT = S1_AT + S1_DUR + GAP
TOTAL = round(S2_AT + S2_DUR + 3.9, 2)

BEATS = [
    ("HOOK", [0.0, 7.0], "neon abstract technology question",
     "hook that stops the thumb"),
    ("QUESTION", [7.0, 15.0], "typing keyboard wonder question",
     "curiosity gap opens"),
    ("PROBLEM", [15.0, 25.0], "laptop work repetitive scroll",
     "the scroll reflex"),
    ("EXPLANATION", [25.0, 35.0], "code programming data screen",
     "pattern interrupts win"),
    ("EXAMPLE", [35.0, 45.0], "screen cuts montage fast",
     "hook techniques demo"),
    ("ESCALATION", [45.0, 55.0], "city aerial scale night",
     "stakes rise"),
    ("PAYOFF", [55.0, S2_AT + S2_DUR], "handshake people collaboration human",
     "curiosity wins"),
    ("ENDING", [S2_AT + S2_DUR, TOTAL], "desk planning resolve calm",
     "controlled exit"),
]
MOTS = {"HOOK": ["cut"], "QUESTION": ["hold", "push"],
        "PROBLEM": ["push", "hold"], "EXPLANATION": ["push", "hold"],
        "EXAMPLE": ["push", "punch", "slide"], "ESCALATION": ["push"],
        "PAYOFF": ["push", "hold"], "ENDING": ["hold"]}
CAMS = {"HOOK": ["static"], "QUESTION": ["static", "push"],
        "PROBLEM": ["push", "static"], "EXPLANATION": ["push", "static"],
        "EXAMPLE": ["push", "pan", "static"], "ESCALATION": ["push"],
        "PAYOFF": ["push", "static"], "ENDING": ["static"]}
KEYWORDS = [(2.0, 6.0, "أول ثانية؟"), (8.0, 13.0, "Scroll"),
            (16.0, 21.0, "المشكلة"), (26.0, 31.0, "النمط"),
            (36.0, 41.0, "الحل"), (S2_AT + 1, S2_AT + 7, "الفضول")]


def main():
    proot = Path(sys.argv[1])
    t0 = time.time()
    work = proot / "renders" / "work"
    (proot / "timeline").mkdir(parents=True, exist_ok=True)
    work.mkdir(parents=True, exist_ok=True)
    log: dict = {"rounds": []}

    states = [b[0] for b in BEATS]
    beats = _vd.direct_script([{"text": {
        "HOOK": "first second decides everything",
        "QUESTION": "why do some videos hook instantly",
        "PROBLEM": "the scroll reflex kills weak openings",
        "EXPLANATION": "pattern interrupts break autopilot",
        "EXAMPLE": "hook techniques demonstrated fast",
        "ESCALATION": "stakes rise for creators",
        "PAYOFF": "curiosity wins retention",
        "ENDING": "controlled exit"}[s]} for s in states], states)
    narr = [{"id": f"B{i}", "span": list(BEATS[i][1]),
             "text": f"beat {i}", "need": BEATS[i][2], "visual": BEATS[i][3]}
            for i in range(len(BEATS))]
    plan = _vp.plan_shots_diverse(narr, B.POOL, voice_mode="NARRATED",
                                  seed=11)
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
    opts = []
    for sh in shots:
        mid = (sh["start"] + sh["end"]) / 2
        bi = next((i for i, b in enumerate(BEATS)
                   if b[1][0] <= mid < b[1][1]), len(BEATS) - 1)
        st = BEATS[bi][0]
        opts.append({"motion": MOTS[st], "camera": CAMS[st],
                     "composition": "center", "state": st})
    shots, decisions = _vp.attach_motion_camera(shots, opts, seed=11)
    log["motion_camera_decisions"] = decisions
    pool_dur = {x["file"]: x["dur"] for x in B.POOL}
    parts, manifest = [], []
    card = work / "tcard.mp4"
    color_clip(B.CARD, W, H, 1.5, card, fps=FPS)
    parts.append(card)
    for i, sh in enumerate(shots):
        dur = round(sh["end"] - sh["start"], 2)
        fn = sh.get("asset")
        if not fn:
            p = work / f"sg{i:02d}.mp4"
            color_clip(B.CARD, W, H, dur, p, fps=FPS)
            manifest.append({"shot": sh["shot_id"], "op": "card",
                             "result": str(p)})
            parts.append(p)
            continue
        cap = max(0.1, pool_dur.get(fn, 99) - dur)
        off = float(sh.get("src_off", round((i * 1.7) % cap, 2)))
        seg = {"shot_id": f"sg{i:02d}", "kind": "clip", "file": fn,
               "span": [off, round(off + dur, 2)],
               "motion": sh["motion"], "camera": sh["camera"]}
        r = _as.render_shot(seg, B.ARS, work, encoder="h264_qsv")
        parts.append(r["part"])
        manifest.append(r["manifest"])
    body = work / "body.mp4"
    concat(parts, body, reencode=True, encoder="libx264")
    measured = round(probe(body).duration, 2)
    total = round(measured + 3.5, 2)
    ecard = work / "ecard.mp4"
    color_clip(B.CARD, W, H, 3.5, ecard, fps=FPS)
    joined = work / "joined.mp4"
    concat([body, ecard], joined, reencode=True, encoder="libx264")
    TOTAL = round(probe(joined).duration, 2)
    audio = _as.build_audio(
        [{"kind": "silence", "dur": S1_AT, "name": "lead.wav"},
         {"kind": "wav", "src": str(NARR2 / "S1_06.wav"), "name": "n1.wav"},
         {"kind": "silence", "dur": GAP, "name": "s05.wav"},
         {"kind": "wav", "src": str(NARR2 / "S2_06.wav"), "name": "n3.wav"},
         {"kind": "silence", "dur": round(TOTAL - (S2_AT + S2_DUR), 2),
          "name": "tail.wav"}],
        {"src": str(B.MUS), "states": _ad.music_plan(states, TOTAL)},
        {"src": str(B.STING), "dur": 1.2, "gain_db": -12.0}, TOTAL, work)

    def T(s):
        h = int(s // 3600)
        m = int((s % 3600) // 60)
        return f"{h}:{m:02d}:{s % 60:05.2f}"

    mid1, mid2 = S1_AT + S1_DUR / 2, S2_AT + S2_DUR / 2
    evs = [
        f"Dialogue: 0,{T(0)},{T(1.5)},Title,"
        f"{_motion.rise(540, 760)}ليه فيديو يشدك\\Nوفيديو يتعدى؟",
        f"Dialogue: 0,{T(S1_AT)},{T(mid1)},Body,{_motion.fade()}أول ثانية",
        f"Dialogue: 0,{T(mid1)},{T(S1_AT + S1_DUR)},Body,"
        f"{_motion.fade()}تحسم.",
        f"Dialogue: 0,{T(S2_AT)},{T(mid2)},Body,{_motion.fade()}الفضول",
        f"Dialogue: 0,{T(mid2)},{T(S2_AT + S2_DUR)},Body,"
        f"{_motion.fade()}يكسب.",
    ]
    for k, (s, e, txt) in enumerate(KEYWORDS):
        evs.append(_motion.dialogue(
            s, e, "Key", txt,
            _motion.slide_in(540, 300, "left" if k % 2 == 0 else "right")))
    evs.append(_motion.dialogue(
        round(TOTAL - 3.5, 2), TOTAL, "End",
        "الفضول كسب\\Nوأنت لسه بتتفرج", _motion.fade(400)))
    head = ("[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: "
            "1920\nScaledBorderAndShadow: yes\n\n[V4+ Styles]\n"
            "Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, "
            "BackColour, Bold, Alignment, MarginV\n"
            "Style: Title,Arial,104,&H00FFD98A,&H80000000,&H80000000,1,5,120\n"
            "Style: Body,Arial,54,&H00FFFFFF,&H90000000,&H90000000,1,2,190\n"
            "Style: Key,Arial,70,&H00FFD98A,&H90000000,&H90000000,1,8,230\n"
            "Style: End,Arial,84,&H00FFD98A,&H80000000,&H80000000,1,5,120\n\n"
            "[Events]\nFormat: Layer, Start, End, Style, Text\n")
    ass = proot / "timeline" / "blind.ass"
    ass.write_text(head + "\n".join(evs) + "\n", encoding="utf-8")
    muxed = work / "muxed.mp4"
    mux(joined, audio["mixed"], muxed)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    final = proot / "renders" / f"blind_social_{stamp}.mp4"
    burn_subtitles(muxed, ass, final, encoder="h264_qsv")
    info = probe(final)
    contract = {"project": proot.name,
                "canvas": {"w": W, "h": H, "fps": FPS},
                "narration": {"segments": [
                    {"id": "S1", "text": S1_TXT, "start": S1_AT},
                    {"id": "S2", "text": S2_TXT, "start": S2_AT}]},
                "shots": [{"shot_id": s.get("shot_id", f"s{i}"),
                           "start": s.get("start", 0),
                           "end": s.get("end", 1),
                           "motion": s.get("motion", {"type": "hold"}),
                           "camera": s.get("camera", {"type": "static"})}
                          for i, s in enumerate(shots)]}
    from engine.tools import contract_schema as _cs
    cval = _cs.validate_contract(contract)
    (proot / "timeline" / "manifest.json").write_text(json.dumps(
        {"duration": round(info.duration, 3), "output": str(final),
         "shots": len(shots), "contract_valid": cval, "assembly": manifest,
         "log": log, "elapsed_s": round(time.time() - t0, 1)},
        ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"BLIND {final} dur={info.duration:.2f} shots={len(shots)} "
          f"contract={cval['valid']} "
          f"mismatches={sum(1 for m in manifest if 'mismatch' in m)}")


if __name__ == "__main__":
    main()
