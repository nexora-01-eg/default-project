"""Revenue intent engine (Phase 2): deterministic, evidence-backed, AR/EN + Arabizi.

Levels: high | medium | low | unknown | not_commercial.
NOT proof anyone will pay — every level carries OBSERVED evidence phrases.
Provenance: payment/hiring/business/tool-want/automation = OBSERVED (matched text);
overall level = INFERRED from evidence; absent data = UNKNOWN.
"""
import re

LEVELS = ("high", "medium", "low", "unknown", "not_commercial")

# Web Arabic usually drops hamzas (أ/إ/آ→ا) and mixes ة/ه, ى/ي. Normalize both text
# and patterns so "احتاج" matches "أحتاج" and "اداه" matches "أداة". Latin untouched.
_NORM_MAP = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ؤ": "و", "ئ": "ي",
                           "ة": "ه", "ى": "ي"})


def _arnorm(s):
    try:
        return s.translate(_NORM_MAP)
    except Exception:
        return s

# (kind, pattern) — keep patterns word-boundary aware where latin to avoid junk matches.
PAYMENT = [
    ("payment", r"willing to pay"), ("payment", r"how much (would|does|will)"),
    ("payment", r"\bbudget\b"), ("payment", r"\bprice\b"), ("payment", r"\bpaid\b"),
    ("payment", r"\bpay\b"), ("payment", r"\$\s?\d"), ("payment", r"per hour"),
    ("payment", r"hourly rate"), ("payment", "ادفع"), ("payment", "مستعد"),
    ("payment", "ميزانية"), ("payment", "بكام"), ("payment", "التكلفة"),
    ("payment", "تكلفة"), ("payment", "سعر"), ("payment", "مدفوع"),
    ("payment", "hedya"), ("payment", "bkam"), ("payment", "mekaneya"),
]
HIRING = [
    ("hiring", r"looking for a (developer|designer|freelancer|expert|consultant|team)"),
    ("hiring", r"need someone"), ("hiring", r"need a (developer|designer|freelancer)"),
    ("hiring", r"\bhiring\b"), ("hiring", r"\bhire\b"), ("hiring", r"freelancer"),
    ("hiring", r"can someone (build|create|make|develop|automate)"),
    ("hiring", "محتاج حد"), ("hiring", "عاوز حد"), ("hiring", "عايز حد"),
    ("hiring", "بدور على حد"), ("hiring", "مطلوب مطور"), ("hiring", "مطلوب مصمم"),
    ("hiring", "مطلوب حد"), ("hiring", "ممكن حد"), ("hiring", "حد يعمل"),
    ("hiring", "حد يعمللي"), ("hiring", "حد يساعد"), ("hiring", "عايز حد يعمللي بوت"),
    ("hiring", "3ayez 7ad"), ("hiring", "3ayza 7ad"), ("hiring", "mehtag 7ad"),
    ("hiring", "m7tag 7ad"), ("hiring", "bedawwar 3ala 7ad"),
]
BUSINESS = [
    ("business", r"our company"), ("business", r"we currently"),
    ("business", r"\bmanually\b"), ("business", r"takes? us .*hour"),
    ("business", r"\bclients?\b"), ("business", r"\bcustomers?\b"),
    ("business", r"\bbusiness\b"), ("business", r"\bteam\b.*\bneed"),
    ("business", "شركتي"), ("business", "شركتنا"), ("business", "الشغل"),
    ("business", "يدويا"), ("business", "يدوي"), ("business", "بنعمل"),
    ("business", "ساعات"), ("business", "التيم"), ("business", "عملاء"),
    ("business", "العملاء"), ("business", "sharika"), ("business", "shoghl"),
]
TOOL_WANT = [
    ("tool_want", r"is there (a|an) (tool|software|app|service)"),
    ("tool_want", r"looking for (a|an) (tool|software|app)"),
    ("tool_want", r"alternative to"), ("tool_want", r"i want a (tool|bot|system)"),
    ("tool_want", r"i need (a|this|this done)"), ("tool_want", r"need this done"),
    ("tool_want", "فيه برنامج"), ("tool_want", "فيه أداة"), ("tool_want", "في أداة"),
    ("tool_want", "حد يعرف أداة"), ("tool_want", "بدور على أداة"),
    ("tool_want", "عاوز برنامج"), ("tool_want", "عايز برنامج"),
    ("tool_want", "محتاج أداة"), ("tool_want", "عايز سيستم"), ("tool_want", "عاوز سيستم"),
    ("tool_want", "عاوز أعمل سيستم"), ("tool_want", "نفسي في برنامج"),
    ("tool_want", "fih program"), ("tool_want", "3ayez program"), ("tool_want", "3ayez system"),
]
AUTOMATION_NEED = [
    ("automation", r"\bautomate\b"), ("automation", r"\bautomation\b"),
    ("automation", r"\bintegrat"), ("automation", r"need .*automat"),
    ("automation", "أتمتة"), ("automation", "أتمت"), ("automation", "اربط"),
    ("automation", "ربط"), ("automation", "تكامل"), ("automation", "عاوز أتمتة"),
]
# Phase 3: granular Arabic buyer-evidence categories (phrases chosen disjoint
# from the tables above; classify() dedupes by phrase keeping the first kind).
SERVICE_REQUEST = [
    ("service_request", "عاوز شركه"), ("service_request", "عايز شركه"),
    ("service_request", "ادور على"), ("service_request", "أدور على"),
    ("service_request", "نبحث عن مستقل"), ("service_request", "ابحث عن مستقل"),
    ("service_request", "دور على حد"), ("service_request", "نبحث عن"),
    ("service_request", "looking for someone"),
]
TOOL_REQUEST = [
    ("tool_request", "محتاج اداه"), ("tool_request", "عاوز اداه"),
    ("tool_request", "بدور على اداه"), ("tool_request", "اداه تحول"),
    ("tool_request", "برنامج يحول"), ("tool_request", "تطبيق يعمل"),
    ("tool_request", "tool that"),
]
AUTOMATION_REQUEST = [
    ("automation_request", "عايز اتمته"), ("automation_request", "عاوز اتمته"),
    ("automation_request", "محتاج اتمته"), ("automation_request", "اتمته للشغل"),
    ("automation_request", "اوتوميشن"), ("automation_request", "نظام تلقائي"),
]
SOFTWARE_REQUEST = [
    ("software_request", "محتاج برنامج"), ("software_request", "عاوز برنامج"),
    ("software_request", "عايز برنامج"), ("software_request", "محتاج نظام"),
    ("software_request", "عاوز نظام"), ("software_request", "عايز نظام"),
    ("software_request", "ابغي برنامج"), ("software_request", "بدي برنامج"),
    ("software_request", "احتاج نظام"), ("software_request", "سيستم"),
    ("software_request", "ابليكيشن"), ("software_request", "انشاء نظام"),
    ("software_request", "إنشاء نظام"), ("software_request", "احتاج اصمم"),
]
PRICE_REQUEST = [
    ("price_request", "كام تكلفه"), ("price_request", "كم تكلفه"),
    ("price_request", "كم التكلفه"), ("price_request", "كم سعر"),
    ("price_request", "توضيح السعر"), ("price_request", "ادفع مقابل"),
    ("price_request", "الدفع مقابل"), ("price_request", "how much would you charge"),
    ("price_request", "what is your rate"), ("price_request", "quote for"),
]
IMPLEMENTATION_REQUEST = [
    ("implementation_request", "حد ينفذ"), ("implementation_request", "تنفيذ المشروع"),
    ("implementation_request", "يبني"), ("implementation_request", "تنفيذ الفكره"),
    ("implementation_request", "تنفيذ الفكرة"), ("implementation_request", "مين ينفذ"),
]
BUSINESS_PROBLEM = [
    ("business_problem", "بنعمل يدوي"), ("business_problem", "نعمل يدوي"),
    ("business_problem", "بياخد وقت"), ("business_problem", "ياخد وقت"),
    ("business_problem", "يضيع وقت"), ("business_problem", "تعبنا"),
    ("business_problem", "مجهود كبير"), ("business_problem", "مرهق"),
]
REPEATED_MANUAL_WORK = [
    ("repeated_manual_work", "كل يوم"), ("repeated_manual_work", "يوميا"),
    ("repeated_manual_work", "بشكل يدوي"), ("repeated_manual_work", "تكرار"),
    ("repeated_manual_work", "روتين"),
]
ALTERNATIVE_REQUEST = [
    ("alternative_request", "بديل ل"), ("alternative_request", "بديل عن"),
    ("alternative_request", "افضل من"), ("alternative_request", "احسن من"),
    ("alternative_request", "instead of"), ("alternative_request", "switch from"),
]
COMPLAINT_SOLUTION_INTENT = [
    ("complaint_with_solution_intent", "جربت"), ("complaint_with_solution_intent", "مش شغال"),
    ("complaint_with_solution_intent", "مش شغاله"), ("complaint_with_solution_intent", "بيعلق"),
    ("complaint_with_solution_intent", "زهقت من"), ("complaint_with_solution_intent", "فاشل"),
]
BUYER_TABLES = [SERVICE_REQUEST, TOOL_REQUEST, AUTOMATION_REQUEST, SOFTWARE_REQUEST,
                PRICE_REQUEST, IMPLEMENTATION_REQUEST, BUSINESS_PROBLEM,
                REPEATED_MANUAL_WORK, ALTERNATIVE_REQUEST, COMPLAINT_SOLUTION_INTENT]
