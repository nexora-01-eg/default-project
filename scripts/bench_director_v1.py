# -*- coding: utf-8 -*-
"""Benchmark: autonomous director path -> 60-90 s narrated video.

Director decides (from topic script + states): beats, shots, assets,
motion, typography, music, sfx. Renderer executes via gateway ops.
Narration: validated Piper lines (L1 hook + L3 ending).
Usage: python scripts/bench_director_v1.py <project_dir>
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, ".")
from engine.autonomy.director import plan_production
from engine.core.media import probe
from engine.creative import motion as _motion
from engine.rendering.ffmpeg import (
    apply_vf, burn_subtitles, color_clip, concat, extract_audio, fade_audio,
    fit_filter, gain_audio, make_silence, mix_audio, mux, trim)
from engine.tools import audio_director as _ad
from engine.tools import contract_schema as _cs
from engine.tools import motion_system as _ms
from engine.tools import quality_score as _qs
from engine.tools import reviewer2 as _r2
from engine.tools import style_contract as _st
from engine.tools import typography as _ty
from engine.tools import visual_director as _vd
from engine.tools import visual_plan as _vp
from engine.tools.router import resolve as _resolve

ARS = Path("F:/Arsenal/MH - محتوى بصري/02-فيديو")
MUS = Path("F:/Arsenal/04_Music/Incompetech/Aitech.mp3")
STING = Path("F:/Arsenal/04_Music/Incompetech/MJS Stings.mp3")
NARR = Path("C:/Users/NOUR SOFT/Documents/Default Project/tools/tts/"
            "piper/tests/narr")
CARD = "0x0B102E"
W, H, FPS = 1080, 1920, 30

POOL = [
    {"file": "107916-679600385_medium.mp4", "w": 2560, "h": 1440,
     "dur": 10.0, "tags": ["neon", "abstract", "glow", "technology"]},
    {"file": "15029082_3840_2160_25fps.mp4", "w": 3840, "h": 2160,
     "dur": 29.28, "tags": ["code", "screen", "programming", "data"]},
    {"file": "251763_medium.mp4", "w": 1440, "h": 2560, "dur": 15.0,
     "tags": ["typing", "keyboard", "hands", "work"]},
    {"file": "92480-637690589_medium.mp4", "w": 1280, "h": 720,
     "dur": 13.3, "tags": ["laptop", "creator", "desk", "work"]},
    {"file": "316712_medium.mp4", "w": 2580, "h": 1440, "dur": 5.21,
     "tags": ["audio", "levels", "processing", "data"]},
    {"file": "358512_medium.mp4", "w": 2560, "h": 1440, "dur": 8.0,
     "tags": ["handshake", "agreement", "people", "collaboration"]},
    {"file": "296958_medium.mp4", "w": 1080, "h": 1920, "dur": 25.13,
     "tags": ["city", "aerial", "scale", "future"]},
    {"file": "6963374-hd_1080_1920_30fps.mp4", "w": 1080, "h": 1920,
     "dur": 11.81, "tags": ["laptop", "startup", "screen", "idea"]},
    {"file": "8373729-hd_1080_1920_25fps.mp4", "w": 1080, "h": 1920,
     "dur": 12.56, "tags": ["desk", "planning", "notebook", "startup"]},
]

SCRIPT = [
    ("زمان كان فريق كامل.", "HOOK"),
    ("دلوقتي المعادلة اتغيّرت.", "PROBLEM"),
    ("السرعة نفسها اتغيّرت.", "EXPLANATION"),
    ("من الفكرة للمونتاج.", "PROCESS"),
    ("تحليل وقص أسرع.", "EXAMPLE"),
    ("القرار لسه للإنسان.", "PAYOFF"),
    ("إنت هتستخدمه إزاي؟", "ENDING"),
]
L1 = ("زمان كان فريق كامل.", 43.138)
L3 = ("القرار قرارك.", 30.1)
L1_AT, GAP = 1.5, 0.5
L3_AT = L1_AT + L1[1] + GAP


def main():
    proot = Path(sys.argv[1])
    t0 = time.time()
    log = {"routing": [], "asset_decisions": []}
    work = proot / "renders" / "work"
    (proot / "timeline").mkdir(parents=True, exist_ok=True)
    work.mkdir(parents=True, exist_ok=True)
    total = round(L3_AT + L3[1] + 3.4, 2)

    # DIRECT (all decisions from meaning)
    plan = plan_production("AI video production", "", "technical", total,
                           "reel", voice_source="piper")
    beats = _vd.direct_script(
        [{"text": t} for t, _ in SCRIPT], [s for _, s in SCRIPT])
    narr = [{"id": "L1", "span": [L1_AT, L1_AT + L1[1]], "text": L1[0],
             "need": "neon technology abstract hook",
             "visual": "high impact opener"},
            {"id": "L3", "span": [L3_AT, L3_AT + L3[1]], "text": L3[0],
             "need": "human scale future payoff",
             "visual": "cinematic resolve"}]
    shots = _vp.storyboard(narr, POOL, voice_mode="NARRATED")
    # enrich with overlapping beat direction
    rich = []
    for sh in shots:
        mid = (sh["start"] + sh["end"]) / 2
        frac = mid / max(total, 0.01)
        bi = min(int(frac * len(beats)), len(beats) - 1)
        beat = beats[bi]
        r = _vp.enrich_shot(dict(sh), beat)
        role = {"HOOK": "INTRO", "PROBLEM": "PROBLEM",
                "EXPLANATION": "BODY", "PROCESS": "PROCESS",
                "EXAMPLE": "KEYWORD", "PAYOFF": "IMPORTANT_FACT",
                "ENDING": "CTA"}.get(beat["state"], "BODY")
        r["motion"] = {"primitive": _ms.motion_grammar(role),
                       "duration": round(sh["end"] - sh["start"], 2)}
        rich.append(r)
    issues = _vp.validate_shots(rich)
    log["shot_validation"] = issues
    # FIT assets to durations (logged, deterministic)
    by_file = {a["file"]: a for a in POOL}
    segs, cursor = [("card", "title", 1.5)], 1.5
    for i, sh in enumerate(rich):
        dur = round(sh["end"] - sh["start"], 2)
        fn = sh.get("asset")
        a = by_file.get(fn or "")
        if not a or a["dur"] < dur:
            alt = sorted(
                [x for x in POOL if x["dur"] >= dur and x["file"] != fn],
                key=lambda x: x["file"])
            if alt:
                log["asset_decisions"].append(
                    {"shot": sh["shot_id"], "was": fn,
                     "now": alt[0]["file"], "reason": "duration fit"})
                fn, a = alt[0]["file"], alt[0]
            else:
                log["asset_decisions"].append(
                    {"shot": sh["shot_id"], "was": fn, "now": "CARD",
                     "reason": "no fit -> procedural card"})
                segs.append(("card", sh["shot_id"], dur))
                cursor = round(cursor + dur, 2)
                continue
        start = round((i * 1.7) % max(0.1, a["dur"] - dur), 2)
        segs.append(("clip", fn, (start, round(start + dur, 2)),
                     sh["shot_id"]))
        cursor = round(cursor + dur, 2)
    tail = round(total - cursor, 2)
    segs.append(("card", "endcard", tail))
    # style contract check
    srecs = [{"shot_id": s[1] if s[0] == "card" else s[3], "texts": [],
              "motion": "push"} for s in segs]
    log["style"] = _st.check_production(srecs)
    # music + sfx from story states
    states = [b["state"] for b in beats]
    mstates = _ad.music_plan(states, total)
    sfx = [_ad.sfx_for(b["state"], 1.5 if i == 0 else 0.0)
           for i, b in enumerate(beats) if b["state"] in ("HOOK", "STATISTIC",
                                                          "PAYOFF")]
    # RENDER video
    parts = []
    for i, s in enumerate(segs):
        if s[0] == "card":
            p = work / f"v{i:02d}.mp4"
            color_clip(CARD, W, H, s[2], p, fps=FPS)
        else:
            _, fn, (a, b), _label = s
            info = probe(ARS / fn)
            tmp = work / f"raw{i:02d}.mp4"
            trim(ARS / fn, a, b, tmp, encoder="h264_qsv")
            p = work / f"v{i:02d}.mp4"
            apply_vf(tmp, fit_filter(info.width, info.height, W, H,
                                     "cover", fps=FPS), p, encoder="h264_qsv")
            tmp.unlink(missing_ok=True)
        parts.append(p)
    joined = work / "joined.mp4"
    concat(parts, joined, reencode=True, encoder="libx264")
    # RENDER audio: narration + ducked bed + sting
    n1 = extract_audio(NARR / "L1_06.wav", work / "n1.wav", sample_rate=44100,
                       channels=2)
    s05 = make_silence(GAP, work / "s05.wav", sample_rate=44100, channels=2)
    n3 = extract_audio(NARR / "L3_06.wav", work / "n3.wav", sample_rate=44100,
                       channels=2)
    lead = make_silence(L1_AT, work / "lead.wav", sample_rate=44100,
                        channels=2)
    tailw = make_silence(round(total - (L3_AT + L3[1]), 2),
                         work / "tail.wav", sample_rate=44100, channels=2)
    narr = concat([lead, n1, s05, n3, tailw], work / "narr.wav",
                  reencode=False)
    mus = extract_audio(MUS, work / "mus.wav", start=2.0, duration=total,
                        sample_rate=44100, channels=2)
    faded = work / "musf.m4a"
    fade_audio(mus, faded, fade_in=2.0, fade_out=3.0)
    slices = []
    for k, st in enumerate(mstates):
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
    sting = extract_audio(STING, work / "st0.m4a", start=0.0, duration=1.2)
    sting_q = work / "stq.m4a"
    gain_audio(sting, sting_q, gain_db=-12.0)
    mixed = mix_audio([narr, bedw, sting_q], work / "mixed.m4a")
    safe = gain_audio(mixed, work / "safe.m4a", gain_db=-1.5)
    muxed = work / "muxed.mp4"
    mux(joined, safe, muxed)
    # captions: verbatim narration cues + keywords
    from engine.creative import motion as _motion
    head = ("[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: "
            "1920\nScaledBorderAndShadow: yes\n\n[V4+ Styles]\n"
            "Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, "
            "BackColour, Bold, Alignment, MarginV\n"
            "Style: Title,Arial,104,&H00FFD98A,&H80000000,&H80000000,1,5,120\n"
            "Style: Body,Arial,54,&H00FFFFFF,&H90000000,&H90000000,1,2,190\n"
            "Style: Key,Arial,70,&H00FFD98A,&H90000000,&H90000000,1,8,230\n"
            "Style: End,Arial,84,&H00FFD98A,&H80000000,&H80000000,1,5,120\n\n"
            "[Events]\nFormat: Layer, Start, End, Style, Text\n")

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
        f"Dialogue: 0,{T(total - 3.4)},{T(total)},End,"
        f"{_motion.fade(400)}القرار…\\Nقرارك إنت",
    ]
    ass = proot / "timeline" / "bench.ass"
    ass.write_text(head + "\n".join(evs) + "\n", encoding="utf-8")
    stamp = time.strftime("%Y%m%d_%H%M%S")
    final = proot / "renders" / f"bench_director_{stamp}.mp4"
    burn_subtitles(muxed, ass, final, encoder="h264_qsv")
    info = probe(final)
    # contract record + validation
    contract = {
        "project": proot.name, "canvas": {"w": W, "h": H, "fps": FPS},
        "voice": {"mode": "TEMPORARY_ARABIC_TTS", "voice": "ar_JO-kareem"},
        "narration": {"segments": [
            {"id": "L1", "text": L1[0], "start": L1_AT},
            {"id": "L3", "text": L3[0], "start": L3_AT}]},
        "shots": [{"shot_id": s[1] if s[0] == "card" else s[3],
                   "start": 0.0, "end": 1.0} for s in segs],
        "audio": {"music_states": mstates,
                  "sfx": [x for x in sfx if x["kind"] != "none"]},
        "review": { "beats": len(beats) } }
    cval = _cs.validate_contract(contract)
    (proot / "timeline" / "director.json").write_text(json.dumps(
        {"beats": beats, "shots": len(rich), "segments": len(segs),
         "music_states": mstates, "sfx": sfx, "contract_valid": cval,
         "log": log}, ensure_ascii=False, indent=1), encoding="utf-8")
    (proot / "timeline" / "build.json").write_text(json.dumps(
        {"duration": round(info.duration, 3), "output": str(final),
         "elapsed_s": round(time.time() - t0, 1)},
        ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"BENCH {final} dur={info.duration:.2f} shots={len(rich)} "
          f"contract={cval['valid']}")


if __name__ == "__main__":
    main()
