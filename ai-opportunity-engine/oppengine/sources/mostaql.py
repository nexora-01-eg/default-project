"""Mostaql: Arabic freelance marketplace, open projects (public, no login).

LIVE basis: listing https://mostaql.com/projects is publicly fetchable; robots.txt
disallows only /search* and /ajax/ (checked 2026-09-23); project pages expose title,
description, budget, publish time, owner publicly. Polite: 2s between detail pages,
<=10 details per run, 2h interval. Skips non-open projects.
"""
import json
import re
import time

from .base import SourceAdapter

LIST_URL = "https://mostaql.com/projects"
LINK_RE = re.compile(r'href="(https://mostaql\.com/project/[^"]+)"')
LD_RE = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.S)
BUDGET_RE = re.compile(r"project-budget_range[^>]*>\s*<span[^>]*>(.*?)</span>", re.S)
TIME_RE = re.compile(r'<time datetime="([^"]+)"')
STATUS_RE = re.compile(r"حالة المشروع</div>\s*<div[^>]*>(.*?)</div>", re.S)


def _strip(html):
    t = re.sub(r"<script.*?</script>", " ", html, flags=re.S)
    t = re.sub(r"<style.*?</style>", " ", t, flags=re.S)
    t = re.sub(r"<[^>]+>", "\n", t)
    import html as _h
    return [l.strip() for l in (_h.unescape(t)).split("\n") if l.strip()]


def parse_listing(html):
    seen, out = set(), []
    for m in LINK_RE.finditer(html):
        u = m.group(1)
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


def parse_detail(html, url):
    """Return item dict or None (skip: closed/unparseable). All fields observed."""
    status_m = STATUS_RE.search(html)
    status = re.sub(r"<[^>]+>", "", status_m.group(1)).strip() if status_m else ""
    if status and "مفتوح" not in status:
        return None  # awarded/closed: not actionable demand
    title, posted = "", None
    ld = LD_RE.search(html)
    if ld:
        try:
            data = json.loads(ld.group(1))
            title = (data.get("title") or "").strip()
            posted = data.get("datePosted")
        except Exception:
            pass
    if not title:
        m = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.S)
        title = re.sub(r"<[^>]+>", "", m.group(1)).strip()[:160] if m else ""
    lines = _strip(html)
    desc, author, skills = "", "", []
    try:
        i = lines.index("تفاصيل المشروع")
        j = next((k for k in range(i + 1, len(lines))
                  if lines[k] in ("تقدم للمشروع", "حالة المشروع", "صاحب المشروع")), len(lines))
        desc = "\n".join(lines[i + 1:j]).strip()[:1500]
    except ValueError:
        pass
    try:
        i = lines.index("صاحب المشروع")
        author = lines[i + 1] if i + 1 < len(lines) else ""
    except ValueError:
        pass
    try:
        i = lines.index("المهارات")
        j = lines.index("صاحب المشروع")
        skills = [l for l in lines[i + 1:j] if len(l) < 60][:8]
    except ValueError:
        pass
    budget = ""
    bm = BUDGET_RE.search(html)
    if bm:
        budget = re.sub(r"<[^>]+>", "", bm.group(1)).strip()
    tm = TIME_RE.search(html)
    published = tm.group(1).replace(" ", "T", 1) if tm else posted
    text = f"{title}\n{desc}".strip()
    if len(text) < 20:
        return None
    mid = re.search(r"/project/(\d+)", url)
    return {"source_url": url, "external_id": f"mostaql-{mid.group(1)}" if mid else None,
            "original_text": text[:2000], "published_at": published,
            "author": author[:120] or None, "author_url": None,
            "raw_meta": {"budget": budget, "skills": skills, "status": status or "unknown"}}


class MostaqlAdapter(SourceAdapter):
    name = "mostaql"
    kind = "marketplace"
    interval_s = 7200
    languages = ["ar"]
    source_type = "marketplace"
    timeout_s = 25
    max_details = 10
    QUALIFY = {"url": LIST_URL, "language": "ar", "category": "freelance marketplace",
               "public_access": "yes, no login for listing+project pages",
               "authentication_required": False, "technical_access": "plain HTTPS HTML",
               "terms_risk": "low: robots.txt allows /projects and /project/* (only /search*, /ajax/ disallowed)",
               "expected_signal_quality": "high: priced buyer requests with budgets",
               "polling_interval": 7200}

    def collect(self):
        listing = self.fetch_text(LIST_URL)
        urls = parse_listing(listing)[: self.max_details]
        if not urls:
            raise RuntimeError("mostaql listing returned zero project links")
        out = []
        for u in urls:
            try:
                item = parse_detail(self.fetch_text(u), u)
            except Exception:
                item = None
            if item:
                out.append(item)
            time.sleep(2)  # politeness between detail pages
            if len(out) >= self.cfg.get("max_collect_per_source", 40):
                break
        return out
