"""Arabic language engine (Phase 3): MSA + 6 dialects + Arabizi + mixed detection.

Multi-signal rule: a dialect wins only with >= 2 DISTINCT markers. A single shared
word (e.g. مش، يعني، ليش) never decides alone. No region/dialect cross-inference.
Returns dict {language, dialect, confidence, mixed, signals}.
"""
import re

AR_RE = re.compile(r"[\u0600-\u06FF]")
ARABIZI_DIGIT = re.compile(r"[a-zA-Z]*[2357][a-zA-Z]*")

NORM_MAP = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ؤ": "و", "ئ": "ي", "ة": "ه", "ى": "ي"})


def _norm(t):
    t = t.translate(NORM_MAP)
    t = re.sub(r"[\u064B-\u0652\u0640]", "", t)
    return t


def _boundary_pat(word):
    sep = r"(?:^|[\s\u060C\u061B\u061F.,;:!?()\[\]{}\"'«»#\-–—/])"
    end = r"(?:[\s\u060C\u061B\u061F.,;:!?()\[\]{}\"'«»#\-–—/]|$)"
    return sep + re.escape(word) + end


def _hits(text, markers):
    """Distinct markers present (boundary-safe)."""
    return {m for m in markers if re.search(_boundary_pat(m), text)}


EGYPTIAN = ["عاوز", "عايز", "عاوزين", "ازاي", "علشان", "عشان", "دلوقتي", "كده",
            "فين", "برضه", "برده", "كمان", "ايه", "خلاص", "نفسي", "بكام", "ده",
            "دي", "دول", "مش", "عشان", "يا جماعه", "محتاج"]
GULF = ["ابغي", "ابغى", "ابي", "وش", "شلون", "وايد", "الحين", "بغيت", "ترا",
        "ترى", "يا هلا", "وشلون", "حيل", "تدري", "ادور", "يبغي", "يبون", "نبي",
        "وشو", "كثر"]
LEVANTINE = ["بدي", "شو", "هلق", "هلا", "هيك", "كتير", "منيح", "ليش", "طيب",
             "شغله", "مشان", "بقدر", "فيني", "مافي", "يعطيك العافيه", "تكرم"]
MAGHREBI = ["بزاف", "بالزاف", "ديال", "كيدير", "لاباس", "بصح", "واش", "راني",
            "صافي", "مزيان", "دابا", "باش", "شكون", "علاش", "كيفاش"]
IRAQI = ["هسه", "اكو", "ماكو", "كلش", "شكو", "ليش", "شلون", "اريد", "شنو",
         "دز", "يمعود", "شكوا"]
SUDANESE = ["داير", "دايره", "زول", "زوله", "قروش", "شنو", "عايز", "يا زول",
            "تمام", "كيف"]
MSA_MARKERS = ["احتاج", "ابحث", "ارغب", "يرجي", "السلام عليكم", "تحيه طيبه",
               "اود", "نامل", "مطلوب", "نبحث", "نرغب", "يسعدنا", "نحن شركه"]

DIALECTS = [("egyptian", EGYPTIAN), ("gulf", GULF), ("levantine", LEVANTINE),
            ("iraqi", IRAQI), ("maghrebi", MAGHREBI), ("sudanese", SUDANESE)]

ARABIZI_WORDS = ["3ayez", "3yez", "3awz", "3ayza", "7ad", "m7tag", "mehtag",
                 "3shan", "3ashan", "3ala", "keda", "kedda", "ezay", "ezzay",
                 "leih", "leeh", "begad", "ya3ni", "y3ni", "mesh", "mish",
                 "msh", "ana", "enta", "enti", "eih", "da", "di", "dol", "el",
                 "bedawwar", "dawwar", "7aga", "kol", "zay", "fe", "ma",
                 "2al", "rayak", "3amel", "te3mel", "yenfa3", "momken"]


def analyze(text):
    """Return {language, dialect, confidence, mixed, signals}."""
    t = (text or "").strip()
    if len(t) < 2:
        return {"language": "unknown", "dialect": "unknown", "confidence": 0.0,
                "mixed": False, "signals": {}}
    n = _norm(t)
    ar_chars = len(AR_RE.findall(t))
    letters = [c for c in t if c.isalpha()]
    if not letters:
        return {"language": "unknown", "dialect": "unknown", "confidence": 0.0,
                "mixed": False, "signals": {}}
    ar_ratio = ar_chars / len(letters)
    latin_letters = [c for c in letters if ord(c) < 128]
    latin_ratio = len(latin_letters) / len(letters)

    # --- Arabizi: latin-script Arabic (needs digit signals +/or several known words)
    if ar_ratio < 0.15 and latin_ratio > 0.5:
        words = re.findall(r"[a-zA-Z0-9]+", t.lower())
        digit_words = {w for w in words if ARABIZI_DIGIT.fullmatch(w) and any(ch.isdigit() for ch in w)}
        word_hits = {w for w in words if w in ARABIZI_WORDS}
        if (digit_words and len(word_hits) >= 2) or len(word_hits) >= 3:
            return {"language": "ar", "dialect": "arabizi",
                    "confidence": 0.7 if len(word_hits) >= 3 else 0.55,
                    "mixed": latin_ratio < 0.95 and ar_ratio > 0.02,
                    "signals": {"arabizi_words": sorted(word_hits),
                                "digit_words": sorted(digit_words)}}
        return {"language": "en", "dialect": "unknown", "confidence": 0.6,
                "mixed": False, "signals": {}}

    if ar_ratio < 0.25:
        return {"language": "en", "dialect": "unknown", "confidence": 0.6,
                "mixed": False, "signals": {}}

    # --- Arabic: multi-signal dialect scoring
    mixed = latin_ratio > 0.15
    counts = {name: _hits(n, [ _norm(m) for m in markers]) for name, markers in DIALECTS}
    msa = _hits(n, [_norm(m) for m in MSA_MARKERS])
    ranked = sorted(counts.items(), key=lambda kv: len(kv[1]), reverse=True)
    best, best_hits = ranked[0]
    signals = {"markers": {k: sorted(v) for k, v in counts.items() if v}, "msa": sorted(msa)}
    if len(best_hits) >= 2:
        conf = min(0.6 + 0.1 * (len(best_hits) - 2), 0.9)
        if mixed:
            conf = max(conf - 0.1, 0.4)
        return {"language": "ar", "dialect": best, "confidence": round(conf, 2),
                "mixed": mixed, "signals": signals}
    if msa:
        return {"language": "ar", "dialect": "msa", "confidence": 0.65 if not mixed else 0.55,
                "mixed": mixed, "signals": signals}
    return {"language": "ar", "dialect": "msa", "confidence": 0.5 if not mixed else 0.4,
            "mixed": mixed, "signals": signals}
