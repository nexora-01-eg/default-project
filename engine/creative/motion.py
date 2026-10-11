"""Reusable ASS motion vocabulary (deterministic, communicative only).

Every builder returns override-tag strings or full Dialogue lines for
libass (which shapes Arabic correctly). No animation for its own sake:
each primitive documents its communicative purpose. Positions are explicit
parameters (1080x1920 master assumed by callers).
"""


def fade(ms: int = 300) -> str:
    """Gentle entrance/exit (openings, keywords, titles)."""
    ms = max(0, int(ms))
    return f"{{\\fad({ms},{ms})}}"


def rise(x: int, y: int, lift: int = 40, ms: int = 300) -> str:
    """Fade + upward settle: entrances that should feel intentional."""
    ms = max(0, int(ms))
    return f"{{\\fad({ms},{ms})\\move({x},{y + lift},{x},{y})}}"


def slide_in(x: int, y: int, side: str = "left", dist: int = 120,
             ms: int = 300) -> str:
    """Directional entrance; alternate sides to avoid monotony."""
    ms = max(0, int(ms))
    if side == "left":
        return f"{{\\fad({ms},{ms})\\move({x - dist},{y},{x},{y})}}"
    return f"{{\\fad({ms},{ms})\\move({x + dist},{y},{x},{y})}}"


def emphasis() -> str:
    """Single-event emphasis (size + gold). Deliberately NOT a fake pulse:
    libass has no honest per-frame scale animation primitive here."""
    return "{\\fs84\\c&H40BFFF&}"


def ass_time(s: float) -> str:
    h = int(s // 3600)
    m = int((s % 3600) // 60)
    return f"{h}:{m:02d}:{(s % 60):05.2f}"


def dialogue(start: float, end: float, style: str, text: str,
             tags: str = "") -> str:
    return (f"Dialogue: 0,{ass_time(start)},{ass_time(end)},{style},"
            f"{tags}{text}")


def check_headline(text: str, limit: int = 8) -> dict:
    """TEXT_DRIVEN hierarchy rule: headlines stay short."""
    n = len(str(text or "").split())
    return {"words": n, "ok": n <= limit,
            "evidence": f"{n} words (limit {limit})"}
