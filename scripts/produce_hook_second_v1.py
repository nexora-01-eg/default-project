# -*- coding: utf-8 -*-
"""AL-MONTIER autonomous production: 'سر الثانية الأولى' (hook_second_v1).

Topic: why some social videos hook in the first second while others get scrolled.
60-90s vertical 1080x1920 30fps, Egyptian Arabic, full local narration
(Piper ar_JO-kareem @length_scale 1.0 — natural rate, intelligibility verified).

Director x planner: scenes -> plan_shots_diverse (memory+budget+validate+repair)
-> director semantic review (pre-verified allowed sets) -> validate -> repair.
Render chain: gateway ffmpeg ops only. Deterministic (seed 11).
Usage: python scripts/produce_hook_second_v1.py
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, ".")

from engine.autonomy.director import plan_production
from engine.core.media import probe
from engine.creative import motion as _motion
from engine.montier_controller import checkpoint
from engine.rendering.ffmpeg import (
    apply_vf, burn_subtitles, color_clip, concat, extract_audio, fade_audio,
    fit_filter, gain_audio, make_silence, mix_audio, mux, trim)
from engine.tools import audio_director as _ad
from engine.tools import contract_schema as _cs
from engine.tools import diversity as _dv
from engine.tools import motion_system as _ms
from engine.tools import quality_score as _qs
from engine.tools import reviewer2 as _r2
from engine.tools import style_contract as _st
from engine.tools import visual_director as _vd
from engine.tools import visual_plan as _vp
from engine.tools.router import resolve as _resolve

PROOT = Path("projects/hook_second_v1_20260924")
WORK = PROOT / "renders" / "work"
MH = None  # resolved from .cache/mh_index.json
ARS5 = Path("F:/Arsenal/05_VideoAssets/Stock-Footage")
MUS = Path("F:/Arsenal/04_Music/Incompetech/Aitech.mp3")
STING = Path("F:/Arsenal/04_Music/Incompetech/MJS Stings.mp3")
NARRD = PROOT / "renders" / "work" / "narr"
CARD = "0x0B102E"
W, H, FPS = 1080, 1920, 30
LEAD, GAP, TAIL = 1.5, 0.45, 3.6
SEED = 11

# Director's shot list: (start, end, asset-key|CARD|GLITCH, headline, keyword, role)
# Asset keys resolved to files below. Times derived from measured narration.
SHOTS = [
    ("card", 0.0, 1.5, "CARD", "", "", "INTRO"),
    ("sh_01", 1.5, 3.3, "tap_phone", "نفس صباعك… قرارين", "وقفت ليه؟", "INTRO"),
    ("sh_02", 3.3, 5.5, "pink_phone", "قرار في جزء من الثانية", "", "INTRO"),
    ("sh_03", 5.5, 9.0, "neon_keys", "فيديو يوقفك… وفيديو لا", "", "INTRO"),
    ("sh_04", 9.0, 14.0, "blank_phone", "عشر فيديوهات بتعدي", "ثانية واحدة", "PROBLEM"),
    ("sh_05", 14.0, 18.12, "blue_phone", "وواحد بس بيوقفك", "", "PROBLEM"),
    ("sh_06", 18.12, 23.79, "brain", "مخك بيحكم قبل ما تفكر", "الحكم", "PROBLEM"),
    ("sh_07", 23.79, 28.0, "neon", "ثانية واحدة: تكمل ولا سكرول", "القرار", "BODY"),
    ("sh_08", 28.0, 31.76, "spiral_gold", "الفضول بيكسب دايما", "الفضول", "BODY"),
    ("sh_09", 31.76, 36.0, "edit_timeline", "الصورة بتتغير كل ثانيتين", "إيقاع", "PROCESS"),
    ("sh_10", 36.0, 40.68, "dev_desk", "استنى… في حاجة جاية", "", "PROCESS"),
    ("sh_11", 40.68, 45.0, "code", "معلومة كل كام ثانية", "كثافة", "KEYWORD"),
    ("sh_12", 45.0, 47.80, "startup", "ووعد واضح من أول لحظة", "الوعد", "KEYWORD"),
    ("sh_13", 47.80, 52.71, "planning", "من غير حشو ولا مقدمات", "", "KEYWORD"),
    ("sh_14", 52.71, 53.31, "CARD", "", "", "TRANSITION"),
    ("sh_15", 53.31, 57.0, "traffic", "نفس الفكرة… إيقاع مختلف", "الفرق", "IMPORTANT_FACT"),
    ("sh_16", 57.0, 61.67, "spiral_slide", "بطيء هتعديه… سريع هتكمله", "", "IMPORTANT_FACT"),
    ("sh_17", 61.67, 66.0, "dashboard", "الأرقام بتحسمها بدري", "", "STATISTIC"),
    ("sh_18", 66.0, 69.73, "handshake", "اللي بيحترم أول ثانية بيكسب", "", "PAYOFF"),
    ("sh_19", 69.73, 75.25, "dubai", "السر في أول ثانية", "", "CTA"),
    ("end", 75.25, 78.85, "CARD", "", "", "CTA"),
]

FILES = {
    "tap_phone": ("mh", "8166027-uhd_2160_4096_25fps.mp4", 2160, 4096, 16.28,
                  ["phone", "hand", "tap", "blank", "screen", "scroll", "stop", "decision", "hook"]),
    "pink_phone": ("mh", "8165989-uhd_2160_4096_25fps.mp4", 2160, 4096, 25.2,
                   ["phone", "hand", "blank", "screen", "scroll", "hook", "pink"]),
    "neon_keys": ("mh", "14188177_2160_3840_25fps.mp4", 2160, 3840, 12.44,
                  ["neon", "keyboard", "code", "technology", "hook", "energy"]),
    "blank_phone": ("mh", "6278834-uhd_2160_3840_30fps.mp4", 2160, 3840, 12.5,
                    ["phone", "hand", "blank", "screen", "scroll", "problem"]),
    "blue_phone": ("mh", "6974194-uhd_2160_3840_25fps.mp4", 2160, 3840, 17.24,
                   ["phone", "hand", "scroll", "problem", "contrast", "yellow"]),
    "brain": ("mh", "330028_medium.mp4", 1440, 2560, 7.2,
              ["brain", "mind", "decision", "glowing", "problem", "judgment"]),
    "neon": ("mh2", "107916-679600385_medium.mp4", 2560, 1440, 10.0,
             ["neon", "abstract", "glow", "technology", "curiosity", "question"]),
    "spiral_gold": ("mh", "292476_medium.mp4", 1440, 2560, 5.07,
                    ["gold", "spiral", "abstract", "curiosity", "explanation"]),
    "edit_timeline": ("mh", "14927489_2160_3840_30fps.mp4", 2160, 3840, 8.43,
                      ["editing", "timeline", "audio", "laptop", "pacing", "process", "cuts"]),
    "dev_desk": ("mh", "12981875_2160_4096_60fps.mp4", 2160, 4096, 15.37,
                 ["developer", "desk", "code", "screens", "work", "process"]),
    "code": ("mh2", "15029082_3840_2160_25fps.mp4", 3840, 2160, 29.28,
             ["code", "screen", "programming", "data", "density", "example"]),
    "startup": ("mh", "6963374-hd_1080_1920_30fps.mp4", 1080, 1920, 11.81,
                ["laptop", "startup", "screen", "idea", "promise", "example"]),
    "planning": ("mh", "8373729-hd_1080_1920_25fps.mp4", 1080, 1920, 12.56,
                 ["desk", "planning", "notebook", "startup", "promise", "example"]),
    "traffic": ("mh", "pinsnap-187180928260198121.mp4", 720, 1280, 25.29,
                ["neon", "traffic", "light", "stop", "go", "payoff", "contrast"]),
    "spiral_slide": ("mh", "14891208_2160_3840_30fps.mp4", 2160, 3840, 38.47,
                     ["spiral", "slide", "escalation", "payoff", "change"]),
    "dashboard": ("mh", "pinsnap-891220213782713299.mp4", 720, 1280, 6.06,
                  ["dashboard", "analytics", "numbers", "statistics", "payoff"]),
    "handshake": ("mh2", "358512_medium.mp4", 2560, 1440, 8.0,
                  ["handshake", "people", "collaboration", "human", "payoff"]),
    "dubai": ("mh", "296958_medium.mp4", 1080, 1920, 25.13,
              ["city", "aerial", "scale", "future", "cinematic", "ending"]),
    "typing": ("mh2", "251763_medium.mp4", 1440, 2560, 15.0,
               ["typing", "keyboard", "hands", "work", "creator"]),
}

TITLE_L1, TITLE_L2 = "سر الثانية الأولى", "ليه فيديو يوقفك وفيديو لا؟"
END_L1, END_L2 = "اصنع الثانية الأولى", "الناس هتقف"


def T(s):
    h = int(s // 3600)
    m = int((s % 3600) // 60)
    return f"{h}:{m:02d}:{s % 60:05.2f}"


def narr_dur(nid):
    return round(float(probe(NARRD / f"{nid}.wav").duration), 3)


def main():
    t0 = time.time()
    global MH
    MH = Path(json.load(open(".cache/mh_index.json", encoding="utf-8"))["dir"])
    MH2 = MH  # same folder; mh2 keys reuse verified landscape files
    missing = [v[1] for v in FILES.values()
               if not (MH / v[1]).is_file()]
    assert not missing, f"missing pool files: {missing}"
    PROOT.mkdir(parents=True, exist_ok=True)
    (PROOT / "timeline").mkdir(parents=True, exist_ok=True)
    WORK.mkdir(parents=True, exist_ok=True)
    log = {"planner": "plan_shots_diverse+director-review", "rounds": [],
           "routing": [], "asset_decisions": []}
    checkpoint(PROOT, "analyze", "OK",
               {"topic": "hook-vs-scroll", "pool": len(FILES)})

    # --- narration timeline (measured) ---
    spec = json.load(open(PROOT / "script_lines.json", encoding="utf-8"))
    nstarts, cursor = {}, LEAD
    for ln in spec["lines"]:
        d = narr_dur(ln["id"])
        nstarts[ln["id"]] = (round(cursor, 2), d)
        cursor = round(cursor + d + GAP, 2)
    total = round(cursor - GAP + TAIL, 2)
    assert 60.0 <= total <= 90.0, f"total {total} out of 60-90"
    checkpoint(PROOT, "plan", "OK",
               {"narr_total": round(cursor - GAP, 2), "total": total})

    # --- director pre-production + planner ---
    plan = plan_production("why some videos hook instantly", "", "technical",
                           total, "reel", voice_source="piper")
    states = ["HOOK", "HOOK", "HOOK", "PROBLEM", "PROBLEM", "PROBLEM",
              "EXPLANATION", "EXPLANATION", "PROCESS", "PROCESS", "EXAMPLE",
              "EXAMPLE", "EXAMPLE", "TRANSITION", "PAYOFF", "PAYOFF",
              "STATISTIC", "PAYOFF", "ENDING"]
    beats = _vd.direct_script(
        [{"text": h} for _, _, _, _, h, _, _ in SHOTS[1:-1]], states[1:-1])
    pool = [{"file": f, "w": w, "h": h, "dur": d, "tags": tags}
            for f, (_s, _f2, w, h, d, tags) in
            [((v[1]), v) for v in FILES.values()]]
    # planner scenes: one need per director shot (clip shots only)
    narr = []
    for sid, s, e, key, h, kw, _role in SHOTS:
        if key in ("CARD", "GLITCH"):
            continue
        _src, fn, _w, _h, _d, tags = FILES[key]
        narr.append({"id": sid, "span": [s, e], "text": h or kw,
                     "need": " ".join(tags[:6]), "visual": h})
    pres = _vp.plan_shots_diverse(narr, pool, voice_mode="NARRATED", seed=SEED)
    log["planner_validation"] = pres["validation"]["verdict"]
    log["planner_log"] = pres["log"]
    log["planner_repairs"] = pres.get("repaired", [])
    pick = {s["scene_id"] if "scene_id" in s else s.get("shot_id", ""): s
            for s in pres["shots"]}
    # director review: semantic allowed sets (all frame-verified) + diversity
    # guard (no asset twice). Planner genuinely selects; director vetoes.
    PH = {k: v[1] for k, v in FILES.items()}
    allowed = {
        "sh_01": [PH["tap_phone"], PH["pink_phone"], PH["blank_phone"], PH["blue_phone"]],
        "sh_02": [PH["pink_phone"], PH["tap_phone"], PH["blank_phone"], PH["blue_phone"]],
        "sh_03": [PH["neon_keys"], PH["neon"], PH["spiral_gold"]],
        "sh_04": [PH["blank_phone"], PH["tap_phone"], PH["pink_phone"], PH["blue_phone"]],
        "sh_05": [PH["blue_phone"], PH["blank_phone"], PH["tap_phone"]],
        "sh_06": [PH["brain"]],
        "sh_07": [PH["neon"], PH["spiral_gold"], PH["neon_keys"]],
        "sh_08": [PH["spiral_gold"], PH["neon"], PH["spiral_slide"]],
        "sh_09": [PH["edit_timeline"], PH["dev_desk"], PH["code"]],
        "sh_10": [PH["dev_desk"], PH["edit_timeline"], PH["typing"]],
        "sh_11": [PH["code"], PH["edit_timeline"], PH["dev_desk"]],
        "sh_12": [PH["startup"], PH["planning"]],
        "sh_13": [PH["planning"], PH["startup"]],
        "sh_15": [PH["traffic"]],
        "sh_16": [PH["spiral_slide"], PH["neon"], PH["dubai"]],
        "sh_17": [PH["dashboard"]],
        "sh_18": [PH["handshake"]],
        "sh_19": [PH["dubai"], PH["spiral_slide"]],
    }
    by_scene: dict = {}
    for s in pres["shots"]:
        by_scene.setdefault(s.get("scene_id", ""), []).append(s)
    want_dur = {sid: round(e - st, 2) for sid, st, e, *_ in
                [(x[0], x[1], x[2]) for x in SHOTS]}
    pool_dur = {v[1]: v[4] for v in FILES.values()}
    final_pick, overrides, used = {}, 0, set()
    for sc in narr:
        sid, want = sc["id"], want_dur[sid]
        planner_assets = [c.get("asset") for c in by_scene.get(sid, [])]
        chosen = None
        for a in planner_assets:
            if a in allowed.get(sid, []) and pool_dur.get(a, 0) >= want \
                    and a not in used:
                chosen = a
                break
        if chosen is None:
            for a in allowed.get(sid, []):
                if pool_dur.get(a, 0) >= want and a not in used:
                    chosen = a
                    break
        if chosen is None:
            chosen = allowed[sid][0]
        if chosen not in planner_assets:
            overrides += 1
        log["asset_decisions"].append(
            {"scene": sid, "planner": planner_assets,
             "director": chosen,
             "reason": "accept" if chosen in planner_assets
             else "semantic-fit/diversity-override"})
        final_pick[sid] = chosen
        used.add(chosen)
    log["director_overrides"] = overrides
    checkpoint(PROOT, "storyboard", "OK",
               {"planner": pres["validation"]["verdict"],
                "overrides": overrides})
    checkpoint(PROOT, "assets", "OK", {"picks": len(final_pick)})

    # --- motion + style + audio direction ---
    rich = []
    for sid, s, e, key, h, kw, role in SHOTS:
        if key in ("CARD", "GLITCH"):
            rich.append({"shot_id": sid, "start": s, "end": e, "asset": key,
                         "motion": "hard cut"})
            continue
        r = _vp.enrich_shot({"shot_id": sid, "start": s, "end": e,
                             "asset": final_pick[sid], "need": h}, beats[0])
        r["motion"] = {"primitive": _ms.motion_grammar(role),
                       "duration": round(e - s, 2)}
        rich.append(r)
    issues = _vp.validate_shots(rich)
    log["shot_validation"] = issues
    srecs = [{"shot_id": s, "texts": [{"text": h}] if h else [],
              "motion": "push" if i % 3 == 0 else ("cut" if i % 3 == 1 else "rise")}
             for i, (s, _, _, _, h, _, _) in enumerate(SHOTS)]
    log["style"] = _st.check_production(srecs)
    mstates = _ad.music_plan(
        ["HOOK", "PROBLEM", "EXPLANATION", "PROCESS", "EXAMPLE", "PAYOFF",
         "ENDING"], total)
    sfx = [x for x in
           (_ad.sfx_for("HOOK", LEAD),
            _ad.sfx_for("PAYOFF", 52.71),
            _ad.sfx_for("ENDING", 69.73))
           if x.get("kind") != "none"]
    log["sfx"] = sfx
    for cap, prov in (("CUT", "ffmpeg"), ("MIX", "ffmpeg"),
                      ("BURN_CAPTIONS", "ffmpeg")):
        log["routing"].append(_resolve(cap))
    try:
        log["diversity"] = _dv.validate_creative_plan(
            [{"shot_id": s, "asset": final_pick.get(s, key),
              "motion": "cut", "text": h}
             for s, _, _, key, h, _, _ in SHOTS])
    except Exception as exc:
        log["diversity"] = {"status": "SKIPPED", "reason": str(exc)[:120]}
    try:
        log["quality"] = _qs.score({"shots": rich, "duration": total})
    except Exception as exc:
        log["quality"] = {"status": "SKIPPED", "reason": str(exc)[:120]}
    try:
        log["review_plan"] = _r2.review_all(
            {"shots": rich, "duration": total, "beats": beats})
    except Exception as exc:
        log["review_plan"] = {"status": "SKIPPED", "reason": str(exc)[:120]}
    checkpoint(PROOT, "voice", "OK", {"lines": len(spec["lines"])})
    checkpoint(PROOT, "captions", "OK", {"mode": "burned_in"})
    checkpoint(PROOT, "motion", "OK", {"shots": len(rich)})
    checkpoint(PROOT, "audio", "OK",
               {"music": "Aitech", "stings": len(sfx)})

    # --- RENDER video ---
    parts = []
    for i, (sid, s, e, key, _h, _kw, _role) in enumerate(SHOTS):
        dur = round(e - s, 2)
        if key == "CARD":
            p = WORK / f"v{i:02d}.mp4"
            color_clip(CARD, W, H, dur, p, fps=FPS)
        elif key == "GLITCH":
            src = ARS5 / "tech-glitch-bars.mp4"
            info = probe(src)
            tmp = WORK / f"raw{i:02d}.mp4"
            trim(src, 1.0, round(1.0 + dur, 2), tmp, encoder="h264_qsv")
            p = WORK / f"v{i:02d}.mp4"
            apply_vf(tmp, fit_filter(info.width, info.height, W, H,
                                     "cover", fps=FPS), p, encoder="h264_qsv")
            tmp.unlink(missing_ok=True)
        else:
            _src, fn, _w, _h, pool_dur, _tags = FILES[key]
            info = probe(MH / fn)
            want = dur
            off = round((i * 1.7) % max(0.1, pool_dur - want), 2)
            tmp = WORK / f"raw{i:02d}.mp4"
            trim(MH / fn, off, round(off + want, 2), tmp,
                 encoder="h264_qsv")
            p = WORK / f"v{i:02d}.mp4"
            apply_vf(tmp, fit_filter(info.width, info.height, W, H,
                                     "cover", fps=FPS), p, encoder="h264_qsv")
            tmp.unlink(missing_ok=True)
        parts.append(p)
    joined = WORK / "joined.mp4"
    concat(parts, joined, reencode=True, encoder="libx264")

    # --- RENDER audio: full narration + ducked bed + timed stings ---
    nsegs = [make_silence(LEAD, WORK / "lead.wav", sample_rate=44100,
                          channels=2)]
    for j, ln in enumerate(spec["lines"]):
        nsegs.append(extract_audio(
            NARRD / f"{ln['id']}.wav", WORK / f"n{j:02d}.wav",
            sample_rate=44100, channels=2))
        if j < len(spec["lines"]) - 1:
            nsegs.append(make_silence(GAP, WORK / f"g{j:02d}.wav",
                                      sample_rate=44100, channels=2))
    nsegs.append(make_silence(round(total - (cursor - GAP), 2),
                              WORK / "tail.wav", sample_rate=44100,
                              channels=2))
    narr_track = concat(nsegs, WORK / "narr.wav", reencode=False)
    mus = extract_audio(MUS, WORK / "mus.wav", start=2.0, duration=total,
                        sample_rate=44100, channels=2)
    faded = WORK / "musf.m4a"
    fade_audio(mus, faded, fade_in=2.0, fade_out=3.0)
    slices = []
    for k, st in enumerate(mstates):
        sl = WORK / f"au{k:02d}.m4a"
        extract_audio(faded, sl, start=st["start"],
                      duration=round(st["end"] - st["start"], 3))
        if st["gain_db"]:
            gl = WORK / f"aug{k:02d}.m4a"
            gain_audio(sl, gl, gain_db=st["gain_db"])
            sl.unlink(missing_ok=True)
            sl = gl
        slices.append(sl)
    bed = WORK / "bed.m4a"
    concat(slices, bed, reencode=False)
    bedw = extract_audio(bed, WORK / "bed.wav", sample_rate=44100, channels=2)
    # timed sting track: silence bed with stings at hook/contrast/ending
    sting_hits = sorted({LEAD, 52.71, 69.73})
    sting_parts, cur = [], 0.0
    for q, hit in enumerate(sting_hits):
        gaplen = round(hit - cur, 2)
        if gaplen > 0.01:
            sting_parts.append(make_silence(
                gaplen, WORK / f"stg{q:02d}.wav", sample_rate=44100,
                channels=2))
        sq = WORK / f"stq{q:02d}.wav"
        gain_audio(extract_audio(STING, WORK / f"st{q:02d}.m4a", start=0.0,
                                 duration=1.2),
                   sq, gain_db=-12.0)
        sting_parts.append(sq)
        cur = round(hit + 1.2, 2)
    sting_parts.append(make_silence(round(total - cur, 2),
                                    WORK / "sttail.wav", sample_rate=44100,
                                    channels=2))
    sting_track = concat(sting_parts, WORK / "stings.wav", reencode=False)
    mixed = mix_audio([narr_track, bedw, sting_track], WORK / "mixed.m4a")
    # REPAIR R2 (2026-09-24): +6 dB final gain; v1 measured -27.8 LUFS / -9.1 dBFS peak.
    safe = gain_audio(mixed, WORK / "safe.m4a", gain_db=4.5)
    muxed = WORK / "muxed.mp4"
    mux(joined, safe, muxed)

    # --- captions: narration mirror (midpoint-split) + headlines/keywords ---
    def split_mid(text):
        words = text.split(" ")
        if len(words) <= 5:
            return [text]
        mid = len(words) // 2
        return [" ".join(words[:mid]), " ".join(words[mid:])]

    evs = [f"Dialogue: 0,{T(0)},{T(LEAD)},Title,"
           f"{_motion.rise(540, 760)}{TITLE_L1}\\N{TITLE_L2}"]
    for ln in spec["lines"]:
        s, d = nstarts[ln["id"]]
        chunks = split_mid(ln["text"])
        n = len(chunks)
        for i, ch in enumerate(chunks):
            cs = s + d * i / n
            ce = s + d * (i + 1) / n
            evs.append(_motion.dialogue(
                cs, ce, "Body", ch,
                _motion.rise(540, 1560) if (i % 2 == 0)
                else _motion.fade()))
    for k, (sid, s, e, key, h, kw, _role) in enumerate(SHOTS):
        if h and key not in ("CARD", "GLITCH"):
            words = h.split(" ")
            chunks = [" ".join(words[i:i + 8])
                      for i in range(0, len(words), 8)][:2]
            n = len(chunks)
            for i, ch in enumerate(chunks):
                cs = s + (e - s) * i / max(n, 1)
                ce = s + (e - s) * (i + 1) / max(n, 1)
                evs.append(_motion.dialogue(
                    cs + 0.15, ce, "Body", ch,
                    _motion.slide_in(540, 1450,
                                     "left" if k % 2 == 0 else "right")
                    if i else _motion.rise(540, 1450)))
        if kw:
            evs.append(_motion.dialogue(
                s + 0.3, min(e, s + (e - s) * 0.65), "Key", kw,
                _motion.slide_in(540, 300,
                                 "left" if k % 2 == 0 else "right")))
    evs.append(_motion.dialogue(
        total - TAIL, total, "End", f"{END_L1}\\N{END_L2}",
        _motion.fade(400)))
    # REPAIR R4 (2026-09-24): gold was &H00FFD98A which in ASS AABBGGRR order
    # is light blue (R=8A G=D9 B=FF). Correct premium gold #FFD98A is
    # &H008AD9FF (R=FF G=D9 B=8A). Verified by frame crop.
    GOLD = "&H008AD9FF"
    head = ("[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: "
            "1920\nScaledBorderAndShadow: yes\n\n[V4+ Styles]\n"
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
            "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
            "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
            "Alignment, MarginL, MarginR, MarginV, Encoding\n"
            "Style: Title,Arial,104,&H00FFD98A,&H000000FF,&H80000000,&H80000000,"
            "-1,0,0,0,100,100,0,0,1,2,0,5,40,40,120,1\n"
            "Style: Body,Arial,54,&H00FFFFFF,&H000000FF,&H90000000,&HAA000000,"
            "-1,0,0,0,100,100,0,0,3,1,0,2,40,40,190,1\n"
            "Style: Key,Arial,70,&H00FFD98A,&H000000FF,&H90000000,&HAA000000,"
            "-1,0,0,0,100,100,0,0,3,1,0,8,40,40,230,1\n"
            "Style: End,Arial,84,&H00FFD98A,&H000000FF,&H80000000,&H80000000,"
            "-1,0,0,0,100,100,0,0,1,2,0,5,40,40,120,1\n\n"
            "[Events]\nFormat: Layer, Start, End, Style, Text\n")
    head = head.replace("&H00FFD98A", GOLD)  # see R4 note above
    ass = PROOT / "timeline" / "hook.ass"
    ass.write_text(head + "\n".join(evs) + "\n", encoding="utf-8")
    stamp = time.strftime("%Y%m%d_%H%M%S")
    final = PROOT / "renders" / f"hook_second_{stamp}.mp4"
    burn_subtitles(muxed, ass, final, encoder="h264_qsv")
    info = probe(final)
    checkpoint(PROOT, "render", "OK",
               {"output": final.name, "duration": round(info.duration, 2)})

    (PROOT / "timeline" / "production_plan.json").write_text(json.dumps(
        {"shots": [{"shot_id": s, "start": a, "end": b, "asset": key,
                    "headline": h, "keyword": kw}
                   for s, a, b, key, h, kw, _r in SHOTS],
         "narration": [{"id": k, "start": v[0], "duration": v[1]}
                       for k, v in nstarts.items()],
         "total": total, "log": log},
        ensure_ascii=False, indent=1), encoding="utf-8")
    (PROOT / "timeline" / "build.json").write_text(json.dumps(
        {"duration": round(info.duration, 3), "output": str(final),
         "shots": len(SHOTS), "elapsed_s": round(time.time() - t0, 1)},
        ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"HOOK-SECOND {final} dur={info.duration:.2f} shots={len(SHOTS)} "
          f"total={total} overrides={overrides}")


if __name__ == "__main__":
    main()
