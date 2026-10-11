# -*- coding: utf-8 -*-
"""Repair round 1 for bench_director_v1: hook montage + diversity re-pick.

Findings repaired: (1) R2 hook FAIL — 7.2 s opening shot -> 3 quick cuts
(same total span, narration sync preserved); (2) repetitive selection —
same file 6x per scene -> distinct files, no adjacent repeats.
Total duration unchanged (78.89 s): same narration, music, captions.
Usage: python scripts/bench_repair_v1.py <project_dir>
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, ".")
from engine.core.media import probe
from engine.rendering.ffmpeg import (
    apply_vf, burn_subtitles, color_clip, concat, fit_filter, mux, trim)

ARS = Path("F:/Arsenal/MH - محتوى بصري/02-فيديو")
NEON = "107916-679600385_medium.mp4"
CODE = "15029082_3840_2160_25fps.mp4"
KEYS = "251763_medium.mp4"
MAC = "92480-637690589_medium.mp4"
STARTUP = "6963374-hd_1080_1920_30fps.mp4"
HS = "358512_medium.mp4"
DUBAI = "296958_medium.mp4"
PLAN = "8373729-hd_1080_1920_25fps.mp4"
CARD = "0x0B102E"
W, H, FPS = 1080, 1920, 30

# (kind, file, src_span_or_len) — total must equal 78.89
SEGS = [
    ("card", None, 1.5),
    ("clip", NEON, (0.0, 2.4)), ("clip", CODE, (0.0, 2.4)),
    ("clip", KEYS, (2.0, 4.4)),
    ("clip", MAC, (0.0, 7.2)), ("clip", STARTUP, (2.0, 6.0)),
    ("clip", "316712_medium.mp4", (0.0, 3.2)),
    ("clip", HS, (0.0, 7.2)), ("clip", DUBAI, (0.0, 7.2)),
    ("clip", PLAN, (0.0, 7.24)),
    ("clip", DUBAI, (7.0, 12.02)), ("clip", CODE, (12.0, 17.04)),
    ("clip", HS, (0.5, 5.54)), ("clip", STARTUP, (4.0, 9.02)),
    ("clip", MAC, (6.0, 11.04)), ("clip", NEON, (4.0, 9.0)),
    ("card", None, 3.99),
]


def main():
    proot = Path(sys.argv[1])
    t0 = time.time()
    work = proot / "renders" / "work"
    parts = []
    for i, s in enumerate(SEGS):
        if s[0] == "card":
            p = work / f"r{i:02d}.mp4"
            color_clip(CARD, W, H, s[2], p, fps=FPS)
        else:
            _, fn, (a, b) = s
            info = probe(ARS / fn)
            assert b <= info.duration + 0.01, (fn, a, b, info.duration)
            tmp = work / f"rraw{i:02d}.mp4"
            trim(ARS / fn, a, b, tmp, encoder="h264_qsv")
            p = work / f"r{i:02d}.mp4"
            apply_vf(tmp, fit_filter(info.width, info.height, W, H,
                                     "cover", fps=FPS), p, encoder="h264_qsv")
            tmp.unlink(missing_ok=True)
        parts.append(p)
    joined = work / "joined_r1.mp4"
    concat(parts, joined, reencode=True, encoder="libx264")
    total = round(probe(joined).duration, 2)
    print(f"repaired video {total}s (target 78.89)")
    (proot / "timeline" / "repair1.json").write_text(json.dumps(
        {"segments": len(parts), "duration": total,
         "elapsed_s": round(time.time() - t0, 1)}, indent=1),
        encoding="utf-8")


if __name__ == "__main__":
    main()
