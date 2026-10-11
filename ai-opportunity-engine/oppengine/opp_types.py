"""Opportunity type tags (Phase 2): practical monetization-oriented taxonomy.

Multiple tags allowed. not_suitable only when the request is not an AI/automation problem.
"""
import re

TAXONOMY = ["AI automation", "AI content", "AI video", "AI audio", "AI transcription",
            "AI translation", "AI document processing", "AI customer support",
            "AI lead processing", "AI research", "AI data extraction",
            "AI developer tooling", "AI workflow", "AI integration",
            "AI local business solution", "AI productivity", "custom AI software",
            "non-AI automation", "not suitable"]

RULES = [
    ("AI video", ["فيديو", "video", "reels", "shorts", "مونتاج", "subtitles", "ترجمة فيديو"]),
    ("AI transcription", ["transcri", "تفريغ", "تحويل الكلام", "speech-to-text", "subtitles"]),
    ("AI translation", ["ترجمة", "translat", "دبلجة", "dub"]),
    ("AI audio", ["صوت", "audio", "voice", "بودكاست", "tts", "تعليق صوتي"]),
    ("AI document processing", ["مستند", "document", "pdf", "فاتورة", "invoice", "ocr", "استخراج بيانات"]),
    ("AI data extraction", ["استخراج", "extract", "scrap", "كشط", "تجميع بيانات"]),
    ("AI customer support", ["ردود", "chatbot", "شات بوت", "بوت", "دعم العملاء", "support", "whatsapp", "واتساب"]),
    ("AI lead processing", ["lead", "عملاء محتملين", "مبيعات", "crm"]),
    ("AI content", ["محتوى", "content", "مقالات", "كتابة", "copywriting", "سوشيال"]),
    ("AI developer tooling", ["كود", "code", "api", "developer", "مطور", "github", "ci", "review"]),
    ("AI research", ["بحث", "research", "تلخيص", "summar", "تحليل"]),
    ("AI workflow", ["workflow", "سير عمل", "أتمتة", "automate", "pipeline"]),
    ("AI integration", ["ربط", "integrat", "تكامل", "اربط", "api", "webhook", "zapier", "n8n"]),
    ("AI productivity", ["إنتاجية", "productivity", "تنظيم", "جدولة", "schedule", "تذكير"]),
    ("AI local business solution", ["محل", "مطعم", "عيادة", "مكتب", "شركة", "store", "restaurant", "clinic"]),
]


def tag(text, ai_feasibility="", ai_relevance=""):
    t = (text or "").lower()
    tags = [name for name, hints in RULES
            if any(h in t for h in hints)]
    if ai_feasibility in ("not_ai",) or ai_relevance == "none":
        return ["not suitable"]
    if not tags:
        tags = ["custom AI software"] if ai_relevance in ("high", "medium") else ["not suitable"]
    # collapse transcription under video when both fire on video+subtitle jobs? keep both: multi-tag allowed
    return sorted(set(tags))


def valid(tags):
    return [x for x in (tags or []) if x in TAXONOMY]
