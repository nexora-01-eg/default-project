# -*- coding: utf-8 -*-
"""Graphics Layer 1.0 proof: ONE shot with icon + label + camera push.

planner propose -> director review -> camera -> compose -> pixels (x2 runs) ->
cache measurements (cold / identical / graphics-edit) -> manifest.
Usage: python scripts/prove_graphics_layer_v1.py
"""
import hashlib
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, ".")

from engine.core.media import probe
from engine.graphics import composition as _gc
from engine.graphics import icons as _icons
from engine.montier_controller import checkpoint
from engine.rendering.ffmpeg import apply_vf, fit_filter, run_ffmpeg, trim
from engine.tools.adapters.providers import FFmpegAdapter

PROOT = Path("projects/graphics_layer_v1")
WORK = PROOT / "renders" / "work"
CACHE = PROOT / "raster_cache"
W, H, FPS, DUR = 1080, 1920, 30, 6.0
BG_FILE = "8166027-uhd_2160_4096_25fps.mp4"
BG_OFF = 2.0


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(65536), b""):
            h.update(c)
    return h.hexdigest()


def frame(path: Path, t: float) -> Path:
    run_ffmpeg(["-loglevel", "error", "-ss", str(t), "-i", str(path),
                "-frames:v", "1", "-y", str(path)], op="px")
    return path


def diff_count(a: Path, b: Path, box: tuple, thresh: int = 40) -> int:
    from PIL import Image
    ia = Image.open(a).convert("RGB").crop(box)
    ib = Image.open(b).convert("RGB").crop(box)
    pa, pb = ia.load(), ib.load()
    return sum(1 for yy in range(ia.height) for xx in range(ia.width)
               if abs(pa[xx, yy][0] - pb[xx, yy][0])
               + abs(pa[xx, yy][1] - pb[xx, yy][1])
               + abs(pa[xx, yy][2] - pb[xx, yy][2]) > thresh)


def gold_count(p: Path, box: tuple) -> int:
    from PIL import Image
    im = Image.open(p).convert("RGB").crop(box)
    px = im.load()
    return sum(1 for yy in range(im.height) for xx in range(im.width)
               if (lambda r, g, b: r > 180 and g > 150 and b < 170
                   and r > b + 40)(*px[xx, yy]))


def build_base(tag: str) -> tuple[Path, int]:
    """Background + supported camera_push. Returns (path, ffmpeg_calls)."""
    mh = Path(json.load(open(".cache/mh_index.json", encoding="utf-8"))["dir"])
    calls = 0
    raw = WORK / f"base_{tag}_raw.mp4"
    trim(mh / BG_FILE, BG_OFF, BG_OFF + DUR, raw, encoder="h264_qsv")
    calls += 1
    info = probe(mh / BG_FILE)
    fit = WORK / f"base_{tag}_fit.mp4"
    apply_vf(raw, fit_filter(info.width, info.height, W, H, "cover", fps=FPS),
             fit, encoder="h264_qsv")
    calls += 1
    raw.unlink(missing_ok=True)
    pushed = WORK / f"base_{tag}_push.mp4"
    FFmpegAdapter().run({"op": "camera_push", "src": str(fit),
                         "dst": str(pushed), "duration": DUR,
                         "zoom_from": 1.0, "zoom_to": 1.08,
                         "encoder": "libx264"})
    calls += 1
    return pushed, calls


def planner_proposals(label_text: str) -> list[dict]:
    return _gc.propose_shot_graphics("sh_gfx_01", [
        {"kind": "icon", "intent": "visual metaphor for viewer attention",
         "keywords": ["attention", "focus", "scroll", "watch", "view",
                      "reveal"],
         "role": "visual metaphor",
         "placement": {"x": 240, "y": 900, "w": 260, "h": 260},
         "timing": {"start": 1.0, "duration": 4.0}},
        {"kind": "label", "text": label_text, "role": "context tag",
         "placement": {"x": 700, "y": 300},
         "timing": {"start": 0.5, "duration": 5.0}}])


def verify(final: Path, cam_base: Path, label_box: tuple) -> dict:
    icon_box = (240, 900, 500, 1160)
    rec = {}
    for tag, t in (("before", 0.3), ("inside", 3.0), ("after", 5.7)):
        fp = frame(WORK / f"{final.stem}_{tag}.png", 0) if False else None
        fp = WORK / f"{final.stem}_{tag}.png"
        run_ffmpeg(["-loglevel", "error", "-ss", str(t), "-i", str(final),
                    "-frames:v", "1", "-y", str(fp)], op="px")
        bp = WORK / f"base_{tag}.png"
        run_ffmpeg(["-loglevel", "error", "-ss", str(t), "-i", str(cam_base),
                    "-frames:v", "1", "-y", str(bp)], op="px")
        rec[tag] = {"t": t,
                    "icon_diff": diff_count(fp, bp, icon_box),
                    "label_diff": diff_count(fp, bp, label_box),
                    "label_gold": gold_count(fp, label_box)}
    return rec


