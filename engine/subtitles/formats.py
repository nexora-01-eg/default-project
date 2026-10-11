"""Phase 14 — caption formats: SRT / WebVTT / ASS writers + style presets.

The JSON CaptionPlan is the source of truth; these are derived artifacts.
ASS carries style/positioning for burned-in rendering (libass); SRT/VTT
are sidecar formats. Karaoke animation: explicitly NOT modeled.
"""
from __future__ import annotations

STYLES: dict[str, dict] = {
    "default": {
        "font_family": "Arial", "font_size": 46, "bold": False, "italic": False,
        "alignment": "bottom", "margin_v": 24, "margin_h": 40, "max_lines": 2,
        "box": False, "outline": 2, "shadow": 0,
        "description": "neutral white bottom captions",
    },
    "clean": {
        "font_family": "Arial", "font_size": 44, "bold": False, "italic": False,
        "alignment": "bottom", "margin_v": 20, "margin_h": 32, "max_lines": 2,
        "box": False, "outline": 1, "shadow": 0,
        "description": "minimal thin-outline captions",
    },
    "social": {
        "font_family": "Arial", "font_size": 56, "bold": True, "italic": False,
        "alignment": "bottom", "margin_v": 96, "margin_h": 48, "max_lines": 2,
        "box": True, "outline": 1, "shadow": 0,
        "description": "bold boxed captions clear of platform UI",
    },
    "cinematic": {
        "font_family": "Times New Roman", "font_size": 40, "bold": False,
        "italic": True, "alignment": "bottom", "margin_v": 64, "margin_h": 96,
        "max_lines": 2, "box": False, "outline": 1, "shadow": 1,
        "description": "serif italic, generous margins",
    },
    "minimal": {
        "font_family": "Arial", "font_size": 36, "bold": False, "italic": False,
        "alignment": "bottom", "margin_v": 16, "margin_h": 24, "max_lines": 1,
        "box": False, "outline": 1, "shadow": 0,
        "description": "small single-line captions",
    },
}

_ALIGNMENT_ASS = {"bottom": 2, "center": 5, "top": 8}


class FormatError(RuntimeError):
    pass


def resolve_style(name: str) -> dict:
    if name not in STYLES:
        raise FormatError(f"unknown caption style {name!r}: "
                          f"expected one of {sorted(STYLES)}")
    return dict(STYLES[name])


def _ms_parts(t: float) -> tuple[int, int, int, int]:
    total_ms = max(0, int(round(t * 1000.0)))
    h, rem = divmod(total_ms, 3_600_000)
    m, rem = divmod(rem, 60_000)
    s, ms = divmod(rem, 1000)
    return h, m, s, ms


def srt_time(t: float) -> str:
    h, m, s, ms = _ms_parts(t)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def vtt_time(t: float) -> str:
    h, m, s, ms = _ms_parts(t)
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"


def write_srt(cues: list[dict]) -> str:
    """Deterministic SRT. Cues must already be ordered and valid."""
    blocks = []
    for i, c in enumerate(cues, 1):
        text = "\n".join(c.get("lines", []) or [c.get("text", "")])
        if not text.strip():
            raise FormatError(f"cue {c.get('cue_id', i)} has empty text")
        blocks.append(f"{i}\n{srt_time(c['start'])} --> {srt_time(c['end'])}\n{text}")
    return "\n\n".join(blocks) + "\n" if blocks else ""


def write_vtt(cues: list[dict], language: str = "") -> str:
    """Deterministic WebVTT (header + optional language tag)."""
    header = "WEBVTT" + (f" - {language}" if language else "")
    blocks = [header, ""]
    for c in cues:
        text = "\n".join(c.get("lines", []) or [c.get("text", "")])
        if not text.strip():
            raise FormatError(f"cue {c.get('cue_id', '?')} has empty text")
        blocks.append(f"{vtt_time(c['start'])} --> {vtt_time(c['end'])}\n{text}")
    return "\n\n".join(blocks) + "\n" if len(blocks) > 2 else header + "\n\n"


def _ass_color(primary_white: bool = True) -> tuple[str, str, str]:
    primary = "&H00FFFFFF" if primary_white else "&H00000000"
    return primary, "&H00000000", "&H80000000"  # primary, outline, translucent back


