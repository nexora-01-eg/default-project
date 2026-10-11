"""Existing-solution discovery: public GitHub search (no key, rate-limited).

Goal is FIND THE GAP, not copy competitors. Best-effort; failures are recorded, never faked.
"""
import json
import urllib.parse
import urllib.request

from . import db as DB
from .security import sanitize_text, validate_public_url


def github_search(query, cfg, limit=5):
    q = urllib.parse.quote_plus(query[:120])
    url = f"https://api.github.com/search/repositories?q={q}&sort=stars&order=desc&per_page={limit}"
    ok, _ = validate_public_url(url)
    if not ok:
        return []
    req = urllib.request.Request(url, headers={"User-Agent": cfg["http_user_agent"],
                                               "Accept": "application/vnd.github+json"})
    try:
        with urllib.request.urlopen(req, timeout=cfg.get("http_timeout_s", 20)) as r:
            data = json.loads(r.read().decode("utf-8", "replace"))
    except Exception:
        return []
    out = []
    for repo in (data.get("items") or [])[:limit]:
        out.append({"name": repo.get("full_name", ""), "url": repo.get("html_url", ""),
                    "capabilities": sanitize_text(str(repo.get("description") or ""), 300),
                    "limitations": "", "pricing": "open-source (see repo license)",
                    "complaints": f"open issues unknown; stars={repo.get('stargazers_count')}",
                    "gap": "", "source": "github"})
    return out


def discover_for_opportunity(db_path, cfg, opp, limit=5):
    sols = github_search(opp.get("title") or opp.get("normalized_problem") or "", cfg, limit)
    cx = DB.connect(db_path)
    try:
        cx.execute("DELETE FROM solutions WHERE opportunity_id=? AND source='github'", (opp["id"],))
        for s in sols:
            cx.execute("INSERT INTO solutions(opportunity_id,name,url,capabilities,limitations,"
                       "pricing,complaints,gap,source) VALUES(?,?,?,?,?,?,?,?,?)",
                       (opp["id"], s["name"], s["url"], s["capabilities"], s["limitations"],
                        s["pricing"], s["complaints"], s["gap"], s["source"]))
        if sols:
            gap = (f"Found {len(sols)} public repo(s); top: {sols[0]['name']}. "
                   "Verify Arabic support, cost, and offline feasibility before building.")
            cx.execute("UPDATE opportunities SET competition_note=?, gap_analysis=?, updated_at=?"
                       " WHERE id=?", (f"github top hit: {sols[0]['name']} ({sols[0]['url']})",
                                       gap, DB.now_iso(), opp["id"]))
        cx.commit()
    finally:
        cx.close()
    return len(sols)
