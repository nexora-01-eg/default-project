"""Narrated tech production v1: voice-led assembly with narration+music mix.

Timeline (82.5 s total, narration-driven):
  L1 "زمان كان فريق كامل." @ 1.5 (43.138 s) / pause 0.5 / L2 "هتستخدمه إزاي؟" (34.199 s)
Video: 3 cards + 20 clip segments (18 shots, 3 static punch reframes).
Audio: narration track + ducked music bed (Aitech, CC-BY) mixed, muxed, captions burned.
Gateway ops only. No source asset modified.
Usage: python scripts/narr_assemble_v1.py <project_dir>
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
    make_silence,
    mix_audio,
    mux,
    trim,
)

ARS = Path("F:/Arsenal/MH - محتوى بصري/02-فيديو")
MUS = Path("F:/Arsenal/04_Music/Incompetech/Aitech.mp3")
NARR = Path("C:/Users/NOUR SOFT/Documents/Default Project/tools/tts/piper/tests/narr")
CARD_COLOR = "0x0B102E"
W, H, FPS = 1080, 1920, 30
L1_DUR, L2_DUR = 43.138, 34.199
L1_AT, GAP, TOTAL = 1.5, 0.5, 82.5
L2_AT = L1_AT + L1_DUR + GAP  # 45.138
TAIL = round(TOTAL - (L2_AT + L2_DUR), 3)

PUNCH = ",crop=940:1671,scale=1080:1920"

# (kind, label, file, span, vf_extra)
SHOTS = [
    ("card", "title-card", None, 1.5, ""),
    ("clip", "S1-neon", "107916-679600385_medium.mp4", (0.0, 1.7), ""),
    ("clip", "S1-code", "15029082_3840_2160_25fps.mp4", (0.0, 1.7), ""),
    ("clip", "S1-neon2", "107916-679600385_medium.mp4", (2.0, 3.7), ""),
    ("clip", "S2-keys", "251763_medium.mp4", (2.0, 6.4), ""),
    ("clip", "S2-macA", "92480-637690589_medium.mp4", (0.0, 2.2), ""),
    ("clip", "S2-macB-punch", "92480-637690589_medium.mp4", (2.2, 4.5), PUNCH),
    ("clip", "S2-startup", "6963374-hd_1080_1920_30fps.mp4", (2.0, 6.5), ""),
    ("clip", "S3-code", "15029082_3840_2160_25fps.mp4", (12.0, 16.0), ""),
    ("clip", "S3-eq", "316712_medium.mp4", (0.0, 4.0), ""),
    ("clip", "S4-code", "15029082_3840_2160_25fps.mp4", (21.0, 25.0), ""),
    ("clip", "S4-mac", "92480-637690589_medium.mp4", (8.0, 12.0), ""),
    ("clip", "S4-keys", "251763_medium.mp4", (6.0, 10.0), ""),
    ("clip", "S4-code2", "15029082_3840_2160_25fps.mp4", (24.0, 29.1), ""),
    ("clip", "S5-hsA", "358512_medium.mp4", (0.0, 3.9), ""),
    ("clip", "S5-hsB-punch", "358512_medium.mp4", (3.9, 7.9), PUNCH),
    ("card", "S5-keycard", None, 2.0, ""),
    ("clip", "S6-dubai", "296958_medium.mp4", (0.0, 6.0), ""),
    ("clip", "S6-neon-callback", "107916-679600385_medium.mp4", (3.0, 9.0), ""),
    ("clip", "S6-planning", "8373729-hd_1080_1920_25fps.mp4", (0.0, 6.0), ""),
    ("clip", "S6-dubA", "296958_medium.mp4", (12.0, 15.0), ""),
    ("clip", "S6-dubB-punch", "296958_medium.mp4", (15.0, 18.3), PUNCH),
    ("card", "end-card", None, 3.2, ""),
]

MUSIC_STATES = [
    (0.0, L1_AT, 0.0),
    (L1_AT, L1_AT + L1_DUR, -6.0),
    (L1_AT + L1_DUR, L2_AT, -2.0),
    (L2_AT, L2_AT + L2_DUR, -6.0),
    (L2_AT + L2_DUR, TOTAL, -2.0),
]

CAPTIONS = [  # (start, end, style, text)
    (L1_AT, (L1_AT * 2 + L1_DUR) / 2, "Body", "زمان كان"),
    ((L1_AT * 2 + L1_DUR) / 2, L1_AT + L1_DUR, "Body", "فريق كامل."),
    (L2_AT, (L2_AT * 2 + L2_DUR) / 2, "Body", "إنت"),
    ((L2_AT * 2 + L2_DUR) / 2, L2_AT + L2_DUR, "Body", "هتستخدمه إزاي؟"),
]
KEYWORDS = [  # (start, end, text) — brief emphasis only
    (2.0, 6.0, "فريق كامل؟"),
    (7.0, 11.0, "المعادلة"),
    (20.0, 24.0, "السرعة"),
    (32.0, 36.0, "تحليل"),
    (46.0, 52.0, "الإنسان"),
    (68.0, 73.0, "قرارك"),
]


def ass_time(s):
    h = int(s // 3600)
    m = int((s % 3600) // 60)
    return f"{h}:{m:02d}:{s % 60:05.2f}"


def build_ass(path):
    head = ("[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\n"
            "PlayResY: 1920\nScaledBorderAndShadow: yes\n\n"
            "[V4+ Styles]\n"
            "Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, "
            "BackColour, Bold, Alignment, MarginV\n"
            "Style: Title,Arial,104,&H00FFD98A,&H80000000,&H80000000,1,5,120\n"
            "Style: Body,Arial,54,&H00FFFFFF,&H90000000,&H90000000,1,2,190\n"
            "Style: Key,Arial,70,&H00FFD98A,&H90000000,&H90000000,1,8,230\n"
            "Style: End,Arial,84,&H00FFD98A,&H80000000,&H80000000,1,5,120\n\n"
            "[Events]\n"
            "Format: Layer, Start, End, Style, Text\n")
    evs = [_motion.dialogue(
        0.0, 1.5, "Title",
        f"{_motion.rise(540, 760)}كيف الذكاء الاصطناعي\\Nبيغيّر صناعة الفيديو؟")]
    for i, (s, e, txt) in enumerate(
            [(c[0], c[1], c[3]) for c in CAPTIONS]):
        evs.append(_motion.dialogue(
            s, e, "Body", txt,
            _motion.rise(540, 1560) if i % 2 == 0 else _motion.fade()))
    for k, (s, e, txt) in enumerate(KEYWORDS):
        evs.append(_motion.dialogue(
            s, e, "Key", txt,
            _motion.slide_in(540, 300, "left" if k % 2 == 0 else "right")))
    evs.append(_motion.dialogue(
        TOTAL - 3.2, TOTAL, "End", "القرار…\\Nقرارك إنت",
        _motion.fade(400)))
    Path(path).write_text(head + "\n".join(evs) + "\n", encoding="utf-8")
    return len(evs)


def main():
    proot = Path(sys.argv[1])
    t0 = time.time()
    work = proot / "renders" / "work"
    work.mkdir(parents=True, exist_ok=True)
    (proot / "renders").mkdir(parents=True, exist_ok=True)
    (proot / "timeline").mkdir(parents=True, exist_ok=True)
    parts, cursor = [], 0.0
    for i, (kind, label, fn, span, extra) in enumerate(SHOTS):
        if kind == "card":
            p = work / f"v{i:02d}.mp4"
            color_clip(CARD_COLOR, W, H, span, p, fps=FPS)
        else:
            s, e = span
            info = probe(ARS / fn)
            vf = fit_filter(info.width, info.height, W, H, "cover", fps=FPS)
            if extra:
                vf += extra
            tmp = work / f"raw{i:02d}.mp4"
            trim(ARS / fn, s, e, tmp, encoder="h264_qsv")
            p = work / f"v{i:02d}.mp4"
            apply_vf(tmp, vf, p, encoder="h264_qsv")
            tmp.unlink(missing_ok=True)
        dur = probe(p).duration
        parts.append(p)
        cursor = round(cursor + dur, 3)
    print(f"parts={len(parts)} assembled={cursor:.2f}s target={TOTAL}")
    joined = work / "joined.mp4"
    concat(parts, joined, reencode=True, encoder="libx264")
    # narration track @44.1k stereo
    lead = make_silence(L1_AT, work / "lead.wav",
                        sample_rate=44100, channels=2)
    n1 = extract_audio(NARR / "L1_06.wav", work / "n1.wav",
                       sample_rate=44100, channels=2)
    s05 = make_silence(GAP, work / "s05.wav", sample_rate=44100, channels=2)
    n2 = extract_audio(NARR / "L2_06.wav", work / "n2.wav",
                       sample_rate=44100, channels=2)
    tail = make_silence(TAIL, work / "tail.wav",
                        sample_rate=44100, channels=2)
    narr = concat([lead, n1, s05, n2, tail], work / "narr.wav", reencode=False)
    assert abs(probe(narr).duration - TOTAL) < 0.1, probe(narr).duration
    # ducked music bed
    mus = extract_audio(MUS, work / "music0.wav", start=2.0,
                        duration=TOTAL, sample_rate=44100, channels=2)
    faded = work / "music_fade.m4a"
    fade_audio(mus, faded, fade_in=2.0, fade_out=3.0)
    slices = []
    for k, (s, e, g) in enumerate(MUSIC_STATES):
        sl = work / f"au{k:02d}.m4a"
        extract_audio(faded, sl, start=s, duration=round(e - s, 3))
        if g:
            gl = work / f"aug{k:02d}.m4a"
            gain_audio(sl, gl, gain_db=g)
            sl.unlink(missing_ok=True)
            sl = gl
        slices.append(sl)
    bed = work / "music_states.m4a"
    concat(slices, bed, reencode=False)
    bedw = extract_audio(bed, work / "bed.wav",
                         sample_rate=44100, channels=2)
    mixed = mix_audio([narr, bedw], work / "mixed.m4a")
    muxed = work / "muxed.mp4"
    mux(joined, mixed, muxed)
    ass = proot / "timeline" / "narr.ass"
    nevents = build_ass(ass)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    final = proot / "renders" / f"narrated_tech_{stamp}.mp4"
    burn_subtitles(muxed, ass, final, encoder="h264_qsv")
    info = probe(final)
    print(f"FINAL {final} dur={info.duration:.2f} "
          f"{info.width}x{info.height} v={info.video_codec} a={info.audio_codec}")
    (proot / "timeline" / "build.json").write_text(json.dumps(
        {"segments": len(parts), "duration": round(info.duration, 3),
         "output": str(final), "ass_events": nevents,
         "elapsed_s": round(time.time() - t0, 1)},
        ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
