# -*- coding: utf-8 -*-
"""Proof: ONE Lucide SVG through STORY->REQUIREMENT->DISCOVERY->PLANNER->
DIRECTOR->OVERLAY->RENDER->PIXELS->QC->MANIFEST. Deterministic, 6 s smoke.
Usage: python scripts/prove_overlay_icon_v1.py
"""
import hashlib
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, ".")

from engine.core.media import probe
from engine.graphics import icons as _icons
from engine.montier_controller import checkpoint
from engine.rendering.ffmpeg import apply_vf, fit_filter, trim

PROOT = Path("projects/overlay_proof_v1")
WORK = PROOT / "renders" / "work"
W, H, FPS, DUR = 1080, 1920, 30, 6.0
INTENT = "visual icon representing attention / scrolling / focus"
KEYWORDS = ["attention", "focus", "scroll", "watch", "view", "reveal"]
BG_FILE = "8166027-uhd_2160_4096_25fps.mp4"  # tap-on-phone, attention motif
BG_OFF = 2.0


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(65536), b""):
            h.update(c)
    return h.hexdigest()


def gold_pixels(frame_png: Path, box: tuple) -> int:
    """Count gold (#FFD98A-ish) pixels inside box. Pillow+numpy-free loop."""
    from PIL import Image
    im = Image.open(frame_png).convert("RGB").crop(box)
    px = im.load()
    n = 0
    for yy in range(im.height):
        for xx in range(im.width):
            r, g, b = px[xx, yy]
            if r > 180 and g > 150 and b < 170 and r > b + 40:
                n += 1
    return n


def diff_count(a_png: Path, b_png: Path, box: tuple, thresh: int = 40) -> int:
    """Pixels in box whose |A-B| per-channel sum exceeds thresh.

    Overlay strokes change thousands of pixels; re-encode noise changes few.
    Same-timestamp final-vs-base comparison, so background motion cancels.
    """
    from PIL import Image
    a = Image.open(a_png).convert("RGB").crop(box)
    b = Image.open(b_png).convert("RGB").crop(box)
    pa, pb = a.load(), b.load()
    n = 0
    for yy in range(a.height):
        for xx in range(a.width):
            ra, ga, ba = pa[xx, yy]
            rb, gb, bb = pb[xx, yy]
            if abs(ra - rb) + abs(ga - gb) + abs(ba - bb) > thresh:
                n += 1
    return n


