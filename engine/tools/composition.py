"""Cinematic composition rules (Phase K). Pure checks + reject helper.

Safe areas for 1080x1920: text inside x[90,990], captions y<=1730,
keywords y>=230. Hierarchy: one focal element per shot.
"""
from __future__ import annotations

SAFE = {"x0": 90, "x1": 990, "caption_y_max": 1730, "keyword_y_min": 230}


def check_text_safe(x: float, y: float, role: str = "caption") -> dict:
    """Single text element inside safe areas? Pure."""
    ok = SAFE["x0"] <= x <= SAFE["x1"]
    if role == "caption":
        ok = ok and y <= SAFE["caption_y_max"]
    elif role == "keyword":
        ok = ok and y >= SAFE["keyword_y_min"]
    return {"ok": bool(ok), "role": role, "x": x, "y": y,
            "reason": "" if ok else f"{role} outside safe area"}


def check_hierarchy(elements: list[str]) -> dict:
    """At most one focal element (headline/keyword/stat) per shot. Pure."""
    focal = [e for e in elements
             if e in ("headline", "keyword", "stat", "title", "endcard")]
    ok = len(focal) <= 2
    return {"ok": ok, "focal": focal,
            "reason": "" if ok else f"{len(focal)} focal elements"}


def reject_asset(asset: dict, reason: str) -> dict:
    """Structured rejection of a technically valid but poor asset. Pure."""
    return {"asset": asset.get("file", "?"), "rejected": True,
            "reason": reason}


def check_shot(shot: dict, texts: list[dict] | None = None) -> list[dict]:
    """Composition audit for one shot. Returns issue dicts. Pure."""
    issues = []
    for t in (texts or []):
        r = check_text_safe(t.get("x", 540), t.get("y", 1500),
                            t.get("role", "caption"))
        if not r["ok"]:
            issues.append({"issue": "WEAK_COMPOSITION",
                           "shot": shot.get("shot_id", "?"),
                           "evidence": r["reason"],
                           "repair": {"capability": "REFRAME"}})
    h = check_hierarchy([t.get("role", "caption") for t in (texts or [])])
    if not h["ok"]:
        issues.append({"issue": "VISUAL_HIERARCHY", "shot": shot.get(
            "shot_id", "?"), "evidence": h["reason"],
            "repair": {"capability": "CAPTION_SIMPLIFY"}})
    return issues
