"""From-scratch assembly: timeline.json + script.json -> finished video.

Uses gateway ops only (trim/apply_vf/concat/color_clip/fade_audio/mux/
burn_subtitles) + ffprobe QC. Deterministic: fixed spans, fixed filters,
fixed encoder choices (documented). No downloads, no network.

Usage: python scripts/assemble_fs.py <project_dir>
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, ".")
from engine.core.media import probe
from engine.creative import motion as _motion
from engine.rendering.ffmpeg import (
    apply_vf,
    burn_subtitles,
    color_clip,
    concat,
    extract_audio,
    fade_audio,
    fit_filter,
    gain_audio,
    mux,
    trim,
)

CARD_COLOR = "0x0B102E"
W, H, FPS = 1080, 1920, 30


def split_arabic(text, parts):
    words = text.split(" ")
    chunks, cur = [], []
    target = max(1, len(words) // parts)
    for w in words:
        cur.append(w)
        if len(cur) >= target and len(chunks) < parts - 1:
            chunks.append(" ".join(cur))
            cur = []
    if cur:
        chunks.append(" ".join(cur))
    return chunks


def split_headlines(text, max_words=8):
    """TEXT_DRIVEN hierarchy: short headline cues, never the full script."""
    words = text.split(" ")
    chunks, cur = [], []
    for w in words:
        cur.append(w)
        if len(cur) >= max_words:
            chunks.append(" ".join(cur))
            cur = []
    if cur:
        chunks.append(" ".join(cur))
    return chunks or ["…"]


def ass_time(s):
    h = int(s // 3600)
    m = int((s % 3600) // 60)
    sec = s % 60
    return f"{h}:{m:02d}:{sec:05.2f}"


def build_ass(script, path):
    title = script.get("title", {"l1": script_title_l1, "l2": script_title_l2,
                                 "span": [0.0, 2.5]})
    endc = script.get("endcard", {"l1": end_l1, "l2": end_l2,
                                  "span": [END_AT, TOTAL]})
    head = ("[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\n"
            "PlayResY: 1920\nScaledBorderAndShadow: yes\n\n"
            "[V4+ Styles]\n"
            "Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, "
            "BackColour, Bold, Alignment, MarginV\n"
            "Style: Title,Arial,104,&H00FFD98A,&H80000000,&H80000000,1,5,120\n"
            "Style: Body,Arial,50,&H00FFFFFF,&H90000000,&H90000000,1,2,190\n"
            "Style: Key,Arial,70,&H00FFD98A,&H90000000,&H90000000,1,8,230\n"
            "Style: End,Arial,84,&H00FFD98A,&H80000000,&H80000000,1,5,120\n\n"
            "[Events]\n"
            "Format: Layer, Start, End, Style, Text\n")
    evs = []
    evs.append(f"Dialogue: 0,{ass_time(title['span'][0])},{ass_time(title['span'][1])},Title,"
               f"{_motion.rise(540, 760)}{title['l1']}\\N{title['l2']}")
    for si, sc in enumerate(script["scenes"]):
        s, e = sc["span"]
        # TEXT_DRIVEN hierarchy: headlines only (never the full script).
        heads = split_headlines(sc.get("headline", sc["text"]))
        n = len(heads)
        for i, chunk in enumerate(heads):
            cs = s + (e - s) * i / max(n, 1)
            ce = s + (e - s) * (i + 1) / max(n, 1)
            evs.append(_motion.dialogue(
                cs, ce, "Body", chunk,
                _motion.rise(540, 1560) if i % 2 == 0
                else _motion.fade()))
        kw_end = min(e, s + (e - s) * 0.6)
        side = "left" if si % 2 == 0 else "right"
        evs.append(_motion.dialogue(
            s + 0.3, kw_end, "Key", sc["keyword"],
            _motion.slide_in(540, 300, side)))
    evs.append(_motion.dialogue(
        endc["span"][0], endc["span"][1], "End",
        f"{endc['l1']}\\N{endc['l2']}", _motion.fade(400)))
    Path(path).write_text(head + "\n".join(evs) + "\n", encoding="utf-8")


script_title_l1 = "كيف الذكاء الاصطناعي"
script_title_l2 = "بيغيّر صناعة الفيديو؟"
end_l1 = "الإبداع + الذكاء الاصطناعي"
end_l2 = "هي دي المعادلة"
END_AT = 72.3
TOTAL = 76.0


def main():
    proot = Path(sys.argv[1])
    t0 = time.time()
    tl = json.loads((proot / "timeline" / "timeline.json").read_text(encoding="utf-8"))
    script = json.loads((proot / "timeline" / "script.json").read_text(encoding="utf-8"))
    work = proot / "renders" / "work"
    work.mkdir(parents=True, exist_ok=True)
    (proot / "renders").mkdir(parents=True, exist_ok=True)
    parts = []
    cursor = 0.0
    for i, seg in enumerate(tl["segments"]):
        if seg["kind"] == "card":
            ln = seg.get("len") or seg.get("dur") or 2.5
            p = work / f"v{i:02d}.mp4"
            color_clip(CARD_COLOR, W, H, ln, p, fps=FPS)
        else:
            s, e = seg["span"]
            ln = round(e - s, 3)
            info = probe(seg["file"])
            vf = fit_filter(info.width, info.height, W, H, "cover", fps=FPS)
            tmp = work / f"raw{i:02d}.mp4"
            trim(seg["file"], s, e, tmp, encoder="h264_qsv")
            p = work / f"v{i:02d}.mp4"
            apply_vf(tmp, vf, p, encoder="h264_qsv")
            tmp.unlink(missing_ok=True)
        dur = probe(p).duration
        parts.append(p)
        cursor = round(cursor + dur, 3)
    print(f"parts={len(parts)} assembled={cursor:.2f}s target={tl['total']}")
    joined = work / "joined.mp4"
    # libx264 assembly concat: measured exact (QSV concat re-encode drops
    # frames on multi-part timelines); burn re-encodes to the final codec.
    concat(parts, joined, reencode=True, encoder="libx264")
    au = tl["audio"]
    mus = work / "music.m4a"
    au_len = round(au["span"][1] - au["span"][0], 3)
    extract_audio(au["file"], mus, start=au["span"][0], duration=au_len)
    faded = work / "music_fade.m4a"
    fade_audio(mus, faded, fade_in=au["fade_in"], fade_out=au["fade_out"])
    # audio states: per-scene gains (hook/build/explanation/peak/resolve);
    # absent in legacy timelines -> single bed unchanged.
    bed = faded
    states = tl.get("audio_states", [])
    if states:
        slices = []
        for k, st in enumerate(states):
            sl = work / f"au{k:02d}.m4a"
            extract_audio(bed, sl, start=st["start"],
                          duration=round(st["end"] - st["start"], 3))
            if st.get("gain_db", 0.0):
                gl = work / f"aug{k:02d}.m4a"
                gain_audio(sl, gl, gain_db=st["gain_db"])
                sl.unlink(missing_ok=True)
                sl = gl
            slices.append(sl)
        bed = work / "music_states.m4a"
        concat(slices, bed, reencode=False)
    muxed = work / "muxed.mp4"
    mux(joined, bed, muxed)
    ass = proot / "timeline" / "fs.ass"
    build_ass(script, ass)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    final = proot / "renders" / f"from_scratch_ai_video_{stamp}.mp4"
    burn_subtitles(muxed, ass, final, encoder="h264_qsv")
    info = probe(final)
    print(f"FINAL {final} dur={info.duration:.2f} "
          f"{info.width}x{info.height} v={info.video_codec} a={info.audio_codec}")
    (proot / "timeline" / "build.json").write_text(json.dumps(
        {"segments": len(parts), "duration": round(info.duration, 3),
         "output": str(final), "elapsed_s": round(time.time() - t0, 1)},
        ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
