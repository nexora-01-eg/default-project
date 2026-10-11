"""Shot-level graphics composition layer (graphics[] per shot).

Supported first-layer types: icon (Arsenal raster, see icons.py) + label
(Pillow Latin chip). Other named types (stat_card, callout, headline,
svg_graphic) are explicitly declared but unsupported: requesting one raises
IconCapabilityError(stage=contract, CAPABILITY_MISSING) - never silent.

Ownership: planner proposes (reasons required), director approves/rejects
(recorded), renderer executes approved ops in layer order. No invention.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from engine.graphics import icons as _icons

SCHEMA_VERSION = "shot-graphics-1.0"
SUPPORTED_TYPES = ("icon", "label")
KNOWN_UNSUPPORTED = ("stat_card", "callout", "headline", "svg_graphic")

LABEL_TEXT_RE = re.compile(r"[A-Za-z0-9 .\-:%+/×]+")
LABEL_FONT = "C:/Windows/Fonts/arialbd.ttf"
LABEL_FG = "#FFD98A"
LABEL_BG = (11, 16, 46, 210)


def _spec_sha(spec: dict) -> str:
    return hashlib.sha256(json.dumps(spec, sort_keys=True,
                                     ensure_ascii=False).encode("utf-8")).hexdigest()


def request_icon(intent: str, keywords: list[str]) -> dict:
    """Planner-side: resolve an icon requirement to a decision (no render)."""
    cands = _icons.search_icons(intent, keywords, top_k=5)
    if not cands:
        raise _icons.IconCapabilityError(f"no icon matches intent: {intent}",
                                         stage="discovery")
    best = cands[0]
    return {"type": "icon", "candidate": best,
            "reason": (f"score {best['score']}: tag evidence {best['tags']} "
                       f"for intent '{intent}'"),
            "confidence": "HIGH" if best["score"] >= 6 else "MEDIUM"}


def request_label(text: str, role: str) -> dict:
    """Planner-side: specify a Latin text chip (Arabic stays in libass)."""
    if not text or not LABEL_TEXT_RE.fullmatch(text):
        raise _icons.IconCapabilityError(
            f"label text must match Latin/digits/punct {LABEL_TEXT_RE.pattern}; "
            f"got {text!r} (Arabic text belongs in the caption system)",
            stage="contract")
    return {"type": "label", "text": text, "role": role,
            "reason": f"contextual tag '{text}' as {role}",
            "confidence": "HIGH"}


def propose_shot_graphics(shot_id: str, requests: list[dict]) -> list[dict]:
    """Planner: turn requirement requests into reasoned graphic proposals."""
    proposals = []
    for i, req in enumerate(requests):
        kind = req.get("kind")
        if kind in KNOWN_UNSUPPORTED:
            raise _icons.IconCapabilityError(
                f"graphic type '{kind}' declared but unsupported "
                f"(supported: {list(SUPPORTED_TYPES)})",
                stage="contract")
        if kind not in SUPPORTED_TYPES:
            raise _icons.IconCapabilityError(f"unknown graphic type: {kind!r}",
                                             stage="contract")
        if kind == "icon":
            dec = request_icon(req["intent"], req.get("keywords", []))
            proposals.append({
                "type": "icon", "layer": i, "shot_id": shot_id,
                "candidate": dec["candidate"],
                "placement": req["placement"], "timing": req["timing"],
                "style": req.get("style", {"color": "#FFD98A",
                                           "opacity": 1.0}),
                "semantic_role": req.get("role", "visual metaphor"),
                "reason": dec["reason"], "decided_by": "planner",
                "confidence": dec["confidence"]})
        else:
            dec = request_label(req["text"], req.get("role", "tag"))
            proposals.append({
                "type": "label", "layer": i, "shot_id": shot_id,
                "text": dec["text"],
                "placement": req["placement"], "timing": req["timing"],
                "style": req.get("style", {"fg": LABEL_FG, "size": 54,
                                           "pad": 28}),
                "semantic_role": dec["role"],
                "reason": dec["reason"], "decided_by": "planner",
                "confidence": dec["confidence"]})
    return proposals


def _boxes_overlap(a: dict, b: dict) -> bool:
    ax, ay, aw, ah = (a["x"], a["y"], a["w"], a["h"])
    bx, by, bw, bh = (b["x"], b["y"], b["w"], b["h"])
    return not (ax + aw <= bx or bx + bw <= ax or ay + ah <= by or by + bh <= ay)


def review_shot_graphics(proposals: list[dict],
                         max_per_shot: int = 3) -> dict:
    """Director: approve/reject each proposal. Recorded; no silent drops."""
    approved, rejected, seen_icons = [], [], set()
    if len(proposals) > max_per_shot:
        return {"approved": [], "rejected": [{
            "proposal": p, "reason": f"exceeds max {max_per_shot} per shot"}
            for p in proposals], "rule": "density"}
    sized = []
    for p in proposals:
        p = dict(p)
        pl = dict(p.get("placement", {}))
        if not isinstance(pl.get("x"), int) or not isinstance(pl.get("y"), int) \
                or pl["x"] < 0 or pl["y"] < 0:
            rejected.append({"proposal": p, "reason":
                             "placement x/y must be non-negative ints"})
            continue
        if p["type"] == "label":
            st = p.get("style", {})
            w, h, _ = _measure_label(p["text"], st.get("size", 54),
                                     st.get("pad", 28))
            pl["w"], pl["h"] = w, h
        elif not isinstance(pl.get("w"), int) \
                or not isinstance(pl.get("h"), int) or pl["w"] <= 0 \
                or pl["h"] <= 0:
            rejected.append({"proposal": p, "reason":
                             "icon placement w/h must be positive ints"})
            continue
        if pl["x"] + pl["w"] > 1080 or pl["y"] + pl["h"] > 1920:
            rejected.append({"proposal": p, "reason":
                             "placement exceeds 1080x1920 canvas"})
            continue
        p["placement"] = pl
        sized.append(p)
    for p in sized:
        if p["type"] == "icon":
            name = p["candidate"]["name"]
            if name in seen_icons:
                rejected.append({"proposal": p, "reason":
                                 f"icon '{name}' already used in this shot"})
                continue
            seen_icons.add(name)
        clash = next((q for q in approved
                      if _boxes_overlap(p["placement"], q["placement"])
                      and not (p["timing"]["start"] >=
                               q["timing"]["start"] + q["timing"]["duration"]
                               or q["timing"]["start"] >=
                               p["timing"]["start"] + p["timing"]["duration"])),
                     None)
        if clash is not None:
            rejected.append({"proposal": p, "reason":
                             f"box overlaps layer {clash['layer']} in time; "
                             f"reposition or retime required"})
            continue
        p = dict(p, approved_by="director",
                 approval_note="hierarchy/timing/placement accepted")
        approved.append(p)
    approved.sort(key=lambda p: p["layer"])
    return {"approved": approved, "rejected": rejected, "rule": "composition"}


def _measure_label(text: str, font_size: int, pad: int) -> tuple:
    from PIL import Image, ImageDraw, ImageFont
    font = ImageFont.truetype(LABEL_FONT, font_size)
    d = ImageDraw.Draw(Image.new("RGBA", (8, 8)))
    bbox = d.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0] + pad * 2, bbox[3] - bbox[1] + pad * 2, bbox


def render_label(text: str, dst: str | Path, font_size: int = 54,
                 fg: str = LABEL_FG, pad: int = 28) -> dict:
    """Render a deterministic Latin label chip (transparent RGBA PNG)."""
    from PIL import Image, ImageDraw, ImageFont
    if not LABEL_TEXT_RE.fullmatch(text or ""):
        raise _icons.IconCapabilityError(f"bad label text: {text!r}",
                                         stage="contract")
    w, h, bbox = _measure_label(text, font_size, pad)
    font = ImageFont.truetype(LABEL_FONT, font_size)
    chip = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(chip)
    d.rounded_rectangle([0, 0, chip.width - 1, chip.height - 1],
                        radius=min(36, pad), fill=LABEL_BG)
    d.text((pad - bbox[0], pad - bbox[1]), text, font=font, fill=fg)
    dst_p = Path(dst)
    dst_p.parent.mkdir(parents=True, exist_ok=True)
    chip.save(dst_p)
    return {"png": str(dst_p), "w": chip.width, "h": chip.height,
            "spec_sha": _spec_sha({"text": text, "size": font_size,
                                   "fg": fg, "pad": pad})}


def _cached(cache_dir: Path, key: str, ext: str) -> Path:
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / f"{key}{ext}"


def rasterize_cached(kind: str, payload: dict, cache_dir: str | Path,
                    size: int = 0, color: str = "#FFD98A") -> dict:
    """Content-hash raster cache: identical specs never re-rasterize.

    Returns raster record + cached flag. intellectually honest: cache hits
    skip chrome/Pillow work; video segments are NOT cached (see report).
    """
    cache = Path(cache_dir)
    if kind == "icon":
        key = _spec_sha({"icon": payload["sha256"], "size": size,
                         "color": color})
        dst = _cached(cache, key, ".png")
        if dst.is_file():
            return {"png": str(dst), "cached": True, "key": key,
                    "source_sha256": payload["sha256"]}
        rec = _icons.rasterize_icon(payload, dst, size=size, color=color)
        rec["cached"], rec["key"] = False, key
        return rec
    if kind == "label":
        key = _spec_sha({"label": payload["text"],
                         "size": payload.get("size", 54),
                         "fg": payload.get("fg", LABEL_FG),
                         "pad": payload.get("pad", 28)})
        dst = _cached(cache, key, ".png")
        if dst.is_file():
            from PIL import Image
            im = Image.open(dst)
            return {"png": str(dst), "cached": True, "key": key,
                    "w": im.width, "h": im.height, "spec_sha": key}
        rec = render_label(payload["text"], dst,
                           font_size=payload.get("size", 54),
                           fg=payload.get("fg", LABEL_FG),
                           pad=payload.get("pad", 28))
        rec["cached"], rec["key"] = False, key
        return rec
    raise _icons.IconCapabilityError(f"cannot rasterize kind: {kind}",
                                     stage="contract")


def compose_shot(base: str | Path, approved: list[dict],
                 dst: str | Path, cache_dir: str | Path,
                 encoder: str = "libx264",
                 timeout: int = 600) -> dict:
    """Shared graphics composition gateway: layers applied in layer order.

    Executes ONLY director-approved ops. One ffmpeg overlay per layer (shared
    `overlay_asset` op - no duplicated filter logic). Returns per-layer
    records + cache/ffmpeg accounting.
    """
    from engine.rendering.ffmpeg import overlay_asset
    if not approved:
        raise _icons.IconCapabilityError("nothing approved to compose",
                                         stage="contract")
    cur, layers, calls, hits = Path(base), [], 0, 0
    work = Path(dst).parent
    for op in sorted(approved, key=lambda o: o["layer"]):
        if op["type"] == "icon":
            rast = rasterize_cached("icon", op["candidate"], cache_dir,
                                    size=op["placement"]["w"],
                                    color=op["style"].get("color", "#FFD98A"))
            w = h = op["placement"]["w"]
            asset_ref = {"kind": "ICON", "name": op["candidate"]["name"],
                         "sha256": op["candidate"]["sha256"]}
        else:
            spec = {"text": op["text"], **op.get("style", {})}
            rast = rasterize_cached("label", spec, cache_dir)
            w, h = rast["w"], rast["h"]
            asset_ref = {"kind": "LABEL", "text": op["text"],
                         "spec_sha": rast.get("spec_sha", rast.get("key"))}
        hits += 1 if rast.get("cached") else 0
        step = work / f"layer{op['layer']:02d}.mp4"
        overlay_asset(cur, rast["png"], step,
                      x=op["placement"]["x"], y=op["placement"]["y"],
                      w=w, h=h, start=float(op["timing"]["start"]),
                      duration=float(op["timing"]["duration"]),
                      opacity=float(op["style"].get("opacity", 1.0)),
                      encoder=encoder, timeout=timeout)
        calls += 1
        layers.append({"layer": op["layer"], "type": op["type"],
                       "asset": asset_ref, "raster": rast,
                       "timing": op["timing"], "placement": op["placement"],
                       "role": op.get("semantic_role", "")})
        cur = step
    final = Path(dst)
    if cur != final:
        cur.replace(final)
    return {"output": str(final), "layers": layers, "cache_hits": hits,
            "ffmpeg_calls": calls}
