"""Stack smoke test (~45 s): exercises newly integrated providers end to end.

 narration (validated Piper L2) + word timing (faster-whisper) +
 kinetic ASS (karaoke + EN emphasis) + B-roll + camera push (zoompan) +
 Pillow stat card + SVG sidecar + fade transitions + music duck +
 sting SFX + loudness normalize + color treatment + OTIO export +
 contract validation + QC + creative review.
Gateway ops + adapters only. Deterministic.
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, ".")
from engine.core.media import probe
from engine.rendering.ffmpeg import (
    apply_vf, burn_subtitles, color_clip, concat, extract_audio, fade_audio,
    fit_filter, gain_audio, make_silence, mix_audio, mux, trim)
from engine.tools import contract_schema, kinetic_captions as KC
from engine.tools import motion_system, visual_plan, visual_review
from engine.tools.adapters.providers import get
from engine.tools.router import resolve

ARS = Path("F:/Arsenal/MH - محتوى بصري/02-فيديو")
MUS = Path("F:/Arsenal/04_Music/Incompetech/Aitech.mp3")
STING = Path("F:/Arsenal/04_Music/Incompetech/MJS Stings.mp3")
NARR_SRC = Path("C:/Users/NOUR SOFT/Documents/Default Project/tools/tts/"
                "piper/tests/narr/L2_06.wav")
W, H, FPS = 1080, 1920, 30


def stat_card_png(dst):
    from PIL import Image, ImageDraw, ImageFont
    img = Image.new("RGB", (W, H), (11, 16, 46))
    dr = ImageDraw.Draw(img)
    try:
        big = ImageFont.load_default(size=300)
        mid = ImageFont.load_default(size=72)
    except TypeError:
        big = ImageFont.load_default()
        mid = ImageFont.load_default()
    dr.text((W // 2, H // 2 - 120), "87%", fill=(255, 217, 138),
            font=big, anchor="mm")
    dr.text((W // 2, H // 2 + 160), "FASTER CUTS", fill=(255, 255, 255),
            font=mid, anchor="mm")
    dr.rectangle([140, H // 2 + 260, W - 140, H // 2 + 300],
                 fill=(255, 217, 138))
    img.save(dst)
    return dst


def main():
    proot = Path(sys.argv[1] if len(sys.argv) > 1
                 else "projects/stack_smoke_20260924")
    t0 = time.time()
    work = proot / "renders" / "work"
    (proot / "timeline").mkdir(parents=True, exist_ok=True)
    work.mkdir(parents=True, exist_ok=True)
    log = []

    def routed(capability, params, fn):
        r = resolve(capability, params)
        log.append({"capability": capability,
                    "selected": (r["selected"] or {}).get("provider"),
                    "decision": r["decision"]})
        assert r["selected"] is not None, r
        return fn()

    # 1. narration words (STT word timing)
    narr = extract_audio(NARR_SRC, work / "narr.wav", sample_rate=44100,
                         channels=2)
    words = routed("WORD_TIMING", {"src": str(narr)}, lambda: get(
        "faster-whisper").run({"src": str(narr),
                               "out": str(work / "words.json"),
                               "model": "tiny"}))
    nwords = words["words"]
    # 2. kinetic ASS from TRUE word timings (built after picture lock)
    ass = proot / "timeline" / "smoke.ass"
    rep = None
    # 3. beats -> snap one cut to nearest beat (real beat-sync use)
    mus = extract_audio(MUS, work / "mus.wav", start=2.0, duration=46.0,
                        sample_rate=44100, channels=2)
    beats = routed("BEAT_DETECTION", {"src": str(mus)},
                   lambda: get("librosa").run(
                       {"src": str(mus), "out": str(work / "beats.json")}))
    cut = min(json.loads(Path(work / "beats.json").read_text(
        encoding="utf-8"))["beats_s"], key=lambda b: abs(b - 20.0))
    # 4. video parts (push->stat boundary snapped to nearest music beat)
    info = probe(ARS / "107916-679600385_medium.mp4")
    vf = fit_filter(info.width, info.height, W, H, "cover", fps=FPS)
    seg = []
    card = work / "v00.mp4"
    color_clip("0x0B102E", W, H, 2.0, card, fps=FPS)
    seg.append(apply_vf(card, "fade=t=in:st=0:d=0.5", work / "f00.mp4",
                        encoder="h264_qsv"))
    for i, (fn, s, e) in enumerate(
            [("107916-679600385_medium.mp4", 0.0, 5.0),
             ("15029082_3840_2160_25fps.mp4", 12.0, 17.0)]):
        raw = work / f"raw{i}.mp4"
        trim(ARS / fn, s, e, raw, encoder="h264_qsv")
        seg.append(apply_vf(raw, vf, work / f"v{i + 1:02d}.mp4",
                            encoder="h264_qsv"))
        Path(raw).unlink(missing_ok=True)
    push_len = round(cut - 12.0, 2)
    assert 4.0 <= push_len <= 24.0, f"beat-snapped push {push_len} out of range"
    draw = work / "draw.mp4"
    trim(ARS / "296958_medium.mp4", 0.0, push_len, draw, encoder="h264_qsv")
    push = routed("CAMERA_PUSH", {"src": str(draw)}, lambda: get(
        "ffmpeg").run({"op": "camera_push", "src": str(draw),
                       "dst": str(work / "push.mp4"), "zoom_from": 1.0,
                       "zoom_to": 1.12, "encoder": "libx264"}))["path"]
    seg.append(push)
    # stat card (Pillow) + SVG sidecar (vector artifact)
    stat_card_png(work / "stat.png")
    spng = apply_vf(work / "stat.png", "loop=loop=150:size=1,fps=30,"
                    "trim=duration=5,setpts=N/FRAME_RATE/TB",
                    work / "vstat.mp4", encoder="h264_qsv")
    seg.append(spng)
    svg = get("svgwrite").run({"kind": "stat_card", "title": "87%",
                               "body": "faster cuts",
                               "dst": str(proot / "timeline" / "stat.svg")})
    endc = work / "vend.mp4"
    color_clip("0x0B102E", W, H, 4.0, endc, fps=FPS)
    seg.append(apply_vf(endc, "fade=t=out:st=3.0:d=1.0", work / "fend.mp4",
                        encoder="h264_qsv"))
    joined = work / "joined.mp4"
    concat(seg, joined, reencode=True, encoder="libx264")
    total = round(probe(joined).duration, 2)
    assert 36.0 <= total <= 46.0, f"smoke total {total} out of range"
    # 5. audio: ducked bed + sting + loudness, trimmed to picture
    faded = work / "mus_fade.m4a"
    fade_audio(mus, faded, fade_in=1.0, fade_out=2.0)
    bed = work / "bed_duck.m4a"
    gain_audio(faded, bed, gain_db=-6.0)
    sting = extract_audio(STING, work / "sting0.m4a", start=0.0, duration=1.2)
    sting_q = work / "sting.m4a"
    gain_audio(sting, sting_q, gain_db=-12.0)
    mixed = mix_audio([narr, bed, sting_q], work / "mixed.m4a")
    mixed_t = extract_audio(mixed, work / "mixed_t.wav", start=0.0,
                            duration=total, sample_rate=44100, channels=2)
    loud = routed("LOUDNESS_NORMALIZATION", {"target": -16.0}, lambda: get(
        "pyloudnorm").run({"src": str(mixed_t),
                           "dst": str(work / "loud.wav"),
                           "target_lufs": -16.0}))["path"]
    muxed = work / "muxed.mp4"
    mux(joined, loud, muxed)
    rep = KC.build_ass(work / "words.json", ass,
                       keywords=[(1.0, 4.0, "قرارك")],
                       title=("STACK SMOKE", "word-timed kinetic", 0.0, 2.0),
                       endcard=("DONE", "stack verified",
                                round(total - 4.0, 2), total))
    final = proot / "renders" / (
        "stack_smoke_%s.mp4" % time.strftime("%Y%m%d_%H%M%S"))
    burn_subtitles(muxed, ass, final, encoder="h264_qsv")
    info = probe(final)
    # 6. OTIO export + contract validation
    otio = get("opentimelineio").run(
        {"op": "export",
         "segments": [{"kind": "clip", "label": f"s{i}", "len": 5.0}
                       for i in range(5)],
         "dst": str(proot / "timeline" / "smoke.otio"), "fps": 30})
    contract = {"project": proot.name, "canvas": {"w": W, "h": H, "fps": FPS},
                "narration": {"segments": [{"id": "n1", "text": "smoke",
                                            "start": 0.0}]},
                "shots": [{"shot_id": "sh_001", "start": 0.0, "end": 5.0}]}
    cval = contract_schema.validate_contract(contract)
    # 7. reviews
    tl = {"segments": [{"kind": "clip", "span": [0, 5],
                        "label": "s", "motion": "push"}],
          "total": total}
    vr = visual_review.review_all(tl, rep["events"], ["a.mp4"])
    (proot / "timeline" / "build.json").write_text(json.dumps(
        {"duration": round(info.duration, 3), "output": str(final),
         "words": nwords, "ass_events": rep["events"], "beats": beats,
         "otio_clips": otio["clips"], "svg": svg["path"],
         "contract_valid": cval["valid"], "visual_review": vr,
         "routing": log, "elapsed_s": round(time.time() - t0, 1)},
        ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"SMOKE {final} dur={info.duration:.2f} words={nwords} "
          f"events={rep['events']} contract={cval['valid']} review={vr}",
          flush=True)


if __name__ == "__main__":
    main()
