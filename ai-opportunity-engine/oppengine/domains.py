"""Problem-domain classification + cross-domain guard (Phase 3.5).

A high embedding similarity is NEVER sufficient alone: two rows group only if their
canonical signatures are compatible — overlapping/compatible domains, same request-type
family, plus embedding similarity. Language-independent: an Arabic and an English
request about translation share the `translation` tag regardless of script.
"""
import re

NORM_MAP = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ؤ": "و", "ئ": "ي",
                           "ة": "ه", "ى": "ي"})

SEP = r"(?:^|[\s\u060C\u061B\u061F.,;:!?()\[\]{}\"'«»#\-–—/])"
SEP_END = r"(?:[\s\u060C\u061B\u061F.,;:!?()\[\]{}\"'«»#\-–—/]|$)"


def _norm(t):
    t = (t or "").translate(NORM_MAP)
    t = re.sub(r"[\u064B-\u0652\u0640]", "", t)
    return t


TOKEN_SEP = r"[\s\u060C\u061B\u061F.,;:!?()\[\]{}\"'«»#\-–—/]+"

_PREFIXES = ("وال", "بال", "كال", "فال", "لل", "ال")
_SUFFIXES = ("هما", "ات", "ون", "ين", "ان", "ها", "هم", "هن", "كم", "كن", "نا", "ه")


def ar_stems(token):
    """Light Arabic stem variants for matching (definite article + common suffixes).

    Chained to a fixpoint (الفيديوهات -> فيديوهات -> فيديوه -> فيديو).
    Conservative: strips apply only if the remainder keeps length >= 4 (suffix)
    or >= 3 (article), so short words like ده/دي never degrade."""
    out = {token}
    changed = True
    while changed:
        changed = False
        for base in list(out):
            for pre in _PREFIXES:
                if base.startswith(pre) and len(base) - len(pre) >= 3:
                    cand = base[len(pre):]
                    if cand not in out:
                        out.add(cand)
                        changed = True
                    break
            for suf in _SUFFIXES:
                if base.endswith(suf) and len(base) - len(suf) >= 4:
                    cand = base[: -len(suf)]
                    if cand not in out:
                        out.add(cand)
                        changed = True
    return out


def tokenize_ar(text):
    return [w for w in re.split(TOKEN_SEP, _norm(text or "")) if w]


def _hit(text, word):
    return re.search(SEP + re.escape(_norm(word)) + SEP_END, text,
                     re.IGNORECASE) is not None


DOMAINS = {
    "translation": ["ترجمه", "ترجمة", "translate", "translation", "مترجم", "translator",
                    "دبلجه", "دبلجة", "dubbing", "subtitles", "ترجمه فوريه"],
    "design": ["تصميم", "design", "مصمم", "designer", "شعار", "logo", "هويه",
               "هوية", "جرافيك", "graphic", "فوتوشوب", "photoshop", "canva",
               "كتالوج", "بوستر", "موشن"],
    "video": ["فيديو", "video", "مونتاج", "montage", "ريلز", "reels", "shorts",
              "شورتس", "يوتيوب", "youtube", "تصوير", "موشن جرافيك"],
    "software_dev": ["برمجه", "برمجة", "programming", "code", "كود", "مطور",
                     "developer", "مبرمج", "تطبيق", "app", "موقع", "website",
                     "بوت", "bot", "ووردبريس", "wordpress", "api", "سيستم",
                     "نظام", "سكربت", "script", "github", "ابل", "ios", "اندرويد",
                     "برنامج", "software", "سوفتوير"],
    "ai_ml": ["ذكاء اصطناعي", "ذكاء إصطناعي", "ai agent", "machine learning",
              "تعلم اله", "deep learning", "نموذج لغوي", "llm", "chatgpt",
              "روبوت محادثه", "شات بوت ذكي", "computer vision", "رؤيه حاسوبيه"],
    "data": ["داتا بيس", "database", "قاعده بيانات", "اكسيل", "excel",
             "تحليل بيانات", "data analysis", "ادخال بيانات", "سكرابينج",
             "scraping"],
    "marketing": ["تسويق", "marketing", "اعلان", "ads", "seo", "سوشيال ميديا",
                  "social media", "حمله اعلانيه", "متابعين", "followers"],
    "writing": ["كتابه", "writing", "مقال", "article", "كتاب", "book",
                "copywriting", "محتوي كتابي", "تدقيق لغوي"],
    "support_ops": ["دعم فني", "support", "خدمه عملاء", "رد علي العملاء",
                    "call center", "سكرتاريه", "مساعد افتراضي"],
    "code_review": ["bounty", "مكافاه", "code review", "مراجعه كود", "pull request",
                    "good first issue", "onboard"],
    "religious_content": ["الحرم", "المنقطعين", "رحاب", "ديني", "مواسم دينيه",
                          "فتوي", "خطبه", "quran", "islamic"],
    "general_discussion": ["رايكم", "نقاش", "discussion", "what do you think",
                           "لماذا"],
}

