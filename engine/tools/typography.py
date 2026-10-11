# -*- coding: utf-8 -*-
"""Typography rules (Phase E): layers, emphasis, breaks, safe zones, bidi.

Findings baked in (Phase A frame review):
- libass shapes Arabic correctly (ligatures, diacritics, RTL order).
- Latin runs inside Arabic MUST be wrapped in bidi isolates (U+2066 LRI
  + U+2069 PDI) or prefixes like الـ detach to the wrong side.
- Trailing Latin punctuation (e.g. ".") mirrors to line start: use Arabic
  stops (؟ ! …) or place Latin stops deliberately.
- Color emoji has no font in the chain: CAPABILITY_MISSING (omit or use a
  PNG overlay, never tofu).
"""
from __future__ import annotations

import re

LATIN_RUN = re.compile(r"[A-Za-z][A-Za-z0-9'\-]*")
LRI, PDI = "\u2066", "\u2069"

MAX_LAYERS = 2
MAX_BODY_WORDS = 8
SAFE = {"margin_v_body": 190, "margin_v_key": 230, "margin_h": 90,
        "title_size": 104, "body_size": 54, "key_size": 70,
        "end_size": 84}


def isolate_latin(text: str) -> str:
    """Wrap Latin runs in bidi isolates so Arabic affixes stay attached.

    Pure. Verified by frame review (workflowالـ defect -> fixed).
    """
    return LATIN_RUN.sub(lambda m: LRI + m.group(0) + PDI, text)


def split_lines(text: str, limit: int = MAX_BODY_WORDS) -> list[str]:
    """Greedy word wrap. Pure."""
    words, lines, cur = text.split(), [], []
    for w in words:
        cur.append(w)
        if len(cur) >= limit:
            lines.append(" ".join(cur))
            cur = []
    if cur:
        lines.append(" ".join(cur))
    return lines or ["…"]


def check_layers(layers: list[str]) -> dict:
    """Overload guard: max 2 simultaneous text layers."""
    ok = len(layers) <= MAX_LAYERS
    return {"ok": ok, "layers": list(layers),
            "reason": "" if ok else f"{len(layers)} layers > 2"}


def emphasis_spans(text: str, keywords: list[str]) -> list[tuple]:
    """Locate keyword spans for Key-layer emphasis. Pure."""
    out = []
    for kw in keywords:
        i = text.find(kw)
        if i >= 0:
            out.append((kw, i, i + len(kw)))
    return out


def style_for(role: str) -> str:
    """Role -> ASS style name."""
    return {"subtitle": "Body", "emphasis": "Key", "headline": "Title",
            "label": "Key", "statistic": "Title", "annotation": "Body",
            "ui": "Key", "cta": "End"}.get(role, "Body")
