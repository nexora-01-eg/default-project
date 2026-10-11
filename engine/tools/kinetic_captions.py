"""Word-timed kinetic captions (additive): words.json -> ASS events.

Rules (compositional, overload-safe):
- max 2 visual layers: narration cue (Body) + optional keyword (Key)
- per-word karaoke highlight (\\kf) for the active word inside each cue
- cues chunked to <= 8 words; English tokens get Key-color emphasis
- Arabic shaping left to libass (no reshaper dependency)
- timings come ONLY from STT word timestamps; never invented
"""
from __future__ import annotations

import json
import re
from pathlib import Path

LATIN = re.compile(r"[A-Za-z]")


def _is_latin(word: str) -> bool:
    return bool(LATIN.search(word or ""))


HIGH_P, MED_P = 0.7, 0.4


def confidence_tier(p: float) -> str:
    """HIGH/MEDIUM/LOW confidence tier for one word. Pure."""
    p = float(p or 0.0)
    if p >= HIGH_P:
        return "HIGH_CONFIDENCE"
    if p >= MED_P:
        return "MEDIUM_CONFIDENCE"
    return "LOW_CONFIDENCE"


def confidence_report(words: list[dict]) -> dict:
    """Aggregate tiers; LOW-heavy input must not get karaoke. Pure."""
    tiers = [confidence_tier(w.get("p", 0.0)) for w in words]
    low_ratio = (tiers.count("LOW_CONFIDENCE") / max(len(tiers), 1))
    return {"tiers": tiers,
            "low_ratio": round(low_ratio, 3),
            "mode": "phrase" if low_ratio > 0.35 else "word"}


def chunk_words(words: list[dict], limit: int = 8) -> list[list[dict]]:
    """Greedy cue chunking on word gaps. Pure."""
    cues, cur, prev_end = [], [], None
    for w in words:
        if cur and (len(cur) >= limit or
                    (prev_end is not None and w["start"] - prev_end > 1.2)):
            cues.append(cur)
            cur = []
        cur.append(w)
        prev_end = w["end"]
    if cur:
        cues.append(cur)
    return cues


def ass_time(s: float) -> str:
    h = int(s // 3600)
    m = int((s % 3600) // 60)
    return f"{h}:{m:02d}:{s % 60:05.2f}"


def cue_text(cue: list[dict], karaoke: bool = True) -> str:
    """Cue with optional per-word \\kf highlight + Latin emphasis + isolates.

    karaoke=False renders a safe phrase cue (used when word confidence is
    LOW). Latin runs always get bidi isolates (typography rule). Pure.
    """
    from engine.tools import typography as _typo
    parts = []
    for w in cue:
        token = _typo.isolate_latin(w["w"])
        if karaoke:
            dur_cs = max(1, int(round((w["end"] - w["start"]) * 100)))
            token = "{\\kf%d}%s" % (dur_cs, token)
        if _is_latin(w["w"]):
            token = "{\\c&H00FFD98A&}" + token + "{\\c&H00FFFFFF&}"
        parts.append(token)
    return " ".join(parts)


def build_ass(words_path: str | Path, dst: str | Path, *,
              keywords: list[tuple] | None = None,
              title: tuple | None = None,
              endcard: tuple | None = None) -> dict:
    """Build a kinetic ASS file from STT words. Timings are STT-true."""
    from engine.creative import motion as _motion
    words = json.loads(Path(words_path).read_text(encoding="utf-8"))["words"]
    head = ("[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\n"
            "PlayResY: 1920\nScaledBorderAndShadow: yes\n\n"
            "[V4+ Styles]\n"
            "Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, "
            "BackColour, Bold, Alignment, MarginV\n"
            "Style: Title,Arial,104,&H00FFD98A,&H80000000,&H80000000,1,5,120\n"
            "Style: Body,Arial,54,&H00FFFFFF,&H90000000,&H90000000,1,2,190\n"
            "Style: Key,Arial,70,&H00FFD98A,&H90000000,&H90000000,1,8,230\n"
            "Style: End,Arial,84,&H00FFD98A,&H80000000,&H80000000,1,5,120\n\n"
            "[Events]\n"
            "Format: Layer, Start, End, Style, Text\n")
    evs = []
    if title:
        evs.append(_motion.dialogue(
            title[2], title[3], "Title",
            "{\\fad(200,200)}" + title[0] + "\\N" + title[1]))
    rep = confidence_report(words)
    karaoke = rep["mode"] == "word"
    for cue in chunk_words(words):
        evs.append(_motion.dialogue(
            cue[0]["start"], cue[-1]["end"], "Body",
            cue_text(cue, karaoke=karaoke), _motion.fade()))
    for s, e, txt in (keywords or []):
        evs.append(_motion.dialogue(s, e, "Key", txt, _motion.fade()))
    if endcard:
        evs.append(_motion.dialogue(
            endcard[2], endcard[3], "End",
            "{\\fad(200,400)}" + endcard[0] + "\\N" + endcard[1]))
    Path(dst).write_text(head + "\n".join(evs) + "\n", encoding="utf-8")
    return {"events": len(evs),
            "cues": sum(1 for _ in chunk_words(words)),
            "words": len(words), "karaoke": karaoke,
            "low_ratio": rep["low_ratio"]}
