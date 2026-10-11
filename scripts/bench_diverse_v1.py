# -*- coding: utf-8 -*-
"""Benchmark re-run: diverse planner prevents repetition BEFORE rendering.

Same topic/narration/audio/captions/render-chain as bench_director_v1.
Differences: shots come from plan_shots_diverse (memory+budget+validate+
repair); NO fit-stage workaround; hook split executed as logged planner
repair when the validator demands it.
Usage: python scripts/bench_diverse_v1.py <project_dir>
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, ".")
import bench_director_v1 as B
from engine.core.media import probe
from engine.creative import motion as _motion
from engine.rendering.ffmpeg import (
    apply_vf, burn_subtitles, color_clip, concat, extract_audio, fade_audio,
    fit_filter, gain_audio, make_silence, mix_audio, mux, trim)
from engine.tools import audio_director as _ad
from engine.tools import contract_schema as _cs
from engine.tools import diversity as _dv
from engine.tools import quality_score as _qs
from engine.tools import reviewer2 as _r2
from engine.tools import visual_director as _vd
from engine.tools import visual_plan as _vp

W, H, FPS = 1080, 1920, 30
L1_AT, GAP = B.L1_AT, B.GAP
L1, L3 = B.L1, B.L3
L3_AT = L1_AT + L1[1] + GAP
TOTAL = round(L3_AT + L3[1] + 3.65, 2)


def main():
    proot = Path(sys.argv[1])
    t0 = time.time()
    work = proot / "renders" / "work"
    (proot / "timeline").mkdir(parents=True, exist_ok=True)
    work.mkdir(parents=True, exist_ok=True)
    log: dict = {"planner": "plan_shots_diverse", "rounds": []}

    # Beat-aligned planning scenes: one need per story beat (audio and
    # captions still follow the two narration spans L1/L3).
    narr = [
        {"id": "S1", "span": [1.5, 7.0], "text": "hook question",
         "need": "neon abstract technology question",
         "visual": "high impact opener"},
        {"id": "S2", "span": [7.0, 18.0], "text": "team workload problem",
         "need": "typing keyboard work team",
         "visual": "human workload"},
        {"id": "S3", "span": [18.0, 31.0], "text": "ai transformation",
         "need": "code programming data screen",
         "visual": "systems at work"},
        {"id": "S4", "span": [31.0, 44.638], "text": "examples montage",
         "need": "laptop startup idea screen",
         "visual": "tools in use"},
        {"id": "S5", "span": [45.138, 58.0], "text": "human decides",
         "need": "handshake people collaboration human",
         "visual": "human presence"},
        {"id": "S6", "span": [58.0, 75.238], "text": "future payoff",
         "need": "city aerial future scale",
         "visual": "cinematic resolve"},
    ]
    plan = _vp.plan_shots_diverse(narr, B.POOL, voice_mode="NARRATED",
                                  seed=7)
    log["planner_decisions"] = plan["log"]
    log["planner_repairs"] = plan["repaired"]
    log["validation_pre"] = plan["validation"]["verdict"]
    # Planner-level repair: hook split when validator demands it.
    shots = list(plan["shots"])
    hook_fail = any(f["dimension"] == "hook" and f["severity"] == "FAIL"
                    for f in plan["validation"]["findings"])
    if hook_fail:
        first = min([s for s in shots if s.get("asset")],
                    key=lambda s: s["start"])
        a, b = first["start"], first["end"]
        thirds = [a, a + (b - a) / 3, a + 2 * (b - a) / 3, b]
        pool_dur = {x["file"]: x["dur"] for x in B.POOL}
        new_tail = []
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
                    new_tail.append(c)
            else:
                new_tail.append(s)
        shots = sorted(new_tail, key=lambda s: s["start"])
        log["rounds"].append({"round": "planner-repair",
                              "fix": "hook montage split",
                              "shot": first["shot_id"]})
    # Fit check (planner must stand on its own: no fit workaround)
    pool_dur = {x["file"]: x["dur"] for x in B.POOL}
    unfitting = [s["shot_id"] for s in shots
                 if s.get("asset") and
                 pool_dur.get(s["asset"], 99) < (s["end"] - s["start"])]
    log["unfitting_picks"] = unfitting
    # RENDER video (deterministic spans/filters/encoders)
    parts, cursor = [], 0.0
    card = work / "tcard.mp4"
    color_clip(B.CARD, W, H, 1.5, card, fps=FPS)
    parts.append(card)
    cursor = 1.5
    for i, sh in enumerate(shots):
        dur = round(sh["end"] - sh["start"], 2)
        fn = sh.get("asset") or "CARD"
        if fn == "CARD" or fn is None:
            p = work / f"dv{i:02d}.mp4"
            color_clip(B.CARD, W, H, dur, p, fps=FPS)
        else:
            info = probe(B.ARS / fn)
            off = float(sh.get("src_off", (i * 1.7) %
                               max(0.1, pool_dur.get(fn, 99) - dur)))
            tmp = work / f"draw{i:02d}.mp4"
            trim(B.ARS / fn, off, round(off + dur, 2), tmp,
                 encoder="h264_qsv")
            p = work / f"dv{i:02d}.mp4"
            apply_vf(tmp, fit_filter(info.width, info.height, W, H,
                                     "cover", fps=FPS), p, encoder="h264_qsv")
            tmp.unlink(missing_ok=True)
        parts.append(p)
        cursor = round(cursor + probe(p).duration, 3)
    tail = round(TOTAL - cursor, 2)
    endc = work / "tend.mp4"
    color_clip(B.CARD, W, H, tail, endc, fps=FPS)
    parts.append(endc)
    joined = work / "joined.mp4"
    concat(parts, joined, reencode=True, encoder="libx264")
    # AUDIO identical to bench v1 pattern
    n1 = extract_audio(B.NARR / "L1_06.wav", work / "n1.wav", sample_rate=44100,
                       channels=2)
    s05 = make_silence(GAP, work / "s05.wav", sample_rate=44100, channels=2)
    n3 = extract_audio(B.NARR / "L3_06.wav", work / "n3.wav", sample_rate=44100,
                       channels=2)
    lead = make_silence(L1_AT, work / "lead.wav", sample_rate=44100,
                        channels=2)
    tailw = make_silence(round(TOTAL - (L3_AT + L3[1]), 2),
                         work / "tail.wav", sample_rate=44100, channels=2)
    narr = concat([lead, n1, s05, n3, tailw], work / "narr.wav",
                  reencode=False)
    mus = extract_audio(B.MUS, work / "mus.wav", start=2.0, duration=TOTAL,
                        sample_rate=44100, channels=2)
    faded = work / "musf.m4a"
    fade_audio(mus, faded, fade_in=2.0, fade_out=3.0)
    states = _ad.music_plan(
        ["HOOK", "PROBLEM", "EXPLANATION", "PROCESS", "EXAMPLE", "PAYOFF",
         "ENDING"], TOTAL)
    slices = []
    for k, st in enumerate(states):
        sl = work / f"au{k:02d}.m4a"
        extract_audio(faded, sl, start=st["start"],
                      duration=round(st["end"] - st["start"], 3))
        if st["gain_db"]:
            gl = work / f"aug{k:02d}.m4a"
            gain_audio(sl, gl, gain_db=st["gain_db"])
            sl.unlink(missing_ok=True)
            sl = gl
        slices.append(sl)
    bed = work / "bed.m4a"
    concat(slices, bed, reencode=False)
    bedw = extract_audio(bed, work / "bed.wav", sample_rate=44100,
                         channels=2)
    sting = extract_audio(B.STING, work / "st0.m4a", start=0.0, duration=1.2)
    sting_q = work / "stq.m4a"
    gain_audio(sting, sting_q, gain_db=-12.0)
    mixed = mix_audio([narr, bedw, sting_q], work / "mixed.m4a")
    safe = gain_audio(mixed, work / "safe.m4a", gain_db=-1.5)
    muxed = work / "muxed.mp4"
    mux(joined, safe, muxed)

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
    ass = proot / "timeline" / "bench.ass"
    ass.write_text(head + "\n".join(evs) + "\n", encoding="utf-8")
    stamp = time.strftime("%Y%m%d_%H%M%S")
    final = proot / "renders" / f"bench_diverse_{stamp}.mp4"
    burn_subtitles(muxed, ass, final, encoder="h264_qsv")
    info = probe(final)
    (proot / "timeline" / "build.json").write_text(json.dumps(
        {"duration": round(info.duration, 3), "output": str(final),
         "shots": len(shots), "log": log,
         "elapsed_s": round(time.time() - t0, 1)},
        ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"DIVERSE-BENCH {final} dur={info.duration:.2f} shots={len(shots)} "
          f"pre={plan['validation']['verdict']} "
          f"rounds={len(log['rounds'])}")


if __name__ == "__main__":
    main()