# compatible pairs (symmetric): subtitles live in translation+video, etc.
COMPAT = {
    "translation": {"translation", "video"},
    "writing": {"writing", "translation"},
    "video": {"video", "design", "translation"},
    "design": {"design", "video"},
    "software_dev": {"software_dev", "ai_ml", "data"},
    "ai_ml": {"ai_ml", "software_dev", "data"},
    "data": {"data", "software_dev", "ai_ml", "support_ops"},
    "marketing": {"marketing", "design", "video"},
    "support_ops": {"support_ops", "data"},
    "code_review": {"code_review", "software_dev"},
    "religious_content": {"religious_content"},
    "general_discussion": {"general_discussion"},
}

# PRIMARY domains define the problem (decisive). SECONDARY domains are contextual:
# they may SUPPORT a match but never DECIDE one (a shared incidental word like
# "book"/"ads" must not group a catalog-design request with a book translation).
PRIMARY = {"translation", "design", "video", "software_dev", "ai_ml", "data"}

# tech/product entities: shared entities support a match; absence is neutral.
ENTITIES = ["python", "javascript", "discord", "wordpress", "excel", "photoshop",
            "figma", "api", "whatsapp", "telegram", "mysql", "react", "flutter",
            "odoo", "sap", "shopify", "salla", "zid", "mada", "tabby", "tamara",
            "hyperpay", "moyasar", "paytabs", "stripe"]


def classify_domain(text):
    """Return (set(domains), set(entities)). Empty set = no domain signals.

    Arabic single-token markers match against morphological stems
    (الفيديوهات -> فيديو, مصممين -> مصمم); multi-word/phrase markers use
    boundary-safe substring search; Latin matched case-insensitively."""
    t = _norm(text or "")
    stems = set()
    for tok in tokenize_ar(text):
        stems.update(ar_stems(tok))
    doms = set()
    for d, words in DOMAINS.items():
        for w in words:
            nw = _norm(w)
            if " " in nw.strip():
                if re.search(SEP + re.escape(nw.strip()) + SEP_END, t, re.IGNORECASE):
                    doms.add(d)
                    break
            elif re.search(r"[a-zA-Z]", nw):
                if nw.lower() in {s.lower() for s in stems} or \
                        re.search(SEP + re.escape(nw) + SEP_END, t, re.IGNORECASE):
                    doms.add(d)
                    break
            elif nw in stems:
                doms.add(d)
                break
    low = t.lower()
    ents = {e.strip() for e in ENTITIES if e.strip() and e.strip() in low}
    return doms, ents


AI_FAMILY = {"explicit_ai", "implicit_ai", "automation"}
HUMAN_FAMILY = {"human_service", "unclear", "not_ai"}


def _family(rtype):
    if rtype in AI_FAMILY:
        return "ai"
    if rtype in HUMAN_FAMILY:
        return "human"
    return "other"


def pair_guard(a_text, a_type, b_text, b_type, high_bar=0.85, sim=None):
    """Cross-domain guard for one pair. Returns {verdict, reasons[]}.

    verdict: pass | flagged | unknown-domain.
    - PRIMARY domains decide: overlap/compat -> pass; disjoint primaries -> flagged
    - one side primary-less but both sides signalling and disagreeing -> flagged
    - linked-only or silent sides -> unknown-domain (caller: require sim >= high_bar)
    - request-type families differ (ai vs human) -> flagged
    - shared entities recorded as supporting evidence (neutral when absent)
    """
    da, ea = classify_domain(a_text)
    db, eb = classify_domain(b_text)
    reasons, flags = [], []
    shared_ents = sorted(ea & eb)
    if shared_ents:
        reasons.append(f"shared entities: {','.join(shared_ents)}")
    fa, fb = _family(a_type or ""), _family(b_type or "")
    if fa != fb and fa != "other" and fb != "other":
        flags.append(f"request-type family mismatch: {a_type} vs {b_type}")
    pa, pb = da & PRIMARY, db & PRIMARY
    if pa and pb:
        if pa & pb:
            reasons.append(f"primary domain overlap: {sorted(pa & pb)}")
        else:
            compat = any((db2 in COMPAT.get(da1, set())) for da1 in pa for db2 in pb)
            if compat:
                reasons.append(f"compatible primary domains: {sorted(pa)} ~ {sorted(pb)}")
            else:
                flags.append(f"cross-domain: {sorted(pa)} vs {sorted(pb)} (embedding alone insufficient)")
    else:
        if da and db:
            linked = bool(da & db) or any(
                (y in COMPAT.get(x, set())) or (x in COMPAT.get(y, set()))
                for x in da for y in db)
            if linked:
                reasons.append(f"secondary-only link {sorted(da)} ~ {sorted(db)}: "
                               f"embedding must clear {high_bar}")
            else:
                flags.append(f"cross-domain (secondary signals disagree): {sorted(da)} vs "
                             f"{sorted(db)} (embedding alone insufficient)")
        else:
            missing = []
            if not da:
                missing.append("A")
            if not db:
                missing.append("B")
            reasons.append(f"no decisive domain signals on {','.join(missing)}: "
                           f"embedding must clear {high_bar}")
    if flags:
        return {"verdict": "flagged", "reasons": reasons + flags,
                "domains_a": sorted(da), "domains_b": sorted(db),
                "entities": shared_ents}
    if not pa or not pb:
        return {"verdict": "unknown-domain", "reasons": reasons,
                "domains_a": sorted(da), "domains_b": sorted(db),
                "entities": shared_ents}
    return {"verdict": "pass", "reasons": reasons,
            "domains_a": sorted(da), "domains_b": sorted(db),
            "entities": shared_ents}