NON_COMMERCIAL = [
    r"^show hn\b", r"\bannouncing\b", r"\breleased\b", r"\btutorial\b",
    r"\bguide to\b", r"\bhow i built\b", r"\bmy opinion\b", r"\bwhat do you think\b",
    r"\bvs\.?\b.*\bcomparison\b", r"^til\b", r"^today i learned\b",
    r"^خبر\b", r"^رأي\b", r"^شرح\b", r"وجهة نظر",
]

URGENT = ["عاجل", "ضروري", "urgent", "asap", "بسرعة", "دلوقتي", "اليوم", "deadline"]


def _hits(text, table):
    out = []
    t = _arnorm(text)
    for kind, pat in table:
        try:
            m = re.search(_arnorm(pat), t, re.IGNORECASE)
        except re.error:
            m = None
        if m:
            frag = m.group(0)
            # keep evidence short + readable
            out.append({"phrase": frag[:80], "kind": kind, "provenance": "OBSERVED"})
    return out


def classify_revenue(text):
    """Return dict: level, evidence[], payment_language, hiring_language,
    business_context, urgency, provenance(note). Never invents: no match -> unknown."""
    t = (text or "").strip()
    if len(t) < 4:
        return {"level": "unknown", "evidence": [], "payment_language": False,
                "hiring_language": False, "business_context": False, "urgency": "low",
                "provenance": "UNKNOWN: text too short"}
    pay = _hits(t, PAYMENT)
    hire = _hits(t, HIRING)
    biz = _hits(t, BUSINESS)
    tool = _hits(t, TOOL_WANT)
    auto = _hits(t, AUTOMATION_NEED)
    buyer = []
    for table in BUYER_TABLES:
        buyer += _hits(t, table)
    for w in URGENT:  # urgent words are themselves evidence (Phase 3)
        # ...except bare "اليوم" (today): far too common in benign/news text
        if w in t and w != "اليوم":
            buyer.append({"phrase": w[:80], "kind": "urgent_need", "provenance": "OBSERVED"})
    seen, evidence = set(), []
    for e in pay + hire + biz + tool + auto + buyer:  # dedupe by phrase
        if e["phrase"] not in seen:
            seen.add(e["phrase"])
            evidence.append(e)
    price = [e for e in evidence if e["kind"] == "price_request"]
    impl = [e for e in evidence if e["kind"] == "implementation_request"]
    cats = sorted({e["kind"] for e in evidence})
    urg = "high" if any(w in t for w in URGENT) else ("medium" if hire or pay else "low")
    flags = {"payment_language": bool(pay), "hiring_language": bool(hire),
             "business_context": bool(biz), "urgency": urg}
    if not evidence:
        nc = any(re.search(p, t, re.IGNORECASE) for p in NON_COMMERCIAL)
        if nc:
            return {"level": "not_commercial", "evidence": [], "categories": [], **flags,
                    "provenance": "INFERRED: non-commercial markers, no revenue signals"}
        return {"level": "unknown", "evidence": [], "categories": [], **flags,
                "provenance": "UNKNOWN: no revenue signals observed"}
    strong = bool(pay or (hire and (biz or urg == "high")) or (price and (hire or impl))
                  or (impl and biz))
    if strong:
        level = "high"
    elif hire or price or impl or (tool and (biz or auto)):
        level = "medium"
    elif tool or auto or biz:
        level = "medium" if (tool and auto) or (tool and biz) else "low"
    else:
        level = "low"
    return {"level": level, "evidence": evidence[:12], "categories": cats, **flags,
            "provenance": f"INFERRED from {len(evidence)} OBSERVED signal(s)"}


def level_score(level):
    return {"high": 1.0, "medium": 0.6, "low": 0.3, "unknown": 0.15,
            "not_commercial": 0.0}.get(level, 0.15)