def main() -> None:
    t0 = time.time()
    ff_calls = [0]
    PROOT.mkdir(parents=True, exist_ok=True)
    (PROOT / "timeline").mkdir(parents=True, exist_ok=True)
    WORK.mkdir(parents=True, exist_ok=True)
    mh = Path(json.load(open(".cache/mh_index.json", encoding="utf-8"))["dir"])

    # --- REQUIREMENT (planner input) ---
    requirement = {"id": "req-icon-001", "kind": "ICON", "intent": INTENT,
                   "keywords": KEYWORDS}
    checkpoint(PROOT, "analyze", "OK", {"requirement": requirement})

    # --- ARSENAL DISCOVERY (existing intelligence: sidecar tags) ---
    cands = _icons.search_icons(INTENT, KEYWORDS, top_k=5)
    if not cands:
        raise _icons.IconCapabilityError("no icon matches intent", "discovery")
    log = {"candidates": [
        {"name": c["name"], "score": c["score"], "tags": c["tags"],
         "sha256": c["sha256"][:16]} for c in cands]}
    checkpoint(PROOT, "plan", "OK", log)

    # --- PLANNER DECISION (top tag-evidence candidate, never filename-only) ---
    best = cands[0]
    if not best["tags"] and not best["categories"]:
        raise _icons.IconCapabilityError(
            f"top candidate {best['name']} has no tag/category evidence",
            "discovery")
    planner = {"decision": "REQUEST_OVERLAY", "asset": best["name"],
               "why": (f"score {best['score']}: tag evidence {best['tags']} "
                       f"matches intent keywords; simplest attention metaphor"),
               "timing": {"start": 1.0, "duration": 4.0},
               "placement": {"x": 390, "y": 810, "size": 300},
               "style": {"color": "#FFD98A", "opacity": 1.0},
               "decided_by": "planner",
               "confidence": "HIGH (tag overlap + single-glyph geometry)"}
    checkpoint(PROOT, "storyboard", "OK", {"planner": planner["decision"]})

    # --- DIRECTOR DECISION (explicit approve + place) ---
    op = _icons.build_overlay_op(
        best, x=390, y=810, size=300, start=1.0, duration=4.0,
        color="#FFD98A", opacity=1.0,
        reason=("eye icon = attention metaphor for the hook story; "
                "center-stage proof placement (390,810,300px) so presence is "
                "unambiguous in pixel verification"),
        decided_by="planner", approved_by="director")
    op["planner_decision"] = planner
    checkpoint(PROOT, "assets", "OK", {"op_id": op["op_id"]})

    # --- RENDER ASSEMBLY: background (existing gateway ops) ---
    src_before = sha256(mh / BG_FILE)
    raw = WORK / "bg_raw.mp4"
    trim(mh / BG_FILE, BG_OFF, BG_OFF + DUR, raw, encoder="h264_qsv")
    ff_calls[0] += 1
    info = probe(mh / BG_FILE)
    base = WORK / "bg_base.mp4"
    apply_vf(raw, fit_filter(info.width, info.height, W, H, "cover", fps=FPS),
             base, encoder="h264_qsv")
    ff_calls[0] += 1
    raw.unlink(missing_ok=True)

    # --- OVERLAY GATEWAY: validate -> raster -> execute ---
    errors = _icons.validate_overlay_op(op, media_duration=DUR)
    if errors:
        raise _icons.IconCapabilityError("; ".join(errors), "contract")
    rast = _icons.rasterize_icon(best, WORK / "eye_300.png", size=300,
                                 color="#FFD98A")
    final = PROOT / "renders" / (
        "overlay_proof_%s.mp4" % time.strftime("%Y%m%d_%H%M%S"))
    res = _icons.execute_overlay(base, rast["png"], op, final,
                                 encoder="libx264")
    ff_calls[0] += 1
    out = probe(final)
    checkpoint(PROOT, "render", "OK",
               {"output": final.name, "duration": round(out.duration, 2)})

    # --- PIXEL VERIFICATION (frames, not manifest claims) ---
    # Primary: same-timestamp final-vs-base differentials (background motion
    # cancels; overlay strokes change thousands of pixels, encode noise few).
    # Supporting: gold-pixel counts (background skin tones also fire gold).
    box = (390, 810, 690, 1110)
    from engine.rendering.ffmpeg import run_ffmpeg
    frames, diffs = {}, {}
    for tag, t in (("before", 0.3), ("inside", 3.0), ("after", 5.5)):
        fp = WORK / f"px_{tag}.png"
        run_ffmpeg(["-loglevel", "error", "-ss", str(t), "-i", str(final),
                    "-frames:v", "1", "-y", str(fp)], op="px_extract")
        ff_calls[0] += 1
        bp = WORK / f"px_base_{tag}.png"
        run_ffmpeg(["-loglevel", "error", "-ss", str(t), "-i", str(base),
                    "-frames:v", "1", "-y", str(bp)], op="px_extract")
        ff_calls[0] += 1
        frames[tag] = {"t": t, "gold_px": gold_pixels(fp, box)}
        diffs[tag] = diff_count(fp, bp, box)
    raster_gold = gold_pixels(Path(rast["png"]), (0, 0, 300, 300))
    verdict = ("PASS" if diffs["inside"] >= 2000
               and diffs["before"] <= 1500
               and diffs["after"] <= 1500
               and frames["inside"]["gold_px"]
               >= 5 * max(frames["before"]["gold_px"], 1) else "FAIL")
    checkpoint(PROOT, "review", "OK",
               {"pixel_verdict": verdict, "frames": frames})

    # --- MANIFEST / PROVENANCE (9 questions answered) ---
    manifest = {
        "schema": "overlay-proof-1.0",
        "output": str(final), "output_sha256": sha256(final),
        "duration": round(out.duration, 3),
        "canvas": {"w": W, "h": H, "fps": FPS},
        "q1_asset": {**op["asset"]},
        "q2_why": op["reason"],
        "q3_planner": planner,
        "q4_director": {"approved_by": "director",
                        "placement_rationale": op["reason"]},
        "q5_renderer": {"op": "overlay_asset",
                        "filter": "format+colorchannelmixer+scale+overlay",
                        "encoder": "libx264",
                        "raster": rast},
        "q6_timing": op["timing"], "q7_placement": op["placement"],
        "q8_hashes": {"source_svg_sha256": best["sha256"],
                      "raster_png_sha256": rast["png_sha256"],
                      "background_source": BG_FILE,
                      "background_offset": BG_OFF},
        "q9_original_untouched": sha256(mh / BG_FILE) == src_before
        and _icons._sha256(best["source_path"]) == best["sha256"],
        "pixel_verification": {"box": list(box), "frames": frames,
                               "same_timestamp_diffs": diffs,
                               "raster_gold_px": raster_gold,
                               "verdict": verdict},
        "performance": {"elapsed_s": round(time.time() - t0, 1),
                        "ffmpeg_invocations": ff_calls[0],
                        "reencoded_unnecessarily": False,
                        "cache_reused": "mh_index (discovery); no segment "
                                        "cache exists (see audit R7)"},
        "requirement": requirement, "overlay_op": op,
    }
    (PROOT / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    (PROOT / "timeline" / "build.json").write_text(json.dumps(
        {"output": str(final), "verdict": verdict,
         "elapsed_s": round(time.time() - t0, 1)},
        ensure_ascii=False, indent=1), encoding="utf-8")
    checkpoint(PROOT, "final_report", "OK", {"verdict": verdict})
    print(f"OVERLAY-PROOF {final.name} verdict={verdict} "
          f"diff_in={diffs['inside']} diff_pre={diffs['before']} "
          f"diff_post={diffs['after']} "
          f"gold_in={frames['inside']['gold_px']} "
          f"elapsed={manifest['performance']['elapsed_s']}s")
    if verdict != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
