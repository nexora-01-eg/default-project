"""Constructed-graphics overlay path: ICON requirement -> discovery -> raster.

Read-only over Arsenal originals (never modified, hashes recorded). Raster and
overlay execution are deterministic gateway operations. Unsupported requests
raise IconCapabilityError (structured, staged) - never a silent fallback.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

SCHEMA_VERSION = "icon-overlay-1.0"
CANVAS_W, CANVAS_H, CANVAS_FPS = 1080, 1920, 30

LUCIDE_ROOT = Path("F:/Arsenal/02_Icons/lucide/icons")
LUCIDE_LICENSE = "ISC (Lucide Icons and Contributors)"

_CHROME_CANDIDATES = (
    shutil.which("chrome"),
    shutil.which("chrome.exe"),
    shutil.which("chromium"),
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
)


class IconCapabilityError(Exception):
    """Structured capability failure. stage in discovery|raster|contract|render."""

    def __init__(self, message: str, stage: str = "contract"):
        super().__init__(f"[{stage}] {message}")
        self.stage = stage


def _sha256(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def find_chrome() -> str:
    """Locate a usable headless-Chrome binary (PATH + known install dirs)."""
    for cand in _CHROME_CANDIDATES:
        if cand and Path(cand).is_file():
            return str(cand)
    raise IconCapabilityError(
        "no headless-Chrome binary found (PATH + Program Files probed); "
        "SVG rasterization unavailable on this machine",
        stage="raster")


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def search_icons(intent: str, keywords: list[str], top_k: int = 5) -> list[dict]:
    """Semantic icon discovery over Lucide sidecar tags/categories.

    Token-level matching (no substring accidents: "watch" must not match
    "swatch"). Scoring: tag hit x3, category hit x2, name hit x1. A score of
    0 (filename-only resemblance) never qualifies. Deterministic: ties
    broken by icon name.
    """
    if not LUCIDE_ROOT.is_dir():
        raise IconCapabilityError(f"icon root missing: {LUCIDE_ROOT}",
                                  stage="discovery")
    keys = set()
    for k in keywords:
        keys |= _tokens(k)
    if not keys:
        raise IconCapabilityError("empty keyword set", stage="discovery")
    out = []
    for jf in sorted(LUCIDE_ROOT.glob("*.json")):
        name = jf.stem
        svg = jf.with_suffix(".svg")
        if not svg.is_file():
            continue
        try:
            meta = json.loads(jf.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        tag_toks: set[str] = set()
        for t in meta.get("tags", []):
            tag_toks |= _tokens(str(t))
        cat_toks: set[str] = set()
        for c in meta.get("categories", []):
            cat_toks |= _tokens(str(c))
        hit_tags = sorted(keys & tag_toks)
        hit_cats = sorted(keys & cat_toks)
        name_hit = sorted(keys & _tokens(name))
        if not hit_tags and not hit_cats:
            continue  # filename resemblance alone never qualifies
        score = len(hit_tags) * 3 + len(hit_cats) * 2 + len(name_hit)
        out.append({"name": name, "set": "lucide",
                    "source_path": str(svg),
                    "sha256": _sha256(svg),
                    "bytes": svg.stat().st_size,
                    "tags": hit_tags, "categories": hit_cats,
                    "score": score, "intent": intent,
                    "license": LUCIDE_LICENSE})
    out.sort(key=lambda r: (-r["score"], r["name"]))
    return out[:top_k]


def _wrap_svg(src: Path, size: int, color: str) -> str:
    """Inline the ORIGINAL svg bytes with only root sizing/color attributes.

    Inner path/circle data is byte-identical to the Arsenal file (verified by
    test). color replaces currentColor via the CSS `color` property.
    """
    raw = src.read_text(encoding="utf-8")
    if "<svg" not in raw:
        raise IconCapabilityError(f"not an SVG document: {src}",
                                  stage="raster")
    patched, n = re.subn(r"<svg\b",
                         f'<svg width="{size}" height="{size}"',
                         raw, count=1)
    if n != 1:
        raise IconCapabilityError(f"SVG root not found exactly once: {src}",
                                  stage="raster")
    return ("<!DOCTYPE html><html><head><meta charset=\"utf-8\">"
            "<style>html,body{margin:0;padding:0;background:rgba(0,0,0,0);"
            f"color:{color}}}</style></head><body>"
            + patched + "</body></html>")


def rasterize_icon(candidate: dict, dst: str | Path, size: int = 300,
                   color: str = "#FFD98A", chrome: str | None = None,
                   timeout: int = 120) -> dict:
    """Rasterize the discovered SVG to a transparent PNG (deterministic)."""
    src = Path(candidate["source_path"])
    if not src.is_file():
        raise IconCapabilityError(f"icon source vanished: {src}",
                                  stage="raster")
    if _sha256(src) != candidate["sha256"]:
        raise IconCapabilityError(
            f"icon bytes changed since discovery: {src}", stage="raster")
    if not re.fullmatch(r"#[0-9A-Fa-f]{6}", color or ""):
        raise IconCapabilityError(f"bad color (need #RRGGBB): {color!r}",
                                  stage="contract")
    if size <= 0 or size > CANVAS_W:
        raise IconCapabilityError(f"bad raster size: {size}", stage="contract")
    exe = chrome or find_chrome()
    dst_p = Path(dst)
    dst_p.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="al-montier-icon-") as tmp:
        html = Path(tmp) / "icon.html"
        png = Path(tmp) / "icon.png"
        html.write_text(_wrap_svg(src, size, color), encoding="utf-8")
        proc = subprocess.run(
            [exe, "--headless", "--disable-gpu", "--hide-scrollbars",
             f"--screenshot={png}", f"--window-size={size},{size}",
             "--default-background-color=00000000",
             "--virtual-time-budget=3000", html.as_uri()],
            capture_output=True, text=True, timeout=timeout)
        if not png.is_file() or png.stat().st_size == 0:
            raise IconCapabilityError(
                f"chrome raster failed (rc={proc.returncode}): "
                f"{(proc.stderr or '')[-300:]}", stage="raster")
        data = png.read_bytes()
        dst_p.write_bytes(data)
    return {"png": str(dst_p), "size": size, "color": color,
            "source_sha256": candidate["sha256"],
            "png_sha256": hashlib.sha256(data).hexdigest(),
            "renderer": f"headless-chrome ({Path(exe).name})"}


def build_overlay_op(candidate: dict, x: int, y: int, size: int,
                     start: float, duration: float,
                     color: str = "#FFD98A", opacity: float = 1.0,
                     reason: str = "", decided_by: str = "planner",
                     approved_by: str = "director") -> dict:
    """Build the serializable overlay decision (no rendering)."""
    return {"schema_version": SCHEMA_VERSION, "type": "overlay",
            "op_id": f"ovl_{candidate['name']}_001",
            "requirement": {"id": "req-icon-001", "kind": "ICON",
                            "intent": candidate.get("intent", "")},
            "asset": {"kind": "ICON", "name": candidate["name"],
                      "set": candidate["set"],
                      "source_path": candidate["source_path"],
                      "sha256": candidate["sha256"],
                      "bytes": candidate["bytes"],
                      "license": candidate["license"]},
            "placement": {"x": x, "y": y, "w": size, "h": size},
            "timing": {"start": start, "duration": duration},
            "style": {"color": color, "opacity": opacity},
            "reason": reason, "decided_by": decided_by,
            "approved_by": approved_by}


def validate_overlay_op(op: dict, canvas_w: int = CANVAS_W,
                        canvas_h: int = CANVAS_H,
                        media_duration: float | None = None) -> list[str]:
    """Validate an overlay decision. Returns error list (empty = valid)."""
    errors: list[str] = []
    if not isinstance(op, dict) or op.get("type") != "overlay":
        return ["op.type must be 'overlay'"]
    if op.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"unsupported schema: {op.get('schema_version')}")
    asset = op.get("asset", {})
    src = asset.get("source_path")
    if asset.get("kind") != "ICON" or not src:
        errors.append("asset.kind must be ICON with source_path")
    elif not Path(src).is_file():
        errors.append(f"asset file missing: {src}")
    elif Path(src).suffix.lower() != ".svg":
        errors.append(f"asset must be .svg, got {Path(src).suffix}")
    if asset.get("sha256") and Path(src or "").is_file():
        if _sha256(src) != asset["sha256"]:
            errors.append("asset bytes differ from decision sha256")
    pl = op.get("placement", {})
    for key in ("x", "y", "w", "h"):
        if not isinstance(pl.get(key), int) or pl[key] < 0:
            errors.append(f"placement.{key} must be a non-negative int")
    if not errors:
        if pl["w"] <= 0 or pl["h"] <= 0:
            errors.append("placement w/h must be > 0")
        if pl["x"] + pl["w"] > canvas_w or pl["y"] + pl["h"] > canvas_h:
            errors.append("placement exceeds 1080x1920 canvas")
    tm = op.get("timing", {})
    try:
        s, d = float(tm.get("start", -1)), float(tm.get("duration", 0))
    except (TypeError, ValueError):
        errors.append("timing.start/duration must be numbers")
    else:
        if s < 0 or d <= 0:
            errors.append("timing must satisfy start>=0, duration>0")
        if media_duration is not None and s + d > media_duration + 1e-6:
            errors.append("overlay window exceeds media duration")
    st = op.get("style", {})
    if not re.fullmatch(r"#[0-9A-Fa-f]{6}", str(st.get("color", ""))):
        errors.append("style.color must be #RRGGBB")
    try:
        o = float(st.get("opacity", -1))
        if not 0.0 < o <= 1.0:
            errors.append("style.opacity must be in (0, 1]")
    except (TypeError, ValueError):
        errors.append("style.opacity must be numeric")
    if not op.get("reason"):
        errors.append("reason is required (no unexplained overlays)")
    if not op.get("decided_by") or not op.get("approved_by"):
        errors.append("decided_by + approved_by required (renderer never decides)")
    return errors


def execute_overlay(base_video: str | Path, raster_png: str | Path,
                    op: dict, dst: str | Path,
                    encoder: str = "libx264",
                    timeout: int = 600) -> dict:
    """Execute a VALIDATED overlay decision via the ffmpeg gateway.

    Raises IconCapabilityError(stage=contract) on validation failure and
    IconCapabilityError(stage=render) on ffmpeg failure. Never falls back.
    """
    from engine.rendering.ffmpeg import overlay_asset
    errors = validate_overlay_op(op)
    if errors:
        raise IconCapabilityError("invalid overlay op: " + "; ".join(errors),
                                  stage="contract")
    pl, tm, st = op["placement"], op["timing"], op["style"]
    return overlay_asset(base_video, raster_png, dst,
                         x=pl["x"], y=pl["y"], w=pl["w"], h=pl["h"],
                         start=float(tm["start"]),
                         duration=float(tm["duration"]),
                         opacity=float(st["opacity"]),
                         encoder=encoder, timeout=timeout)
