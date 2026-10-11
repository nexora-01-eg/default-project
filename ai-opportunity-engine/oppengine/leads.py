"""Lead intelligence (Phase 2): preserve ONLY publicly exposed contact info.

Allowed: public_username, public_profile_url, public post URL, website/email/social
links that appear verbatim in the request text or author fields.
FORBIDDEN: phones, addresses, national IDs, inferred identity, private enrichment.
"""
import re

from . import db as DB
from .security import sanitize_text

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
URL_RE = re.compile(r"https?://[^\s'\"<>]+")
PHONE_RE = re.compile(r"(\+?\d[\d\s\-()]{7,}\d)")  # detected -> REDACTED, never stored

SOCIAL_DOMAINS = ("github.com", "linkedin.com", "x.com", "twitter.com", "facebook.com",
                  "instagram.com", "t.me", "telegram.me", "wa.me", "youtube.com",
                  "behance.net", "dribbble.com", "upwork.com", "freelancer.com",
                  "mostaql.com", "khamsat.com", "nafezly.com")


def extract_lead(raw):
    """raw: raw_requests row dict. Returns lead dict (nothing stored here)."""
    text = raw.get("original_text") or ""
    username = (raw.get("author") or "").strip()[:120] or None
    profile = (raw.get("author_url") or "").strip()[:500] or None
    emails = [e[:120] for e in dict.fromkeys(EMAIL_RE.findall(text))][:3]
    urls = [u[:300] for u in dict.fromkeys(URL_RE.findall(text))][:5]
    # drop the post's own source_url from website candidates
    src = (raw.get("source_url") or "")
    websites = [u for u in urls if u != src and not any(
        d in u for d in ("news.ycombinator.com", "reddit.com", "github.com",
                         "stackoverflow.com", "stackexchange.com", "api.stackexchange.com"))]
    social = [u for u in urls if any(d in u for d in SOCIAL_DOMAINS)]
    has_phone = bool(PHONE_RE.search(text))  # noted, never stored
    score_parts, reasons = [], []
    if profile:
        score_parts.append(2)
        reasons.append("OBSERVED public profile URL")
    elif username:
        score_parts.append(1)
        reasons.append("OBSERVED public username only")
    if emails:
        score_parts.append(2)
        reasons.append("OBSERVED email verbatim in request text")
    if websites:
        score_parts.append(1)
        reasons.append("OBSERVED website verbatim in request text")
    if social:
        score_parts.append(1)
        reasons.append("OBSERVED social link verbatim in request text")
    score = sum(score_parts)
    contactability = ("high" if score >= 4 else "medium" if score >= 2 else
                      "low" if score >= 1 else "none")
    return {"request_id": raw.get("id"), "public_username": username,
            "public_profile_url": profile, "public_email": emails[0] if emails else None,
            "public_website": websites[0] if websites else None,
            "public_social_links": social[:3], "source_url": src,
            "contactability": contactability,
            "contactability_reason": "; ".join(reasons) if reasons else "UNKNOWN: no public contact observed",
            "phone_redacted": has_phone}


def store_lead(db_path, lead, opportunity_id=None):
    import json
    cx = DB.connect(db_path)
    try:
        cx.execute("INSERT INTO leads(request_id,opportunity_id,public_username,public_profile_url,"
                   "public_email,public_website,public_social_links,source_url,contactability,"
                   "contactability_reason,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?) "
                   "ON CONFLICT(request_id) DO UPDATE SET opportunity_id=excluded.opportunity_id",
                   (lead["request_id"], opportunity_id, lead.get("public_username"),
                    lead.get("public_profile_url"), lead.get("public_email"),
                    lead.get("public_website"),
                    json.dumps(lead.get("public_social_links") or [], ensure_ascii=False),
                    lead.get("source_url"), lead.get("contactability"),
                    lead.get("contactability_reason"), DB.now_iso()))
        cx.commit()
    finally:
        cx.close()


def refresh_for_opportunity(db_path, opp_id):
    cx = DB.connect(db_path)
    try:
        raws = [dict(r) for r in cx.execute(
            "SELECT r.* FROM opportunity_members m JOIN normalized n ON n.id=m.normalized_id "
            "JOIN raw_requests r ON r.id=n.raw_id WHERE m.opportunity_id=?", (opp_id,))]
    finally:
        cx.close()
    return [store_lead(db_path, extract_lead(r), opp_id) or extract_lead(r) for r in raws]


def contact_brief(db_path, opp_id, lang="en"):
    """DRAFT-ONLY contact brief. Never sends anything."""
    import json
    cx = DB.connect(db_path)
    try:
        o = cx.execute("SELECT * FROM opportunities WHERE id=?", (opp_id,)).fetchone()
        if not o:
            return None
        o = dict(o)
        members = [dict(r) for r in cx.execute(
            "SELECT r.author, r.author_url, r.source_url, r.source, n.problem FROM opportunity_members m "
            "JOIN normalized n ON n.id=m.normalized_id JOIN raw_requests r ON r.id=n.raw_id "
            "WHERE m.opportunity_id=? LIMIT 5", (opp_id,))]
        leads = [dict(r) for r in cx.execute(
            "SELECT * FROM leads WHERE opportunity_id=? ORDER BY contactability DESC LIMIT 5", (opp_id,))]
    finally:
        cx.close()
    ev = {}
    try:
        ev = json.loads(o.get("evidence") or "{}")
    except Exception:
        pass
    best = leads[0] if leads else {}
    lines = [
        "CONTACT BRIEF — DRAFT ONLY. Do NOT send automatically. Manual outreach only.",
        f"Problem: {sanitize_text(o.get('normalized_problem') or o.get('title') or '', 300)}",
        f"Why this may help: {len(members)} public request(s) observed; "
        f"AI feasibility={o.get('ai_feasibility')}; local={o.get('local_feasibility')}.",
        f"What could be offered: {(o.get('suggested_solution') or 'custom AI/automation service (see gap analysis)')[:300]}",
        "Evidence: " + "; ".join(
            f"{m.get('source')}: {(m.get('problem') or '')[:90]}" for m in members[:3]),
        f"Public profile: {best.get('public_profile_url') or best.get('public_username') or 'UNKNOWN'}",
        f"Public contact: {best.get('public_email') or best.get('public_website') or 'UNKNOWN (no public contact observed)'}",
    ]
    if lang.startswith("ar"):
        draft = ("مرحباً، لاحظت طلبك العام بخصوص: "
                 f"{sanitize_text(o.get('normalized_problem') or '', 160)} "
                 "أعمل على حلول أتمتة/ذكاء اصطناعي مخصصة وقد أستطيع المساعدة. "
                 "هل تود مناقشة التفاصيل؟ (مسودة فقط)")
    else:
        draft = ("Hi — I saw your public request about: "
                 f"{sanitize_text(o.get('normalized_problem') or '', 160)} "
                 "I build small custom AI/automation solutions and might be able to help. "
                 "Open to a quick chat about details? (draft only)")
    lines.append(f"Suggested first message (DRAFT): {draft}")
    lines.append(f"Source links: " + ", ".join(m.get("source_url") or "" for m in members[:3]))
    return "\n\n".join(lines)
