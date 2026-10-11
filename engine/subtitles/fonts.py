"""Phase 14 — local font discovery and validation. No downloads, ever.

Three validation tiers (honest about what each proves):
  valid     — file exists and opens as a font (PIL).
  uncertain — valid file, but Arabic coverage unprovable locally
              (no fontTools); Arabic text proceeds with a recorded warning.
  invalid   — missing or unopenable file: fail clearly.
A curated filename map covers well-known Arabic-capable Windows fonts.
"""
from __future__ import annotations

import os
from pathlib import Path

# Lowercase filenames known (by vendor documentation) to contain Arabic.
KNOWN_ARABIC_FONTS = frozenset({
    "arial.ttf", "arialbd.ttf", "ariali.ttf", "arialbi.ttf",
    "times.ttf", "timesbd.ttf", "timesi.ttf", "timesbi.ttf",
    "cour.ttf", "courbd.ttf", "couri.ttf", "courbi.ttf",
    "tahoma.ttf", "tahomabd.ttf",
    "segoeui.ttf", "segoeuib.ttf", "segoeuii.ttf", "segoeuil.ttf",
    "simpo.ttf", "simpbdo.ttf", "trado.ttf", "tradbdo.ttf",
    "andalus.ttf", "majalla.ttf", "majallab.ttf", "majallai.ttf",
    "sakkalsm.ttf", "dastinsm.ttf",
})

# filename (lower) -> display family for common Windows fonts.
FAMILY_MAP = {
    "arial.ttf": "Arial", "arialbd.ttf": "Arial", "ariali.ttf": "Arial",
    "arialbi.ttf": "Arial", "times.ttf": "Times New Roman",
    "cour.ttf": "Courier New", "tahoma.ttf": "Tahoma",
    "segoeui.ttf": "Segoe UI", "majalla.ttf": "Sakkal Majalla",
    "simpo.ttf": "Simplified Arabic", "trado.ttf": "Traditional Arabic",
}


class FontError(RuntimeError):
    pass


def windows_fonts_dir() -> Path:
    return Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"


def discover_fonts(fonts_dir: str | Path | None = None) -> list[dict]:
    """List usable .ttf/.otf/.ttc files. Never touches the network."""
    root = Path(fonts_dir) if fonts_dir else windows_fonts_dir()
    if not root.is_dir():
        return []
    out = []
    for ext in ("*.ttf", "*.otf", "*.ttc", "*.TTF", "*.OTF"):
        for p in sorted(root.glob(ext)):
            name = p.name.lower()
            out.append({"family": FAMILY_MAP.get(name, p.stem),
                        "file": str(p), "arabic_known": name in KNOWN_ARABIC_FONTS})
    return out


def _has_arabic(text: str) -> bool:
    return any("\u0600" <= ch <= "\u06ff" or "\u0750" <= ch <= "\u077f"
               or "\u08a0" <= ch <= "\u08ff" or "\ufb50" <= ch <= "\ufdff"
               or "\ufe70" <= ch <= "\ufeff" for ch in text)


def resolve_font(family: str = "Arial", font_file: str | None = None,
                 fonts_dir: str | Path | None = None) -> dict:
    """Resolve family (or explicit file) to a concrete font file on disk."""
    if font_file:
        p = Path(font_file)
        if not p.is_file():
            raise FontError(f"requested font file not found: {p}")
        return {"family": family, "file": str(p), "source": "explicit"}
    for entry in discover_fonts(fonts_dir):
        if entry["family"].lower() == family.lower():
            return {"family": entry["family"], "file": entry["file"],
                    "source": "discovery"}
    raise FontError(f"font family {family!r} not found in {fonts_dir or windows_fonts_dir()}")


def validate_font_for_text(font_file: str, text: str = "") -> dict:
    """Tiered validation: exists -> opens (PIL) -> Arabic coverage proof/uncertain."""
    p = Path(font_file)
    if not p.is_file():
        return {"status": "invalid", "reason": f"missing file: {p}"}
    try:
        from PIL import ImageFont
        ImageFont.truetype(str(p), 24)
    except Exception as exc:
        return {"status": "invalid", "reason": f"unopenable font file: {exc}"}
    needs_arabic = bool(text) and _has_arabic(text)
    if needs_arabic and p.name.lower() not in KNOWN_ARABIC_FONTS:
        return {"status": "uncertain",
                "reason": ("valid font file, but Arabic coverage cannot be proven "
                           "locally (no fontTools); rendering proceeds with a warning"),
                "arabic_known": False}
    return {"status": "valid",
            "reason": "exists, opens, Arabic coverage known" if needs_arabic
                      else "exists and opens",
            "arabic_known": (p.name.lower() in KNOWN_ARABIC_FONTS) if needs_arabic else True}