def write_ass(cues: list[dict], style: dict, font_family: str,
              width: int, height: int) -> str:
    """Styled ASS for burned-in rendering. Positions scale with frame size."""
    if width <= 0 or height <= 0:
        raise FormatError(f"invalid frame size {width}x{height}")
    scale = height / 1080.0
    size = max(8, int(round(style.get("font_size", 46) * scale)))
    mv = int(round(style.get("margin_v", 24) * scale))
    mh = int(round(style.get("margin_h", 40) * scale))
    alignment = _ALIGNMENT_ASS.get(style.get("alignment", "bottom"), 2)
    bold = -1 if style.get("bold") else 0
    italic = -1 if style.get("italic") else 0
    outline = style.get("outline", 2)
    shadow = style.get("shadow", 0)
    if style.get("box"):
        border_style, back = 3, "&H80000000"
    else:
        border_style, back = 1, "&H80000000"
    primary, outline_c, _ = _ass_color()
    header = (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        "WrapStyle: 0\n"
        f"PlayResX: {width}\n"
        f"PlayResY: {height}\n"
        "ScaledBorderAndShadow: yes\n"
        "YCbCr Matrix: TV.709\n"
        "\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
        "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
        "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding\n"
        f"Style: Default,{font_family},{size},{primary},{primary},"
        f"{outline_c},{back},{bold},{italic},0,0,100,100,0,0,"
        f"{border_style},{outline},{shadow},{alignment},{mh},{mh},{mv},1\n"
        "\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, "
        "Effect, Text\n"
    )
    events = []
    for c in cues:
        text = "\\N".join(c.get("lines", []) or [c.get("text", "")])
        if not text.strip():
            raise FormatError(f"cue {c.get('cue_id', '?')} has empty text")
        text = text.replace("{", "\\{").replace("}", "\\}")
        h1, m1, s1, ms1 = _ms_parts(c["start"])
        h2, m2, s2, ms2 = _ms_parts(c["end"])
        start = f"{h1}:{m1:02d}:{s1:02d}.{ms1 // 10:02d}"
        end = f"{h2}:{m2:02d}:{s2:02d}.{ms2 // 10:02d}"
        events.append(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{text}")
    return header + "\n".join(events) + ("\n" if events else "")


_EMPHASIS_OPEN = {"keyword": r"{\1c&H0000FFFF&}", "important_words": r"{\1c&H0000FFFF&\b1}"}
_EMPHASIS_CLOSE = {"keyword": r"{\1c}", "important_words": r"{\1c\b0}"}


def _tag_lines_with_emphasis(lines: list[str], tokens: list[str],
                             emph_spans: list[dict]) -> list[str]:
    """Deterministic emphasis tagging. emph_spans: [{text, occurrence}].
    Falls back to untagged lines on any mismatch (never corrupt text)."""
    if not emph_spans:
        return [l.replace("{", "\\{").replace("}", "\\}") for l in lines]
    flat = " ".join(lines)
    if " ".join(tokens) != flat:
        return [l.replace("{", "\\{").replace("}", "\\}") for l in lines]
    # Map token index -> emphasis kind by occurrence order.
    by_text: dict[str, list[int]] = {}
    for i, t in enumerate(tokens):
        by_text.setdefault(t, []).append(i)
    used: dict[str, int] = {}
    kinds: dict[int, str] = {}
    for span in emph_spans:
        lst = by_text.get(span["text"], [])
        n = used.get(span["text"], 0)
        if n < len(lst):
            kinds[lst[n]] = span.get("kind", "keyword")
            used[span["text"]] = n + 1
    out_lines = []
    idx = 0
    for line in lines:
        parts = []
        for tok in line.split(" "):
            safe = tok.replace("{", "\\{").replace("}", "\\}")
            if idx in kinds:
                o = _EMPHASIS_OPEN[kinds[idx]]
                c = _EMPHASIS_CLOSE[kinds[idx]]
                parts.append(f"{o}{safe}{c}")
            else:
                parts.append(safe)
            idx += 1
        out_lines.append(" ".join(parts))
    return out_lines


def write_ass_visual(cues: list[dict], style: dict, font_family: str,
                     width: int, height: int,
                     placements: dict | None = None,
                     emphasis: dict | None = None,
                     adaptations: dict | None = None) -> str:
    """ASS with per-event alignment overrides + inline emphasis tags.

    cues: mapped cue dicts (cue_id, start, end, text, lines). placements:
    cue_id -> position (top|center|bottom). emphasis: cue_id ->
    [{text, occurrence, kind}]. adaptations: cue_id -> style patch dict.
    Unknown cue ids in the maps are ignored (defensive, never crash).
    """
    placements = placements or {}
    emphasis = emphasis or {}
    adaptations = adaptations or {}
    if width <= 0 or height <= 0:
        raise FormatError(f"invalid frame size {width}x{height}")
    scale = height / 1080.0
    size = max(8, int(round(style.get("font_size", 46) * scale)))
    mv = int(round(style.get("margin_v", 24) * scale))
    mh = int(round(style.get("margin_h", 40) * scale))
    bold = -1 if style.get("bold") else 0
    italic = -1 if style.get("italic") else 0
    base_outline = style.get("outline", 2)
    shadow = style.get("shadow", 0)
    base_box = bool(style.get("box"))
    primary, outline_c, back = _ass_color()[0], _ass_color()[1], "&H80000000"
    base_alignment = _ALIGNMENT_ASS.get(style.get("alignment", "bottom"), 2)
    need_box_style = any((adaptations.get(c.get("cue_id", ""), {}) or {}).get("box")
                         for c in cues)
    header = (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        "WrapStyle: 0\n"
        f"PlayResX: {width}\n"
        f"PlayResY: {height}\n"
        "ScaledBorderAndShadow: yes\n"
        "YCbCr Matrix: TV.709\n"
        "\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
        "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
        "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding\n"
        f"Style: Default,{font_family},{size},{primary},{primary},"
        f"{outline_c},{back},{bold},{italic},0,0,100,100,0,0,"
        f"{3 if base_box else 1},{base_outline},{shadow},{base_alignment},{mh},{mh},{mv},1\n"
    )
    if need_box_style:
        header += (
            f"Style: DefaultBox,{font_family},{size},{primary},{primary},"
            f"{outline_c},{back},{bold},{italic},0,0,100,100,0,0,"
            f"3,{base_outline},{shadow},{alignment},{mh},{mh},{mv},1\n"
        )
    header += (
        "\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, "
        "Effect, Text\n"
    )
    events = []
    for c in cues:
        lines = list(c.get("lines", []) or [c.get("text", "")])
        tokens = " ".join(lines).split(" ")
        emp = emphasis.get(c.get("cue_id", ""), []) or []
        tagged = _tag_lines_with_emphasis(lines, tokens, emp)
        text = "\\N".join(tagged)
        if not text.replace("\\N", "").strip():
            raise FormatError(f"cue {c.get('cue_id', '?')} has empty text")
        adapt = adaptations.get(c.get("cue_id", ""), {}) or {}
        # Style-level adaptation rendered per event: box via style switch,
        # outline (and shadow where set) via inline overrides.
        ev_style = "DefaultBox" if adapt.get("box") else "Default"
        overrides = ""
        if "outline" in adapt:
            overrides += f"{{\\bord{int(adapt['outline'])}}}"
        if "shadow" in adapt:
            overrides += f"{{\\shad{int(adapt['shadow'])}}}"
        text = overrides + text if overrides else text
        pos = placements.get(c.get("cue_id", ""), style.get("alignment", "bottom"))
        an = {"top": 8, "center": 5, "bottom": 2}.get(pos, 2)
        h1, m1, s1, ms1 = _ms_parts(c["start"])
        h2, m2, s2, ms2 = _ms_parts(c["end"])
        start = f"{h1}:{m1:02d}:{s1:02d}.{ms1 // 10:02d}"
        end = f"{h2}:{m2:02d}:{s2:02d}.{ms2 // 10:02d}"
        events.append(f"Dialogue: 0,{start},{end},{ev_style},,0,0,0,,{{\\an{an}}}{text}")
    return header + "\n".join(events) + ("\n" if events else "")