def main() -> None:
    t0 = time.time()
    PROOT.mkdir(parents=True, exist_ok=True)
    (PROOT / "timeline").mkdir(parents=True, exist_ok=True)
    WORK.mkdir(parents=True, exist_ok=True)
    mh = Path(json.load(open(".cache/mh_index.json", encoding="utf-8"))["dir"])
    src_before = sha256(mh / BG_FILE)
    eye_before = sha256(_icons.LUCIDE_ROOT / "eye.svg")

    checkpoint(PROOT, "analyze", "OK",
               {"shot": "sh_gfx_01: hook beat, attention metaphor + tag"})
    proposals = planner_proposals("HOOK")
    checkpoint(PROOT, "plan", "OK",
               {"proposals": [(p["type"], p["reason"][:80])
                              for p in proposals]})
    review = _gc.review_shot_graphics(proposals)
    assert len(review["approved"]) == 2 and not review["rejected"], review
    checkpoint(PROOT, "storyboard", "OK",
               {"approved": [(p["type"], p["layer"]) for p in review["approved"]]})
    label_box = (lambda pl: (pl["x"], pl["y"], pl["x"] + pl["w"],
                             pl["y"] + pl["h"]))(
        [p for p in review["approved"] if p["type"] == "label"][0]["placement"])

    runs = {}
    for run, tag in (("cold", "HOOK"),):
        rb = time.time()
        cam_base, base_calls = build_base("r1")
        comp = _gc.compose_shot(cam_base, review["approved"],
                                WORK / "comp_r1.mp4", CACHE, encoder="libx264")
        final = PROOT / "renders" / (
            "graphics_layer_%s.mp4" % time.strftime("%Y%m%d_%H%M%S"))
        Path(WORK / "comp_r1.mp4").replace(final)
        rec = verify(final, cam_base, label_box)
        runs["run1_cold"] = {"output": str(final), "comp": comp,
                             "verify": rec,
                             "ffmpeg_calls": base_calls + comp["ffmpeg_calls"] + 6,
                             "wall_s": round(time.time() - rb, 1)}
    checkpoint(PROOT, "render", "OK", {"run1": runs["run1_cold"]["output"]})

    # determinism: identical second compose (raster cache must hit)
    rb = time.time()
    cam2, _ = build_base("r2")
    comp2 = _gc.compose_shot(cam2, review["approved"], WORK / "comp_r2.mp4",
                             CACHE, encoder="libx264")
    rec2 = verify(WORK / "comp_r2.mp4", cam2, label_box)
    runs["run2_identical"] = {"comp": comp2, "verify": rec2,
                              "wall_s": round(time.time() - rb, 1)}

    # graphics-edit: label text changes -> icon raster hit, label re-raster
    rb = time.time()
    review3 = _gc.review_shot_graphics(planner_proposals("FOCUS"))
    assert len(review3["approved"]) == 2
    cam3, _ = build_base("r3")
    comp3 = _gc.compose_shot(cam3, review3["approved"], WORK / "comp_r3.mp4",
                             CACHE, encoder="libx264")
    runs["run3_edit"] = {"comp": comp3, "wall_s": round(time.time() - rb, 1)}
    checkpoint(PROOT, "review", "OK", {"runs": list(runs)})

    v1, v2 = runs["run1_cold"]["verify"], runs["run2_identical"]["verify"]
    verdict = ("PASS"
               if v1["inside"]["icon_diff"] >= 2000
               and v1["inside"]["label_diff"] >= 1500
               and v1["inside"]["label_gold"] >= 200
               and v1["before"]["icon_diff"] <= 1500
               and v1["after"]["icon_diff"] <= 1500
               and v2["inside"]["icon_diff"] == v1["inside"]["icon_diff"]
               and v2["inside"]["label_diff"] == v1["inside"]["label_diff"]
               else "FAIL")
    manifest = {
        "schema": "graphics-layer-proof-1.0",
        "final": runs["run1_cold"]["output"],
        "shot": {"id": "sh_gfx_01", "duration": DUR, "canvas": [W, H, FPS],
                 "camera": {"op": "camera_push", "zoom": [1.0, 1.08],
                            "executor": "FFmpegAdapter"}},
        "planner": {"proposals": proposals},
        "director": {"review": review, "rule": review["rule"]},
        "layers": runs["run1_cold"]["comp"]["layers"],
        "pixel_verification": runs["run1_cold"]["verify"],
        "determinism": {"run2_verify": v2},
        "cache_measurements": {
            "run1_cold": {"cache_hits": runs["run1_cold"]["comp"]["cache_hits"],
                          "wall_s": runs["run1_cold"]["wall_s"],
                          "ffmpeg_calls": runs["run1_cold"]["ffmpeg_calls"]},
            "run2_identical": {
                "cache_hits": runs["run2_identical"]["comp"]["cache_hits"],
                "wall_s": runs["run2_identical"]["wall_s"]},
            "run3_graphics_edit": {
                "cache_hits": runs["run3_edit"]["comp"]["cache_hits"],
                "wall_s": runs["run3_edit"]["wall_s"]},
            "boundary": "raster cache skips chrome/Pillow only; video "
                        "segments re-encode every run (no segment cache)"},
        "provenance": {
            "background": {"file": BG_FILE, "offset": BG_OFF,
                           "sha_before": src_before,
                           "untouched": sha256(mh / BG_FILE) == src_before},
            "icon_eye_untouched": sha256(_icons.LUCIDE_ROOT / "eye.svg") == eye_before},
        "verdict": verdict,
        "elapsed_s": round(time.time() - t0, 1),
    }
    (PROOT / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    checkpoint(PROOT, "final_report", "OK", {"verdict": verdict})
    print(f"GRAPHICS-LAYER verdict={verdict} "
          f"icon_in={v1['inside']['icon_diff']} "
          f"label_in={v1['inside']['label_diff']} "
          f"label_gold={v1['inside']['label_gold']} "
          f"hits1={runs['run1_cold']['comp']['cache_hits']} "
          f"hits2={runs['run2_identical']['comp']['cache_hits']} "
          f"hits3={runs['run3_edit']['comp']['cache_hits']}")
    if verdict != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
