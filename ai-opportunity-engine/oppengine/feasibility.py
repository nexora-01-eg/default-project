"""Local feasibility engine — grounded in the Phase 0 audit. No invented capability."""
import json
import re

from . import db as DB

# Verified local capabilities (LOCAL_ENVIRONMENT_AUDIT.md). capability -> evidence.
LOCAL_CAPS = {
    "stt": "faster-whisper CPU/int8 know-how + FFmpeg 9.0.1 (sibling project verified)",
    "ffmpeg": "FFmpeg 9.0.1 full build installed (h264_qsv verified on this box)",
    "llm_reason": "Qwen2.5-Coder-7B loaded in LM Studio :1234 (verified)",
    "embeddings": "nomic-embed-text-v1.5 loaded in LM Studio :1234 (verified)",
    "opencv": "OpenCV available in project .venv (verified)",
    "python": "Python 3.11.9 (verified)",
    "sqlite": "SQLite 3.45.1 stdlib (verified)",
    "node": "Node 24 (verified, for future tool UIs)",
    "docker": "Docker 29.8 client (verified)",
}
NOT_AVAILABLE = ["plausible-deniability browser automation", "tesseract OCR", "playwright/selenium",
                 "postgres/redis/elastic", "ollama", "paid APIs"]

NEED_HINTS = {
    "stt": ["subtitles", "ترجمة", "تفريغ", "transcri", "صوت", "فيديو", "دبلجة", "speech"],
    "ffmpeg": ["فيديو", "video", "قص", "مونتاج", "reels", "shorts", "تحويل صيغة"],
    "llm_reason": ["تلخيص", "summar", "تصنيف", "chatbot", "شات بوت", "ردود", "محتوى", "كتابة"],
    "embeddings": ["بحث", "search", "تشابه", "توصية", "recommend"],
    "opencv": ["صور", "image", "وجوه", "face", "object"],
}


def assess(title, problem):
    blob = f"{title or ''} {problem or ''}".lower()

    def hit(hint):
        # word-boundary match: avoids "face" matching "surfaces"
        return re.search(r"(?<!\w)" + re.escape(hint.lower()) + r"(?!\w)", blob) is not None

    matched = [cap for cap, hints in NEED_HINTS.items() if any(hit(h) for h in hints)]
    if not matched:
        return "Medium", "No special local dependency detected; Python+LLM baseline applies."
    missing_media = ("stt" in matched or "ffmpeg" in matched)
    level = "High" if all(c in LOCAL_CAPS for c in matched) else "Medium"
    why = "Matched needs: " + ", ".join(f"{c} ({LOCAL_CAPS[c]})" for c in matched)
    if missing_media:
        why += ". Note: heavy 4K/long-form media work is slow on 4C CPU + 2GB VRAM — chunk it."
    return level, why


def refresh(db_path):
    cx = DB.connect(db_path)
    try:
        opps = [dict(r) for r in cx.execute("SELECT * FROM opportunities")]
    finally:
        cx.close()
    for o in opps:
        level, why = assess(o.get("title"), o.get("normalized_problem"))
        cx = DB.connect(db_path)
        try:
            cx.execute("UPDATE opportunities SET local_feasibility=?, local_why=?, updated_at=? WHERE id=?",
                       (level, why, DB.now_iso(), o["id"]))
            cx.commit()
        finally:
            cx.close()
    return len(opps)
