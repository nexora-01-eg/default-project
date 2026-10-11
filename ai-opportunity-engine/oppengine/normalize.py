"""Normalization + language detection (Arabic/English heuristic, no external deps).

Distinguishes explicit AI requests vs implicit opportunities vs non-AI — never forced.
"""
import html
import re
import unicodedata

AR_RE = re.compile(r"[\u0600-\u06FF]")
EG_MARKERS = ["عاوز", "عايز", "محتاج", "ازاي", "علشان", "كده", "دلوقتي", "نفسي", "فين",
              "اداة", "برنامج", "مصمم", "لوجو", "فيديو", "ترجمة", "دبلجة"]
AI_EXPLICIT = [r"\bAI\b", r"artificial intelligence", r"machine learning", r"\bLLM\b",
               "ذكاء اصطناعي", "ذكاء إصطناعي", "تعلم آلي", "تعلم عميق", "شات بوت",
               "روبوت محادثة", "gpt", "chatgpt", "كلود", "جيميناي"]
AI_TASK_HINTS = ["تحويل الكلام", "subtitles", "ترجمة", "تلخيص", "summar", "تصنيف",
                 "استخراج", "extract", "تعرف على", "recogn", "توليد", "generat",
                 "صور", "فيديو", "صوت", "نص", "ocr", "transcri", "تفريغ",
                 "قص", "مونتاج", "دبلجة", "تحسين", "automate", "أتمتة", "تلقائي"]
NON_AI_HINTS = ["محامي", "طبيب أسنان", "سباك", "كهربائي سيارات", "توصيل عفش",
                "زواج", "عزاء", "تبرع بالدم", "مفقود", "للبيع مستعمل"]
URL_RE = re.compile(r"https?://\S+|www\.\S+")
WS_RE = re.compile(r"\s+")


def detect_language(text):
    t = text or ""
    if not t.strip():
        return "unknown"
    ar_chars = len(AR_RE.findall(t))
    letters = [c for c in t if c.isalpha()]
    if not letters:
        return "unknown"
    return "ar" if ar_chars / max(len(letters), 1) > 0.25 else "en"


def normalize_text(text):
    if not isinstance(text, str):
        return ""
    t = re.sub(r"<[^>]{1,500}>", " ", text)  # strip HTML first (URLs inside tags)
    t = URL_RE.sub(" ", t)
    t = html.unescape(t)
    t = unicodedata.normalize("NFKC", t)
    t = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", " ", t)
    # strip diacritics/tatweel for Arabic matching, keep readable form
    t = re.sub(r"[\u064B-\u0652\u0640]", "", t)
    t = WS_RE.sub(" ", t).strip()
    return t[:2000]


def classify_request(text):
    """Return (request_type, ai_relevance, confidence, reason).

    request_type: explicit_ai | implicit_ai | automation | human_service | not_ai | unclear
    ai_relevance: high | medium | low | none
    """
    t = (text or "").strip()
    if len(t) < 4:
        return "unclear", "none", 0.9, "too short"
    low = t.lower()
    explicit = any(re.search(p, t, re.IGNORECASE) for p in AI_EXPLICIT)
    task_hits = sum(1 for h in AI_TASK_HINTS if h in t or h in low)
    non_ai = any(h in t for h in NON_AI_HINTS)
    words = len(t.split())
    if explicit and not non_ai:
        return "explicit_ai", "high", 0.85, "explicit AI mention"
    if non_ai and task_hits == 0:
        return "human_service" if words > 3 else "unclear", "none", 0.7, "physical/human-only service"
    if task_hits >= 2:
        return "implicit_ai", "high", 0.75, f"{task_hits} AI-task signals"
    if task_hits == 1:
        return "implicit_ai", "medium", 0.6, "single AI-task signal"
    if any(m in t for m in EG_MARKERS) and words >= 4:
        return "automation", "low", 0.45, "service request, automation possible"
    if words < 5:
        return "unclear", "none", 0.6, "insufficient information"
    return "human_service", "low", 0.5, "no AI signals"


def extract_fields(text, lang):
    """Lightweight deterministic extractor (LLM enriches later in ai_reasoning)."""
    t = normalize_text(text)
    urgency = "low"
    if any(w in t for w in ["عاجل", "ضروري", "urgent", "asap", "بسرعة", "دلوقتي", "اليوم"]):
        urgency = "high"
    elif any(w in t for w in ["محتاج", "عاوز", "عايز", "need", "looking for", "مطلوب"]):
        urgency = "medium"
    return {
        "normalized_text": t,
        "problem": t[:300],
        "desired_result": "",
        "requirements": [],
        "constraints": [],
        "urgency": urgency,
        "language": lang,
    }
