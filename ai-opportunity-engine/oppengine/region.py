"""Geographic signals (Phase 3): EXPLICIT mentions only. Never infer from dialect.

Returns {region, evidence, confidence}. Bare 'عمان' is ambiguous (Oman/Jordan) and
resolves only with disambiguating context, else Unknown.
"""
import re

NORM_MAP = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ؤ": "و", "ئ": "ي", "ة": "ه", "ى": "ي"})


def _norm(t):
    t = t.translate(NORM_MAP)
    t = re.sub(r"[\u064B-\u0652\u0640]", "", t)
    return t


# Arabic punctuation (، ؛ ؟) lives inside U+0600–U+06FF, so \w-boundaries fail.
# Use an explicit separator set instead.
SEP = r"(?:^|[\s\u060C\u061B\u061F.,;:!?()\[\]{}\"'«»#\-–—/])"
SEP_END = r"(?:[\s\u060C\u061B\u061F.,;:!?()\[\]{}\"'«»#\-–—/]|$)"


def _bp(word):
    return SEP + re.escape(word) + SEP_END


# region -> [(variant, weight)] ; city-level variants weigh more for display only.
GAZETTEER = {
    "Egypt": [("مصر", 2), ("القاهره", 3), ("الجيزه", 3), ("الاسكندريه", 3),
              ("اسكندريه", 3), ("المنصوره", 3), ("الصعيد", 2), ("طنطا", 3),
              ("اسيوط", 3), ("egypt", 2), ("cairo", 3), ("alexandria", 3),
              ("مصري", 1), ("مصريه", 1)],
    "Saudi Arabia": [("السعوديه", 2), ("المملكه العربيه السعوديه", 3), ("الرياض", 3),
                     ("جده", 3), ("الدمام", 3), ("مكه", 3), ("المدينه", 3),
                     ("الخبر", 3), ("ابها", 3), ("saudi", 2), ("riyadh", 3),
                     ("jeddah", 3), ("سعودي", 1), ("سعوديه", 1)],
    "UAE": [("الامارات", 2), ("دبي", 3), ("ابوظبي", 3), ("ابو ظبي", 3),
            ("الشارقه", 3), ("عجمان", 3), ("uae", 2), ("dubai", 3),
            ("abu dhabi", 3), ("اماراتي", 1)],
    "Qatar": [("قطر", 2), ("الدوحه", 3), ("qatar", 2), ("doha", 3), ("قطري", 1)],
    "Kuwait": [("الكويت", 2), ("kuwait", 2), ("كويتي", 1)],
    "Bahrain": [("البحرين", 2), ("المنامه", 3), ("bahrain", 2), ("بحريني", 1)],
    "Oman": [("مسقط", 3), ("صلاله", 3), ("سلطنه عمان", 3), ("muscat", 3),
             ("oman", 2), ("عماني", 1)],
    "Jordan": [("الاردن", 2), ("الزرقاء", 3), ("اربد", 3), ("jordan", 2),
               ("amman", 3), ("اردني", 1)],
    "Lebanon": [("لبنان", 2), ("بيروت", 3), ("lebanon", 2), ("beirut", 3),
                ("لبناني", 1)],
    "Iraq": [("العراق", 2), ("بغداد", 3), ("البصره", 3), ("اربيل", 3),
             ("iraq", 2), ("baghdad", 3), ("عراقي", 1)],
    "Palestine": [("فلسطين", 2), ("غزه", 3), ("القدس", 3), ("رام الله", 3),
                  ("palestine", 2), ("gaza", 3), ("فلسطيني", 1)],
    "Syria": [("سوريا", 2), ("سوريه", 2), ("دمشق", 3), ("حلب", 3),
              ("syria", 2), ("damascus", 3), ("سوري", 1)],
    "Morocco": [("المغرب", 2), ("الدار البيضاء", 3), ("الرباط", 3), ("مراكش", 3),
                ("morocco", 2), ("casablanca", 3), ("مغربي", 1)],
    "Algeria": [("الجزائر", 2), ("وهران", 3), ("algeria", 2), ("جزائري", 1)],
    "Tunisia": [("تونس", 2), ("صفاقس", 3), ("tunisia", 2), ("tunis", 3),
                ("تونسي", 1)],
    "Libya": [("ليبيا", 2), ("طرابلس", 3), ("بنغازي", 3), ("libya", 2),
              ("ليبي", 1)],
    "Sudan": [("السودان", 2), ("الخرطوم", 3), ("sudan", 2), ("khartoum", 3),
              ("سوداني", 1)],
    "Yemen": [("اليمن", 2), ("صنعاء", 3), ("عدن", 3), ("yemen", 2), ("يمني", 1)],
}

# pre-normalize variants once
GAZ = {r: [(_norm(v), w) for v, w in vs] for r, vs in GAZETTEER.items()}

AMBIGUOUS_OMAN = _norm("عمان")
JORDAN_CTX = [_norm(x) for x in ("الاردن", "اردني", "الزرقاء", "اربد")]
OMAN_CTX = [_norm(x) for x in ("مسقط", "صلاله", "سلطنه", "عماني")]


def detect_region(text):
    """Return {region, evidence, confidence(high|medium|unknown)}."""
    from .domains import ar_stems, tokenize_ar
    t = _norm(text or "")
    if not t.strip():
        return {"region": "Unknown", "evidence": "", "confidence": "unknown"}
    stems = set()
    for tok in tokenize_ar(text):
        stems.update(ar_stems(tok))
    stems_l = {s.lower() for s in stems}
    hits = []  # (region, variant_raw, weight, pos)
    for region, variants in GAZ.items():
        for v, w in variants:
            if " " in v.strip():
                m = re.search(_bp(v), t, re.IGNORECASE)
                pos = m.start() if m else -1
            else:
                pos = -1
                if v.lower() in stems_l:
                    try:
                        pos = t.lower().index(v.lower())
                    except ValueError:
                        pos = 0
            if pos >= 0:
                hits.append((region, v, w, pos))
    # bare عمان disambiguation
    m = re.search(_bp(AMBIGUOUS_OMAN), t)
    if m:
        has_j = any(re.search(_bp(x), t) for x in JORDAN_CTX)
        has_o = any(re.search(_bp(x), t) for x in OMAN_CTX)
        if has_j and not has_o:
            hits.append(("Jordan", "عمان+الاردن-سياق", 2, m.start()))
        elif has_o and not has_j:
            hits.append(("Oman", "عمان+سلطنه-سياق", 2, m.start()))
        else:
            return {"region": "Unknown", "evidence": "عمان (ambiguous: Oman/Jordan)",
                    "confidence": "unknown"}
    if not hits:
        return {"region": "Unknown", "evidence": "", "confidence": "unknown"}
    regions = sorted({h[0] for h in hits})
    best = max(hits, key=lambda h: (h[2], -h[3]))
    ev = best[1]
    if len(regions) > 1:
        return {"region": best[0], "evidence": f"{ev} (+{','.join(r for r in regions if r != best[0])})",
                "confidence": "medium"}
    conf = "high" if best[2] >= 2 else "medium"
    return {"region": best[0], "evidence": ev, "confidence": conf}
