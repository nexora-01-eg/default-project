"""Phase 5/6 — filler-word annotation (identify only, never delete).

Language-aware, extensible: FILLER_WORDS maps ISO-639-1 codes to filler sets.
Matching is case-insensitive with surrounding punctuation stripped.
Deletion/removal belongs to Phase 8+; this module only annotates.
"""
from __future__ import annotations

import string

FILLER_WORDS: dict[str, frozenset[str]] = {
    "en": frozenset({
        "um", "uh", "er", "ah", "hmm", "hm", "like", "you-know", "y'know",
        "i-mean", "well", "so", "actually", "basically", "literally",
        "right", "okay", "huh",
    }),
    "ar": frozenset({
        "يعني", "اه", "امم", "مم", "ايه", "طيب", "كده", "زي", "والله",
        "بصراحة", "تقريبا",
    }),
}

_STRIP = string.punctuation + "،؛؟«»…—–'\""


def normalize_token(token: str) -> str:
    return token.strip().strip(_STRIP).lower()


def filler_set(language: str) -> frozenset[str]:
    """Return the filler set for a language code ('' prefix-matched, else empty)."""
    lang = (language or "").lower().split("-")[0]
    return FILLER_WORDS.get(lang, frozenset())


def annotate_fillers(segments: list[dict], language: str) -> list[dict]:
    """Annotate likely filler words. Returns [{word,start,end,segment_id}].

    segments: [{id, words:[{word,start,end,...}]}]. Unknown language -> [].
    """
    fillers = filler_set(language)
    if not fillers:
        return []
    out: list[dict] = []
    for seg in segments:
        for w in seg.get("words", []):
            if normalize_token(str(w.get("word", ""))) in fillers:
                out.append({"word": w.get("word"), "start": w.get("start"),
                            "end": w.get("end"), "segment_id": seg.get("id")})
    return out
