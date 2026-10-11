"""Procedural graphics kit (Phase J): deterministic reusable components.

Vector side (svgwrite): counters, bars, timelines, progress, comparison
cards, arrows, callouts, grids, network diagrams, UI panels, code panels,
data cards, process diagrams. Raster side (Pillow, Latin+numerals only —
Arabic stays in libass): stat cards, quote cards, lower thirds.
All deterministic: same contract -> byte-identical file.
"""
from __future__ import annotations

from pathlib import Path


def _doc(kind: str, w: int, h: int, bg: str):
    import svgwrite
    dwg = svgwrite.Drawing(size=(w, h))
    dwg.add(dwg.rect(insert=(0, 0), size=(w, h), fill=bg))
    return dwg


def counter(contract: dict, dst: str | Path) -> Path:
    d = _doc("counter", 1080, 1080, contract.get("bg", "#0B102E"))
    fg = contract.get("fg", "#FFD98A")
    d.add(d.text(str(contract.get("value", "0")),
                 insert=(540, 480), text_anchor="middle", font_size=220,
                 fill=fg, font_family="Arial"))
    d.add(d.text(str(contract.get("label", "")),
                 insert=(540, 620), text_anchor="middle", font_size=56,
                 fill="#FFFFFF", font_family="Arial"))
    dst_p = Path(dst)
    dst_p.parent.mkdir(parents=True, exist_ok=True)
    d.saveas(str(dst_p))
    return dst_p


def bars(contract: dict, dst: str | Path) -> Path:
    import svgwrite
    vals = [float(v) for v in contract.get("values", [50, 80])]
    labels = list(contract.get("labels", []))
    w, h = 1080, 700
    d = _doc("bars", w, h, contract.get("bg", "#0B102E"))
    mx, n = max(vals + [1.0]), len(vals)
    bw = (w - 160) / max(n, 1)
    for i, v in enumerate(vals):
        bh = (h - 220) * (v / mx)
        x = 80 + i * bw + 12
        d.add(d.rect(insert=(x, h - 140 - bh), size=(bw - 24, bh),
                     fill=contract.get("fg", "#FFD98A"), rx=10))
        if i < len(labels):
            d.add(d.text(str(labels[i]), insert=(x + (bw - 24) / 2, h - 90),
                         text_anchor="middle", font_size=36, fill="#FFFFFF",
                         font_family="Arial"))
    dst_p = Path(dst)
    dst_p.parent.mkdir(parents=True, exist_ok=True)
    d.saveas(str(dst_p))
    return dst_p


def progress(contract: dict, dst: str | Path) -> Path:
    p = max(0.0, min(1.0, float(contract.get("progress", 0.5))))
    w, h = 1080, 200
    d = _doc("progress", w, h, contract.get("bg", "#0B102E"))
    d.add(d.rect(insert=(90, 80), size=(w - 180, 40), rx=20,
                 fill="#2A3358"))
    d.add(d.rect(insert=(90, 80), size=((w - 180) * p, 40), rx=20,
                 fill=contract.get("fg", "#FFD98A")))
    dst_p = Path(dst)
    dst_p.parent.mkdir(parents=True, exist_ok=True)
    d.saveas(str(dst_p))
    return dst_p


def timeline_strip(contract: dict, dst: str | Path) -> Path:
    steps = list(contract.get("steps", ["A", "B", "C"]))
    w, h = 1080, 360
    d = _doc("timeline", w, h, contract.get("bg", "#0B102E"))
    n = len(steps)
    for i, s in enumerate(steps):
        x = 90 + i * ((w - 180) / max(n - 1, 1))
        d.add(d.circle(center=(x, 150), r=26,
                       fill=contract.get("fg", "#FFD98A")))
        d.add(d.text(str(s), insert=(x, 230), text_anchor="middle",
                     font_size=40, fill="#FFFFFF", font_family="Arial"))
        if i:
            x0 = 90 + (i - 1) * ((w - 180) / max(n - 1, 1))
            d.add(d.line(start=(x0 + 26, 150), end=(x - 26, 150),
                         stroke="#5A6486", stroke_width=6))
    dst_p = Path(dst)
    dst_p.parent.mkdir(parents=True, exist_ok=True)
    d.saveas(str(dst_p))
    return dst_p


def network(contract: dict, dst: str | Path) -> Path:
    import math
    n = max(3, int(contract.get("nodes", 6)))
    w, h = 1080, 1080
    d = _doc("network", w, h, contract.get("bg", "#0B102E"))
    pts = [(540 + 320 * math.cos(2 * math.pi * i / n),
            540 + 320 * math.sin(2 * math.pi * i / n)) for i in range(n)]
    for i in range(n):
        d.add(d.line(start=pts[i], end=pts[(i + 1) % n],
                     stroke="#5A6486", stroke_width=4))
        d.add(d.line(start=(540, 540), end=pts[i],
                     stroke=contract.get("fg", "#FFD98A"), stroke_width=3))
    d.add(d.circle(center=(540, 540), r=40,
                   fill=contract.get("fg", "#FFD98A")))
    for x, y in pts:
        d.add(d.circle(center=(x, y), r=22, fill="#FFFFFF"))
    dst_p = Path(dst)
    dst_p.parent.mkdir(parents=True, exist_ok=True)
    d.saveas(str(dst_p))
    return dst_p


def raster_card(title: str, body: str, dst: str | Path, *,
                accent: str = "#FFD98A") -> Path:
    """Pillow fullscreen card (Latin + numerals only). Deterministic."""
    from PIL import Image, ImageDraw, ImageFont
    img = Image.new("RGB", (1080, 1920), (11, 16, 46))
    dr = ImageDraw.Draw(img)
    try:
        big = ImageFont.load_default(size=160)
        mid = ImageFont.load_default(size=64)
    except TypeError:
        big = ImageFont.load_default()
        mid = ImageFont.load_default()
    dr.text((540, 830), title, fill=tuple(
        int(accent.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)),
        font=big, anchor="mm")
    dr.text((540, 1010), body, fill=(255, 255, 255), font=mid,
            anchor="mm")
    dr.rectangle([240, 1120, 840, 1140], fill=tuple(
        int(accent.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)))
    dst_p = Path(dst)
    dst_p.parent.mkdir(parents=True, exist_ok=True)
    img.save(dst_p)
    return dst_p
