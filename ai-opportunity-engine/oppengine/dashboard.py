"""Dashboard: stdlib http.server, server-rendered HTML. AR/EN, RTL/LTR, dark/light.

Routes: / (opportunities) /feed /opp?id= /sources /search /analytics
        /feedback (POST) /spec?id= (opportunity_spec.json) /api/stats /health
"""
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

from . import db as DB
from . import pipeline as PIPE
from .security import esc

STR = {
    "title": {"en": "AI Opportunity Engine", "ar": "محرك فرص الذكاء الاصطناعي"},
    "opps": {"en": "Opportunities", "ar": "الفرص"},
    "feed": {"en": "Live Feed", "ar": "التدفق المباشر"},
    "sources": {"en": "Sources", "ar": "المصادر"},
    "search": {"en": "Search", "ar": "البحث"},
    "analytics": {"en": "Analytics", "ar": "التحليلات"},
    "requests": {"en": "requests", "ar": "طلبات"},
    "score": {"en": "score", "ar": "النقاط"},
    "feas": {"en": "AI feasibility", "ar": "جدوى الذكاء الاصطناعي"},
    "local": {"en": "Local feasibility", "ar": "الجدوى المحلية"},
    "evidence": {"en": "Evidence", "ar": "الأدلة"},
    "solutions": {"en": "Existing solutions & gaps", "ar": "الحلول الموجودة والفجوات"},
    "actions": {"en": "Your decision", "ar": "قرارك"},
    "empty": {"en": "No data yet — run a collection cycle.", "ar": "لا توجد بيانات بعد — شغّل دورة جمع."},
    "revenue": {"en": "Revenue Opportunities", "ar": "فرص الإيرادات"},
    "signals": {"en": "Revenue Signals", "ar": "إشارات الشراء"},
    "leads": {"en": "Leads", "ar": "العملاء المحتملون"},
    "demand": {"en": "Demand", "ar": "الطلب"},
    "brief": {"en": "Contact Brief (draft — manual only)", "ar": "موجز التواصل (مسودة — يدوي فقط)"},
    "rev_intent": {"en": "revenue intent", "ar": "نية الشراء"},
    "arabic": {"en": "Arabic Demand", "ar": "الطلب العربي"},
    "ar_sources": {"en": "Arabic Sources", "ar": "المصادر العربية"},
    "dialect": {"en": "dialect", "ar": "اللهجة"},
    "region": {"en": "region", "ar": "المنطقة"},
    "buyer": {"en": "Buyer Signals", "ar": "إشارات المشترين"},
    "single_obs": {"en": "SINGLE_OBSERVATION — not a validated market", "ar": "ملاحظة وحيدة — ليست سوقاً مؤكدة"},
    "firstmoney": {"en": "FIRST-MONEY candidates", "ar": "مرشحو أول دخل"},
}

CSS = ("body{font-family:Segoe UI,Tahoma,Arial,sans-serif;margin:0;background:var(--bg);color:var(--fg)}"
       ":root{--bg:#0f1420;--fg:#e8ecf4;--card:#1a2233;--line:#2b3answer}"
       "body.light{--bg:#f6f7fb;--fg:#141a26;--card:#fff;--line:#dfe5ef}"
       "header{padding:14px 20px;border-bottom:1px solid var(--line);display:flex;gap:12px;flex-wrap:wrap;align-items:center}"
       "nav a{margin:0 8px;color:var(--fg);text-decoration:none;border:1px solid var(--line);padding:4px 10px;border-radius:8px}"
       ".wrap{padding:18px;max-width:1100px;margin:auto}"
       ".card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px;margin:10px 0}"
       ".muted{opacity:.75;font-size:.9em}.pill{display:inline-block;padding:2px 10px;border-radius:20px;border:1px solid var(--line);margin:2px}"
       "a{color:#6ea8fe}table{border-collapse:collapse;width:100%}td,th{border:1px solid var(--line);padding:6px 8px;text-align:start}"
       "button{padding:6px 12px;margin:2px;border-radius:8px;border:1px solid var(--line);cursor:pointer}"
       "input,select{background:var(--card);color:var(--fg);border:1px solid var(--line);border-radius:8px;padding:6px 10px}")


def _lang(qs):
    l = (qs.get("lang", ["ar"])[0] or "ar").lower()
    return "ar" if l.startswith("ar") else "en"


def _theme(qs):
    t = (qs.get("theme", ["dark"])[0] or "dark").lower()
    return "light" if t.startswith("light") else "dark"


def _keep(qs, **ov):
    cur = {"lang": _lang(qs), "theme": _theme(qs)}
    cur.update(ov)
    return "lang=" + cur["lang"] + "&theme=" + cur["theme"]


def page(lang, theme, body, active=""):
    rtl = lang == "ar"
    t = STR["title"][lang]
    nav = "".join(f'<a href="/{p}?{_keep_qs(lang, theme)}">{STR[n][lang]}</a>'
                   for p, n in [("", "opps"), ("revenue", "revenue"), ("first-money", "firstmoney"),
                                ("arabic", "arabic"), ("feed", "feed"),
                                ("leads", "leads"), ("demand", "demand"),
                                ("sources", "sources"), ("search", "search"),
                                ("analytics", "analytics")])
    other = "en" if lang == "ar" else "ar"
    otheme = "light" if theme == "dark" else "dark"
    return ("<!DOCTYPE html><html lang='%s' dir='%s'><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            "<title>%s</title><style>%s</style></head>"
            "<body class='%s'><header><b>%s</b><nav>%s</nav>"
            "<span style='margin-inline-start:auto'><a href='?lang=%s&theme=%s'>%s</a> "
            "<a href='?lang=%s&theme=%s'>%s mode</a></span></header>"
            "<div class='wrap'>%s</div></body></html>"
            % (lang, "rtl" if rtl else "ltr", esc(t), CSS.replace("--line:#2b3answer", "--line:#2b3652"),
               "" if theme == "dark" else "light", esc(t), nav, other, theme,
               "EN" if lang == "ar" else "عربي", lang, otheme, otheme, body))


def _keep_qs(lang, theme):
    return f"lang={lang}&theme={theme}"


def _q(cx, sql, args=()):
    return [dict(r) for r in cx.execute(sql, args)]


class Handler(BaseHTTPRequestHandler):
    db_path = "data/oppengine.db"
    server_version = "OppEngine/0.1"

    def log_message(self, *a):
        pass

    def _send(self, body, ctype="text/html; charset=utf-8", code=200):
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        u = urlparse(self.path)
        qs = parse_qs(u.query)
        lang, theme = _lang(qs), _theme(qs)
        try:
            if u.path in ("/", "/opportunities"):
                return self._send(page(lang, theme, self.v_opps(qs, lang, theme)))
            if u.path == "/revenue":
                return self._send(page(lang, theme, self.v_revenue(qs, lang, theme)))
            if u.path == "/first-money":
                return self._send(page(lang, theme, self.v_firstmoney(qs, lang, theme)))
            if u.path == "/arabic":
                return self._send(page(lang, theme, self.v_arabic(qs, lang, theme)))
            if u.path == "/arabic-sources":
                return self._send(page(lang, theme, self.v_arabic_sources(lang, theme)))
            if u.path == "/revenue-signals":
                return self._send(page(lang, theme, self.v_signals(qs, lang, theme)))
            if u.path == "/leads":
                return self._send(page(lang, theme, self.v_leads(qs, lang, theme)))
            if u.path == "/demand":
                return self._send(page(lang, theme, self.v_demand(qs, lang, theme)))
            if u.path == "/brief":
                return self._send(page(lang, theme, self.v_brief(qs, lang, theme)))
            if u.path == "/feed":
                return self._send(page(lang, theme, self.v_feed(qs, lang, theme)))
            if u.path == "/opp":
                return self._send(page(lang, theme, self.v_opp(qs, lang, theme)))
            if u.path == "/sources":
                return self._send(page(lang, theme, self.v_sources(lang, theme)))
            if u.path == "/search":
                return self._send(page(lang, theme, self.v_search(qs, lang, theme)))
            if u.path == "/analytics":
                return self._send(page(lang, theme, self.v_analytics(lang, theme)))
            if u.path == "/spec":
                return self.spec(qs)
            if u.path == "/api/stats":
                return self._send(json.dumps(DB.stats(self.db_path), ensure_ascii=False),
                                   "application/json")
            if u.path == "/health":
                return self._send(json.dumps({"ok": True, "stats": DB.stats(self.db_path)}),
                                   "application/json")
            return self._send("not found", code=404)
        except Exception as exc:
            return self._send(page(lang, theme, f"<div class='card'>Error: {esc(str(exc)[:300])}</div>"))

    def do_POST(self):
        u = urlparse(self.path)
        if u.path == "/feedback":
            n = int(self.headers.get("Content-Length", 0) or 0)
            form = parse_qs(self.rfile.read(min(n, 8192)).decode("utf-8", "replace"))
            try:
                oid = int(form.get("opportunity_id", ["0"])[0])
            except ValueError:
                oid = 0
            dec = (form.get("decision", [""])[0] or "")[:20]
            reason = (form.get("reason", [""])[0] or "")[:500]
            if oid and dec in ("interesting", "ignore", "already_solved", "too_difficult",
                               "investigate", "build", "archive", "contact_manually"):
                cx = DB.connect(self.db_path)
                try:
                    cx.execute("INSERT INTO feedback(opportunity_id,decision,reason,created_at)"
                               " VALUES(?,?,?,?)", (oid, dec, reason, DB.now_iso()))
                    if dec in ("ignore", "archive", "already_solved", "too_difficult"):
                        st = "archived" if dec == "archive" else "rejected"
                        cx.execute("UPDATE opportunities SET status=?, updated_at=? WHERE id=?",
                                   (st, DB.now_iso(), oid))
                    cx.commit()
                finally:
                    cx.close()
            self.send_response(303)
            lang = form.get("lang", ["ar"])[0]
            theme = form.get("theme", ["dark"])[0]
            self.send_header("Location", f"/opp?id={oid}&lang={lang}&theme={theme}")
            self.end_headers()
            return
        return self._send("not found", code=404)

    # -- views ----------------------------------------------------------
    def v_opps(self, qs, lang, theme):
        cx = DB.connect(self.db_path)
        try:
            rows = _q(cx, "SELECT * FROM opportunities WHERE status NOT IN ('archived','rejected')"
                           " ORDER BY score DESC, updated_at DESC LIMIT 100")
        finally:
            cx.close()
        if not rows:
            return f"<div class='card'>{esc(STR['empty'][lang])}</div>"
        cards = []
        for o in rows:
            so = (f" · ⚠ {esc(STR['single_obs'][lang])}"
                  if (o.get("demand_strength") or "") == "single_observation" else "")
            cards.append(
                f"<div class='card'><a href='/opp?id={o['id']}&{_keep(qs)}'><b>{esc(o['title'] or '')}</b></a>"
                f"<div class='muted'>{esc(o['category'] or '')} · {o['request_count']} {esc(STR['requests'][lang])} · "
                f"{esc(STR['score'][lang])}: {o['score']:.2f}{so}</div>"
                f"<div><span class='pill'>{esc(o['ai_feasibility'] or '')}</span>"
                f"<span class='pill'>{esc(STR['local'][lang])}: {esc(o['local_feasibility'] or '?')}</span>"
                f"<span class='pill'>{esc(o['status'] or '')}</span></div>"
                f"<div class='muted'>{esc((o.get('gap_analysis') or '')[:220])}</div></div>")
        return "".join(cards)

    def v_feed(self, qs, lang, theme):
        cx = DB.connect(self.db_path)
        try:
            rows = _q(cx, "SELECT r.*, n.request_type, n.ai_relevance, n.confidence FROM raw_requests r "
                           "LEFT JOIN normalized n ON n.raw_id=r.id ORDER BY r.id DESC LIMIT 100")
        finally:
            cx.close()
        if not rows:
            return f"<div class='card'>{esc(STR['empty'][lang])}</div>"
        out = []
        for r in rows:
            out.append(f"<div class='card'><div class='muted'>{esc(r['source'] or '')} · "
                       f"{esc(r['collected_at'] or '')} · {esc(r['language'] or '')} · "
                       f"{esc(r.get('request_type') or '')}/{esc(r.get('ai_relevance') or '')}</div>"
                       f"<div>{esc(r['original_text'] or '')}</div>"
                       f"<div class='muted'><a href='{esc(r['source_url'] or '')}'>source ↗</a>"
                       f"{' · @' + esc(r['author']) if r.get('author') else ''}</div></div>")
        return "".join(out)

    def v_opp(self, qs, lang, theme):
        try:
            oid = int(qs.get("id", ["0"])[0])
        except ValueError:
            oid = 0
        cx = DB.connect(self.db_path)
        try:
            o = cx.execute("SELECT * FROM opportunities WHERE id=?", (oid,)).fetchone()
            if not o:
                return "<div class='card'>not found</div>"
            o = dict(o)
            members = _q(cx, "SELECT n.*, r.source, r.source_url, r.author, r.author_url, r.collected_at,"
                             " r.original_text FROM opportunity_members m JOIN normalized n ON n.id=m.normalized_id "
                             "JOIN raw_requests r ON r.id=n.raw_id WHERE m.opportunity_id=? ORDER BY r.id DESC", (oid,))
            sols = _q(cx, "SELECT * FROM solutions WHERE opportunity_id=?", (oid,))
            fb = _q(cx, "SELECT * FROM feedback WHERE opportunity_id=? ORDER BY id DESC", (oid,))
        finally:
            cx.close()
        ev = {}
        try:
            ev = json.loads(o.get("evidence") or "{}")
        except Exception:
            pass
        h = [f"<div class='card'><h2>{esc(o['title'] or '')}</h2>"
             f"<div class='muted'>{esc(o['category'] or '')} · {o['request_count']} {esc(STR['requests'][lang])} · "
             f"{esc(STR['score'][lang])} {o['score']:.2f} · conf {o.get('confidence')}"
             + (f" · ⚠ {esc(STR['single_obs'][lang])}"
                if (o.get('demand_strength') or "") == "single_observation" else "")
             + "</div>"
             f"<p><b>{esc(STR['feas'][lang])}:</b> {esc(o.get('ai_feasibility') or '')}<br>"
             f"<b>{esc(STR['local'][lang])}:</b> {esc(o.get('local_feasibility') or '')} — {esc(o.get('local_why') or '')}</p>"
             f"<p><b>GAP:</b> {esc(o.get('gap_analysis') or '')}</p>"
             f"<p><b>Suggested:</b> {esc(o.get('suggested_solution') or '')}</p>"
             f"<p class='muted'>Scoring: {esc(json.dumps(ev.get('scoring', {}), ensure_ascii=False))}</p>"
             f"<p><a href='/spec?id={oid}'>opportunity_spec.json ↗</a></p></div>"]
        # -- Phase 2 evidence sections (A-O) ---------------------------------
        cx2 = DB.connect(self.db_path)
        try:
            dem = cx2.execute("SELECT * FROM demand_signals WHERE opportunity_id=?",
                              (oid,)).fetchone()
            dem = dict(dem) if dem else {}
            revs = _q(cx2, "SELECT rs.*, r.source, r.source_url FROM revenue_signals rs "
                            "JOIN normalized n ON n.raw_id=rs.request_id "
                            "JOIN raw_requests r ON r.id=rs.request_id "
                            "JOIN opportunity_members m ON m.normalized_id=n.id "
                            "WHERE m.opportunity_id=? LIMIT 20", (oid,))
            lds = _q(cx2, "SELECT * FROM leads WHERE opportunity_id=? ORDER BY "
                           "CASE contactability WHEN 'high' THEN 0 WHEN 'medium' THEN 1 "
                           "WHEN 'low' THEN 2 ELSE 3 END LIMIT 10", (oid,))
            ca = cx2.execute("SELECT * FROM commercial_analysis WHERE opportunity_id=?",
                             (oid,)).fetchone()
            ca = dict(ca) if ca else {}
        finally:
            cx2.close()
        import json as _j2
        try:
            dsum = _j2.loads(dem.get("evidence_summary") or "{}")
        except Exception:
            dsum = {}
        h.append(f"<div class='card'><b>C. Demand evidence:</b> "
                 f"{esc(dsum.get('demand_evidence', 'single_observation'))} · "
                 f"indep {dem.get('independent_request_count', 0)} · "
                 f"sources {dem.get('unique_source_count', 0)} · authors {dem.get('unique_author_count', 0)} · "
                 f"growth48h {dem.get('growth_rate', 0)} · first {esc((dem.get('first_seen') or '')[:10])} · "
                 f"last {esc((dem.get('last_seen') or '')[:10])} "
                 f"<span class='muted'>({esc(dsum.get('provenance', ''))})</span></div>")
        rev_rows = []
        for r in revs:
            try:
                _evs = json.loads(r.get("evidence") or "[]")
            except Exception:
                _evs = []
            _ph = "; ".join(f"{e.get('kind')}: {e.get('phrase')}" for e in _evs[:3])
            rev_rows.append(
                f"<div class='muted'>{esc(r.get('source') or '')} · {esc(r.get('level') or '')} · "
                f"{esc(_ph)} · <a href='{esc(r.get('source_url') or '')}'>source ↗</a></div>")
        h.append(f"<div class='card'><b>D. Revenue signals ({esc(o.get('revenue_intent') or 'unknown')}):</b> "
                 + ("".join(rev_rows) or "<span class='muted'>none observed — UNKNOWN</span>") + "</div>")
        h.append(f"<div class='card'><b>E. Public leads:</b> "
                 + ("".join(
                     f"<div class='muted'>@{esc(l.get('public_username') or '?')} · "
                     f"{esc(l.get('contactability') or '')} · "
                     f"{esc(l.get('public_email') or l.get('public_website') or 'no public contact')} · "
                     f"{esc(l.get('contactability_reason') or '')}</div>" for l in lds)
                    or "<span class='muted'>none — no public contact observed</span>")
                 + f"<div><a href='/brief?id={oid}&{_keep(qs)}'>contact brief (draft) ↗</a> · "
                   f"<a href='/leads?{_keep(qs)}'>all leads ↗</a></div></div>")
        try:
            _prov = _j2.loads(ca.get("provenance") or "{}")
        except Exception:
            _prov = {}
        h.append(f"<div class='card'><b>F–M. Commercial analysis:</b> "
                 f"demand={esc(ca.get('demand_strength') or '')} · urgency={esc(ca.get('urgency') or '')} · "
                 f"buyer={esc(ca.get('buyer_context') or '')} · competition={esc(ca.get('competition_level') or '')} · "
                 f"gap={esc(ca.get('solution_gap') or '')} · build={esc(ca.get('local_buildability') or '')} · "
                 f"complexity={esc(o.get('complexity') or ca.get('estimated_complexity') or '')} · "
                 f"confidence={ca.get('evidence_confidence', '')}"
                 f"<div class='muted'>types: {esc(', '.join(_j2.loads(o.get('opp_types') or '[]')))}</div>"
                 f"<div class='muted'>service formats: {esc(', '.join(i.get('format', '') for i in (_j2.loads(o.get('service_ideas') or '[]'))))} "
                 f"(pricing UNKNOWN unless source-backed)</div></div>")
        h.append(f"<h3>{esc(STR['evidence'][lang])}</h3>")
        for m in members:
            contact = ""
            if m.get("author"):
                contact += f" · @{esc(m['author'])}"
                if m.get("author_url"):
                    contact += f" (<a href='{esc(m['author_url'])}'>profile ↗</a>)"
            h.append(f"<div class='card'><div class='muted'>{esc(m.get('source') or '')} · "
                     f"{esc(m.get('collected_at') or '')}{contact}</div>"
                     f"<div>{esc(m.get('original_text') or '')}</div>"
                     f"<div class='muted'>{esc(m.get('reasoning') or '')} · conf {m.get('confidence')}"
                     + (f" · {esc(STR['dialect'][lang])}: {esc(m.get('dialect') or '')}" if m.get("dialect") else "")
                     + (f" · {esc(STR['region'][lang])}: {esc(m.get('explicit_region') or '')}" if m.get("explicit_region") else "")
                     + "</div>"
                     f"<div><a href='{esc(m.get('source_url') or '')}'>source ↗</a></div></div>")
        h.append(f"<h3>{esc(STR['solutions'][lang])}</h3>")
        if not sols:
            h.append("<div class='card muted'>none found yet</div>")
        for s in sols:
            h.append(f"<div class='card'><b>{esc(s['name'] or '')}</b> — <a href='{esc(s['url'] or '')}'>link ↗</a>"
                     f"<div>{esc(s['capabilities'] or '')}</div>"
                     f"<div class='muted'>{esc(s['pricing'] or '')} · {esc(s['complaints'] or '')}</div></div>")
        opts = "".join(f"<option value='{d}'>{d}</option>" for d in
                       ["interesting", "investigate", "build", "contact_manually",
                        "already_solved", "too_difficult", "ignore", "archive"])
        h.append(f"<div class='card'><h3>{esc(STR['actions'][lang])}</h3>"
                 f"<form method='POST' action='/feedback'><input type='hidden' name='opportunity_id' value='{oid}'>"
                 f"<input type='hidden' name='lang' value='{lang}'><input type='hidden' name='theme' value='{theme}'>"
                 f"<select name='decision'>{opts}</select> "
                 f"<input name='reason' placeholder='reason…' size='40'> "
                 f"<button type='submit'>OK</button></form>")
        for f in fb:
            h.append(f"<div class='muted'>{esc(f['created_at'] or '')} — {esc(f['decision'])}: {esc(f['reason'] or '')}</div>")
        h.append("</div>")
        return "".join(h)

    def v_sources(self, lang, theme):
        cx = DB.connect(self.db_path)
        try:
            rows = _q(cx, "SELECT * FROM sources ORDER BY name")
            counts = {r["source"]: r["c"] for r in
                      _q(cx, "SELECT source, COUNT(*) c FROM raw_requests GROUP BY source")}
        finally:
            cx.close()
        h = ["<table><tr><th>source</th><th>kind</th><th>status</th><th>collected</th>"
             "<th>last success</th><th>errors</th><th>note</th></tr>"]
        for s in rows:
            meta = {}
            try:
                meta = json.loads(s.get("meta") or "{}")
            except Exception:
                pass
            h.append(f"<tr><td>{esc(s['name'])}</td><td>{esc(s['kind'])}</td><td>{esc(s['status'])}</td>"
                     f"<td>{counts.get(s['name'], 0)}</td><td>{esc(s.get('last_success') or '—')}</td>"
                     f"<td>{s.get('consecutive_errors', 0)}</td><td class='muted'>{esc(meta.get('reason', ''))}</td></tr>")
        return "".join(h) + "</table>"

    def v_search(self, qs, lang, theme):
        q = (qs.get("q", [""])[0] or "")[:200]
        box = (f"<div class='card'><form method='GET' action='/search'>"
               f"<input name='q' value='{esc(q)}' size='40' placeholder='…'>"
               f"<input type='hidden' name='lang' value='{lang}'>"
               f"<input type='hidden' name='theme' value='{theme}'>"
               f"<button type='submit'>{esc(STR['search'][lang])}</button></form></div>")
        if not q:
            return box
        cx = DB.connect(self.db_path)
        try:
            like = f"%{q}%"
            raws = _q(cx, "SELECT * FROM raw_requests WHERE original_text LIKE ? ORDER BY id DESC LIMIT 50", (like,))
            opps = _q(cx, "SELECT * FROM opportunities WHERE title LIKE ? OR normalized_problem LIKE ?"
                           " ORDER BY score DESC LIMIT 20", (like, like))
        finally:
            cx.close()
        h = [box, f"<h3>opportunities ({len(opps)})</h3>"]
        for o in opps:
            h.append(f"<div class='card'><a href='/opp?id={o['id']}&{_keep(qs)}'><b>{esc(o['title'] or '')}</b></a>"
                     f" <span class='muted'>{o['score']:.2f}</span></div>")
        h.append(f"<h3>requests ({len(raws)})</h3>")
        for r in raws:
            h.append(f"<div class='card'><div class='muted'>{esc(r['source'] or '')}</div>"
                     f"<div>{esc((r['original_text'] or '')[:400])}</div></div>")
        return "".join(h)

    def v_analytics(self, lang, theme):
        s = DB.stats(self.db_path)
        cx = DB.connect(self.db_path)
        try:
            runs = _q(cx, "SELECT * FROM runs ORDER BY id DESC LIMIT 10")
            def _one(sql, args=()):
                try:
                    return cx.execute(sql, args).fetchone()[0]
                except Exception:
                    return 0
            signals_hi = _one("SELECT COUNT(*) FROM revenue_signals WHERE level IN ('high','medium')")
            ar_opps = _one("SELECT COUNT(DISTINCT m.opportunity_id) FROM opportunity_members m "
                           "JOIN normalized n ON n.id=m.normalized_id JOIN raw_requests r ON r.id=n.raw_id "
                           "WHERE r.language='ar'")
            contactable = _one("SELECT COUNT(*) FROM leads WHERE contactability IN ('high','medium')")
            strong_local = _one("SELECT COUNT(*) FROM opportunities WHERE local_feasibility='High'"
                                " AND status NOT IN ('archived','rejected')")
            with_gaps = _one("SELECT COUNT(*) FROM opportunities WHERE gap_analysis IS NOT NULL"
                             " AND gap_analysis != '' AND status NOT IN ('archived','rejected')")
            llm = cx.execute("SELECT COALESCE(SUM(attempts),0) a, COALESCE(SUM(successes),0) s,"
                             " COALESCE(SUM(failures),0) f, COALESCE(SUM(latency_ms),0) ms,"
                             " COALESCE(SUM(tokens),0) t FROM llm_usage").fetchone()
            llm = dict(llm) if llm else {}
            unhealthy = _q(cx, "SELECT name, rate_limit_state, consecutive_errors, last_error FROM sources "
                               "WHERE consecutive_errors > 0 OR rate_limit_state != ''")
        finally:
            cx.close()
        h = [f"<div class='card'><b>raw:</b> {s['raw_requests']} · <b>analyzed:</b> {s['normalized']} · "
             f"<b>opportunities:</b> {s['opportunities']} · <b>feedback:</b> {s['feedback']}</div>",
             f"<div class='card'><b>Revenue widgets (commercial signals, not guarantees):</b><br>"
             f"fresh med/high signals: <b>{signals_hi}</b> · Arabic opportunities: <b>{ar_opps}</b> · "
             f"contactable leads: <b>{contactable}</b> · strong local feasibility: <b>{strong_local}</b> · "
             f"with solution gaps: <b>{with_gaps}</b></div>",
             f"<div class='card'><b>LLM budget:</b> attempts {llm.get('a', 0)} · successes {llm.get('s', 0)} · "
             f"failures {llm.get('f', 0)} · latency {llm.get('ms', 0)}ms · tokens {llm.get('t', 0)} "
             f"(0 = not reported by server → UNKNOWN)</div>"]
        if unhealthy:
            h.append("<div class='card'><b>Sources needing attention</b><table>"
                     "<tr><th>source</th><th>state</th><th>errors</th><th>last error</th></tr>"
                     + "".join(f"<tr><td>{esc(u['name'])}</td><td>{esc(u['rate_limit_state'] or '')}</td>"
                               f"<td>{u['consecutive_errors']}</td>"
                               f"<td class='muted'>{esc((u['last_error'] or '')[:100])}</td></tr>"
                               for u in unhealthy) + "</table></div>")
        for title, rows, k in [("by source", s["by_source"], "source"), ("by language", s["by_lang"], "language"),
                               ("by category", s["by_category"], "category")]:
            h.append(f"<div class='card'><b>{esc(title)}</b><table>")
            for r in rows:
                h.append(f"<tr><td>{esc(str(r.get(k if k in r else list(r.keys())[0])) )}</td><td>{r['c']}</td></tr>")
            h.append("</table></div>")
        h.append("<div class='card'><b>recent cycles</b><table><tr><th>source</th><th>collected</th>"
                 "<th>analyzed</th><th>new opps</th><th>duration</th><th>error</th></tr>")
        for r in runs:
            h.append(f"<tr><td>{esc(r['source'] or '')}</td><td>{r['collected']}</td><td>{r['analyzed']}</td>"
                     f"<td>{r['opportunities_new']}</td><td>{r['duration_s']}s</td>"
                     f"<td class='muted'>{esc((r['error'] or '')[:80])}</td></tr>")
        return "".join(h) + "</table></div>"

    # -- Phase 2 views ----------------------------------------------------
    def v_revenue(self, qs, lang, theme):
        f_rev = (qs.get("rev", [""])[0] or "")[:20]
        f_lang = (qs.get("flang", [""])[0] or "")[:10]
        f_type = (qs.get("otype", [""])[0] or "")[:40]
        f_status = (qs.get("status", [""])[0] or "")[:20]
        cx = DB.connect(self.db_path)
        try:
            rows = _q(cx, "SELECT o.*, d.independent_request_count indep, d.evidence_summary dsum"
                           " FROM opportunities o LEFT JOIN demand_signals d"
                           " ON d.opportunity_id=o.id"
                           " WHERE o.status NOT IN ('archived','rejected')"
                           " ORDER BY o.score DESC LIMIT 200")
        finally:
            cx.close()
        import json as _j
        if f_rev:
            rows = [r for r in rows if (r.get("revenue_intent") or "unknown") == f_rev]
        if f_type:
            rows = [r for r in rows if f_type in _j.loads(r.get("opp_types") or "[]")]
        if f_status:
            rows = [r for r in rows if (r.get("status") or "") == f_status]
        filt = (f"<div class='card'><form method='GET' action='/revenue'>"
                f"<input type='hidden' name='lang' value='{lang}'>"
                f"<input type='hidden' name='theme' value='{theme}'>"
                f"rev <select name='rev'><option value=''>—</option>"
                + "".join(f"<option value='{l}'{' selected' if f_rev == l else ''}>{l}</option>"
                          for l in ["high", "medium", "low", "unknown", "not_commercial"])
                + f"</select> lang <select name='flang'><option value=''>—</option>"
                + "".join(f"<option value='{l}'{' selected' if f_lang == l else ''}>{l}</option>"
                          for l in ["ar", "en"])
                + f"</select> type <input name='otype' value='{esc(f_type)}' size='18'> "
                f"<button type='submit'>filter</button> <span class='muted'>commercial signals only — "
                f"never guaranteed revenue</span></form></div>")

        def _lang_ok(r):
            if not f_lang:
                return True
            try:
                cx2 = DB.connect(self.db_path)
                try:
                    langs = {x["language"] for x in _q(
                        cx2, "SELECT r.language FROM opportunity_members m "
                             "JOIN normalized n ON n.id=m.normalized_id "
                             "JOIN raw_requests r ON r.id=n.raw_id WHERE m.opportunity_id=?",
                        (r["id"],))}
                finally:
                    cx2.close()
                return f_lang in langs
            except Exception:
                return True

        rows = [r for r in rows if _lang_ok(r)]
        if not rows:
            return (f"<h2>{esc(STR['revenue'][lang])}</h2>" + filt
                    + f"<div class='card'>{esc(STR['empty'][lang])}</div>")
        cards = [f"<h2>{esc(STR['revenue'][lang])}</h2>", filt]
        for o in rows:
            cards.append(
                f"<div class='card'><a href='/opp?id={o['id']}&{_keep(qs)}'><b>{esc(o['title'] or '')}</b></a>"
                f"<div class='muted'>score {o['score']:.2f} · {esc(STR['rev_intent'][lang])}: "
                f"<b>{esc(o.get('revenue_intent') or 'unknown')}</b> · indep {o.get('indep') or 0} · "
                f"{esc(o.get('demand_strength') or '')} · {esc(o.get('complexity') or '')}</div>"
                f"<div><span class='pill'>{esc(o['ai_feasibility'] or '')}</span>"
                f"<span class='pill'>local {esc(o.get('local_feasibility') or '?')}</span>"
                f"<span class='pill'>{esc(o.get('status') or '')}</span></div></div>")
        return "".join(cards)

    def v_firstmoney(self, qs, lang, theme):
        """Candidates ONLY: commercial intent + clear problem + AI-feasible +
        validated-or-single evidence + public source. Spurious/insufficient excluded."""
        feas = ("clearly_feasible", "feasible_with_local_tools", "feasible_with_human",
                "feasible_with_external", "experimental")
        cx = DB.connect(self.db_path)
        try:
            rows = _q(cx, "SELECT * FROM opportunities WHERE status NOT IN ('archived','rejected')"
                           " AND COALESCE(validation_state,'') NOT IN ('SPURIOUS_MATCH','INSUFFICIENT_EVIDENCE')"
                           " AND COALESCE(revenue_intent,'unknown') IN ('high','medium')"
                           " AND LENGTH(COALESCE(normalized_problem,'')) >= 40"
                           " AND ai_feasibility IN (?,?,?,?,?)"
                           " ORDER BY score DESC LIMIT 50", feas)
            out = []
            for o in rows:
                oid = o["id"]
                members = _q(cx, "SELECT n.ai_relevance, n.normalized_text, r.source, r.source_url,"
                                 " r.author FROM opportunity_members m "
                                 "JOIN normalized n ON n.id=m.normalized_id "
                                 "JOIN raw_requests r ON r.id=n.raw_id "
                                 "WHERE m.opportunity_id=? ORDER BY r.id", (oid,))
                if not members or not any(m.get("source_url") for m in members):
                    continue
                rels = sorted({m.get("ai_relevance") or "?" for m in members})
                if not (set(rels) & {"high", "medium"}):
                    continue
                sols = _q(cx, "SELECT name, url FROM solutions WHERE opportunity_id=? LIMIT 5", (oid,))
                revs = _q(cx, "SELECT rs.level, rs.evidence FROM revenue_signals rs "
                               "JOIN normalized n ON n.raw_id=rs.request_id "
                               "JOIN opportunity_members m ON m.normalized_id=n.id "
                               "WHERE m.opportunity_id=?", (oid,))
                lead = cx.execute("SELECT public_username, public_profile_url, public_email,"
                                  " public_website, contactability FROM leads "
                                  "WHERE opportunity_id=? ORDER BY "
                                  "CASE contactability WHEN 'high' THEN 0 WHEN 'medium' THEN 1 "
                                  "WHEN 'low' THEN 2 ELSE 3 END LIMIT 1", (oid,)).fetchone()
                out.append((o, members, rels, sols, revs, dict(lead) if lead else {}))
        finally:
            cx.close()
        import json as _j
        h = [f"<h2>{esc(STR['firstmoney'][lang])}</h2>",
             "<div class='card muted'>Only: commercial intent + clear problem + AI relevance + "
             "feasible + evidence + public source. Spurious/insufficient excluded. "
             "Manual outreach only — nothing here sends messages.</div>"]
        if not out:
            h.append(f"<div class='card'>{esc(STR['empty'][lang])}</div>")
            return "".join(h)
        for o, members, rels, sols, revs, lead in out:
            seed = members[0]
            evph = []
            for r in revs:
                try:
                    evph += [f"{e.get('kind')}: {e.get('phrase')}" for e in _j.loads(r.get("evidence") or "[]")[:2]]
                except Exception:
                    pass
            try:
                ideas = _j.loads(o.get("service_ideas") or "[]")
            except Exception:
                ideas = []
            solnames = ", ".join(s.get("name") or "" for s in sols) or "none found yet"
            ideanames = ", ".join(i.get("format", "") for i in ideas) or "—"
            gapshort = (o.get("gap_analysis") or "")[:300] or "—"
            evshort = "; ".join(evph[:6]) or "—"
            if lead.get("public_email") or lead.get("public_website"):
                contact = lead.get("public_email") or lead.get("public_website")
            elif lead.get("public_profile_url"):
                contact = lead.get("public_profile_url")
            elif lead.get("public_username"):
                contact = "@" + lead["public_username"]
            else:
                contact = "none observed"
            opts = "".join(f"<option value='{d}'>{dl}</option>" for d, dl in
                           [("investigate", "Investigate"), ("build", "Build"),
                            ("contact_manually", "Contact manually"), ("ignore", "Ignore")])
            h.append(
                f"<div class='card'><a href='/opp?id={o['id']}&{_keep(qs)}'><b>{esc(o['title'] or '')}</b></a>"
                f"<div class='muted'>score {o['score']:.2f} · intent {esc(o.get('revenue_intent') or '')} · "
                f"AI {esc('/'.join(rels))} · {esc(o.get('validation_state') or '')}</div>"
                f"<p><b>Problem:</b> {esc((o.get('normalized_problem') or '')[:400])}</p>"
                f"<p><b>Original:</b> {esc((seed.get('normalized_text') or '')[:300])} "
                f"<span class='muted'>({esc(seed.get('source') or '')}"
                f"{' · @' + esc(seed['author']) if seed.get('author') else ''} · "
                f"<a href='{esc(seed.get('source_url') or '')}'>source ↗</a>)</span></p>"
                f"<p><b>Commercial evidence:</b> {esc(evshort)}</p>"
                f"<p><b>Independent evidence:</b> {o.get('independent_evidence_count', 0)} request(s) across "
                f"{o.get('independent_source_count', 0)} source(s) · same-problem {o.get('same_problem_count', 0)}</p>"
                f"<p><b>Existing solutions:</b> {esc(solnames)}</p>"
                f"<p><b>Gap:</b> {esc(gapshort)}</p>"
                f"<p><b>AI feasibility:</b> {esc(o.get('ai_feasibility') or '')} · "
                f"<b>Local:</b> {esc(o.get('local_feasibility') or '')} · "
                f"<b>Complexity:</b> {esc(o.get('complexity') or '')} · "
                f"<b>Confidence:</b> {o.get('confidence')}</p>"
                f"<p><b>Suggested service:</b> {esc(ideanames)}</p>"
                f"<p><b>Public contact:</b> {esc(contact)}</p>"
                f"<form method='POST' action='/feedback'>"
                f"<input type='hidden' name='opportunity_id' value='{o['id']}'>"
                f"<input type='hidden' name='lang' value='{lang}'>"
                f"<input type='hidden' name='theme' value='{theme}'>"
                f"<select name='decision'>{opts}</select> "
                f"<input name='reason' placeholder='reason…' size='30'> "
                f"<button type='submit'>OK</button></form></div>")
        return "".join(h)

    def v_arabic(self, qs, lang, theme):
        f_d = (qs.get("dialect", [""])[0] or "")[:20]
        f_r = (qs.get("region", [""])[0] or "")[:40]
        f_i = (qs.get("intent", [""])[0] or "")[:20]
        f_s = (qs.get("source", [""])[0] or "")[:40]
        cx = DB.connect(self.db_path)
        try:
            total = cx.execute("SELECT COUNT(*) c FROM raw_requests WHERE language='ar'").fetchone()["c"]
            by_d = _q(cx, "SELECT COALESCE(NULLIF(n.dialect,''),'unknown') d, COUNT(*) c "
                           "FROM raw_requests r LEFT JOIN normalized n ON n.raw_id=r.id "
                           "WHERE r.language='ar' GROUP BY d ORDER BY c DESC")
            by_r = _q(cx, "SELECT COALESCE(NULLIF(n.explicit_region,''),'Unknown') r, COUNT(*) c "
                           "FROM raw_requests r LEFT JOIN normalized n ON n.raw_id=r.id "
                           "WHERE r.language='ar' GROUP BY r ORDER BY c DESC")
            by_i = _q(cx, "SELECT rs.level l, COUNT(*) c FROM revenue_signals rs "
                           "JOIN raw_requests r ON r.id=rs.request_id "
                           "WHERE r.language='ar' GROUP BY l ORDER BY c DESC")
            req = _q(cx, "SELECT r.id, r.source, r.source_url, r.author, r.collected_at,"
                          " r.original_text, n.dialect, n.explicit_region, rs.level, rs.evidence"
                          " FROM raw_requests r LEFT JOIN normalized n ON n.raw_id=r.id"
                          " LEFT JOIN revenue_signals rs ON rs.request_id=r.id"
                          " WHERE r.language='ar' ORDER BY r.id DESC LIMIT 200")
            ar_opps = _q(cx, "SELECT DISTINCT o.id, o.title, o.score, o.status, o.revenue_intent,"
                             " o.demand_strength FROM opportunities o "
                             "JOIN opportunity_members m ON m.opportunity_id=o.id "
                             "JOIN normalized n ON n.id=m.normalized_id "
                             "JOIN raw_requests r ON r.id=n.raw_id "
                             "WHERE r.language='ar' AND o.status NOT IN ('archived','rejected')"
                             " ORDER BY o.score DESC LIMIT 50")
        finally:
            cx.close()
        import json as _j
        if f_d:
            req = [x for x in req if (x.get("dialect") or "unknown") == f_d]
        if f_r:
            req = [x for x in req if (x.get("explicit_region") or "Unknown") == f_r]
        if f_i:
            req = [x for x in req if (x.get("level") or "unknown") == f_i]
        if f_s:
            req = [x for x in req if (x.get("source") or "") == f_s]
        filt = (f"<div class='card'><form method='GET' action='/arabic'>"
                f"<input type='hidden' name='lang' value='{lang}'>"
                f"<input type='hidden' name='theme' value='{theme}'>"
                f"{esc(STR['dialect'][lang])} <select name='dialect'><option value=''>—</option>"
                + "".join(f"<option value='{d['d']}'{' selected' if f_d == d['d'] else ''}>{esc(d['d'])} ({d['c']})</option>" for d in by_d)
                + f"</select> {esc(STR['region'][lang])} <select name='region'><option value=''>—</option>"
                + "".join(f"<option value='{esc(r['r'])}'{' selected' if f_r == r['r'] else ''}>{esc(r['r'])} ({r['c']})</option>" for r in by_r)
                + f"</select> intent <select name='intent'><option value=''>—</option>"
                + "".join(f"<option value='{l}'{' selected' if f_i == l else ''}>{l}</option>"
                          for l in ["high", "medium", "low", "unknown", "not_commercial"])
                + f"</select> <button type='submit'>filter</button></form></div>")
        _d = ", ".join(f"{x['d']}={x['c']}" for x in by_d) or "—"
        _r = ", ".join(f"{x['r']}={x['c']}" for x in by_r) or "—"
        _i = ", ".join(f"{x['l']}={x['c']}" for x in by_i) or "—"
        h = [f"<h2>{esc(STR['arabic'][lang])}</h2>",
             f"<div class='card'><b>{total}</b> Arabic requests · "
             f"dialects: {esc(_d)} · "
             f"regions: {esc(_r)} · "
             f"intent: {esc(_i)}</div>",
             filt]
        h.append(f"<h3>{esc(STR['buyer'][lang])} — Arabic opportunities ({len(ar_opps)})</h3>")
        for o in ar_opps:
            so = " · ⚠ " + esc(STR['single_obs'][lang]) if (o.get("demand_strength") or "") == "single_observation" else ""
            h.append(f"<div class='card'><a href='/opp?id={o['id']}&{_keep(qs)}'><b>{esc(o['title'] or '')}</b></a>"
                     f"<div class='muted'>score {o['score']:.2f} · intent {esc(o.get('revenue_intent') or '')}"
                     f" · {esc(o.get('demand_strength') or '')}{so}</div></div>")
        h.append(f"<h3>Arabic requests ({len(req)})</h3>")
        for x in req:
            try:
                evs = _j.loads(x.get("evidence") or "[]")
            except Exception:
                evs = []
            ph = "; ".join(f"{e.get('kind')}: {e.get('phrase')}" for e in evs[:3])
            h.append(f"<div class='card'><div class='muted'>{esc(x.get('source') or '')} · "
                     f"{esc(x.get('dialect') or 'unknown')} · {esc(x.get('explicit_region') or 'Unknown')} · "
                     f"<b>{esc(x.get('level') or 'unknown')}</b> · {esc(x.get('collected_at') or '')}"
                     f"{' · @' + esc(x['author']) if x.get('author') else ''}</div>"
                     f"<div>{esc((x.get('original_text') or '')[:600])}</div>"
                     + (f"<div class='muted'>{esc(ph)}</div>" if ph else "")
                     + f"<div><a href='{esc(x.get('source_url') or '')}'>source ↗</a></div></div>")
        return "".join(h)

    def v_arabic_sources(self, lang, theme):
        from . import qualification as _Q
        rows = _Q.all_rows(self.db_path)
        h = [f"<h2>{esc(STR['ar_sources'][lang])}</h2>",
             "<div class='card muted'>LIVE = real items persisted via scheduled runs. "
             "Zeros are reported as zero — never converted to success.</div>"
             "<table><tr><th>name</th><th>lang</th><th>category</th><th>status</th>"
             "<th>probe</th><th>scheduled</th><th>robots</th><th>reason</th></tr>"]
        for r in rows:
            h.append(f"<tr><td>{esc(r.get('name') or '')}</td><td>{esc(r.get('language') or '')}</td>"
                     f"<td>{esc(r.get('category') or '')}</td><td><b>{esc(r.get('status') or '')}</b></td>"
                     f"<td>{r.get('probe_items') or 0}</td><td>{r.get('scheduled_items') or 0}</td>"
                     f"<td>{esc(r.get('robots_status') or '')}</td>"
                     f"<td class='muted'>{esc((r.get('reason') or '')[:200])}</td></tr>")
        if not rows:
            h.append(f"</table><div class='card'>{esc(STR['empty'][lang])}</div>")
        else:
            h.append("</table>")
        return "".join(h)

    def v_signals(self, qs, lang, theme):
        cx = DB.connect(self.db_path)
        try:
            rows = _q(cx, "SELECT rs.*, r.source, r.source_url, r.language FROM revenue_signals rs "
                           "JOIN raw_requests r ON r.id=rs.request_id "
                           "WHERE rs.level IN ('high','medium') ORDER BY rs.id DESC LIMIT 100")
        finally:
            cx.close()
        import json as _j
        if not rows:
            return f"<div class='card'>{esc(STR['empty'][lang])}</div>"
        out = [f"<h2>{esc(STR['signals'][lang])}</h2>"
               f"<div class='card muted'>fresh commercial signals — evidence phrases observed, "
               f"not proof of payment</div>"]
        for s in rows:
            try:
                evs = _j.loads(s.get("evidence") or "[]")
            except Exception:
                evs = []
            phrases = "; ".join(f"{e.get('kind')}: {e.get('phrase')}" for e in evs[:4])
            out.append(f"<div class='card'><span class='pill'>{esc(s['level'] or '')}</span> "
                       f"<span class='muted'>{esc(s['source'] or '')} · {esc(s['language'] or '')} · "
                       f"pay={s.get('payment_language')} hire={s.get('hiring_language')} "
                       f"biz={s.get('business_context')}</span>"
                       f"<div>{esc(phrases)}</div>"
                       f"<div><a href='{esc(s.get('source_url') or '')}'>source ↗</a></div></div>")
        return "".join(out)

    def v_leads(self, qs, lang, theme):
        cx = DB.connect(self.db_path)
        try:
            rows = _q(cx, "SELECT * FROM leads ORDER BY "
                           "CASE contactability WHEN 'high' THEN 0 WHEN 'medium' THEN 1 "
                           "WHEN 'low' THEN 2 ELSE 3 END, id DESC LIMIT 100")
        finally:
            cx.close()
        if not rows:
            return f"<div class='card'>{esc(STR['empty'][lang])}</div>"
        h = [f"<h2>{esc(STR['leads'][lang])}</h2>"
             "<div class='card muted'>public contact info only — never enriched. "
             "Manual outreach only.</div><table><tr><th>req</th><th>opp</th><th>user</th>"
             "<th>contact</th><th>level</th></tr>"]
        for l in rows:
            contact = l.get("public_email") or l.get("public_website") or ""
            prof = (f"<a href='{esc(l['public_profile_url'])}'>profile ↗</a>"
                    if l.get("public_profile_url") else esc(l.get("public_username") or "—"))
            if l.get("opportunity_id"):
                olink = "<a href='/opp?id=%s&%s'>#%s</a>" % (l["opportunity_id"], _keep(qs), l["opportunity_id"])
            else:
                olink = "—"
            h.append(f"<tr><td>{l.get('request_id')}</td>"
                     f"<td>{olink}</td>"
                     f"<td>{prof}</td><td>{esc(contact)}</td>"
                     f"<td>{esc(l.get('contactability') or '')}</td></tr>")
        return "".join(h) + "</table>"

    def v_demand(self, qs, lang, theme):
        cx = DB.connect(self.db_path)
        try:
            rows = _q(cx, "SELECT o.id, o.title, o.score, o.status, d.* FROM demand_signals d "
                           "JOIN opportunities o ON o.id=d.opportunity_id ORDER BY o.score DESC LIMIT 100")
        finally:
            cx.close()
        if not rows:
            return f"<div class='card'>{esc(STR['empty'][lang])}</div>"
        import json as _j
        h = [f"<h2>{esc(STR['demand'][lang])}</h2>"
             "<table><tr><th>opp</th><th>strength</th><th>indep</th><th>sources</th>"
             "<th>authors</th><th>growth48h</th><th>fresh</th><th>last seen</th></tr>"]
        for r in rows:
            try:
                s = _j.loads(r.get("evidence_summary") or "{}")
            except Exception:
                s = {}
            h.append(f"<tr><td><a href='/opp?id={r['id']}&{_keep(qs)}'>{esc((r['title'] or '')[:60])}</a></td>"
                     f"<td>{esc(s.get('strength', ''))}</td><td>{r.get('independent_request_count')}</td>"
                     f"<td>{r.get('unique_source_count')}</td><td>{r.get('unique_author_count')}</td>"
                     f"<td>{r.get('growth_rate')}</td><td>{r.get('freshness')}</td>"
                     f"<td class='muted'>{esc((r.get('last_seen') or '')[:16])}</td></tr>")
        return "".join(h) + "</table>"

    def v_brief(self, qs, lang, theme):
        try:
            oid = int(qs.get("id", ["0"])[0])
        except ValueError:
            oid = 0
        from . import leads as _L
        brief = _L.contact_brief(self.db_path, oid, lang)
        if not brief:
            return "<div class='card'>not found</div>"
        return (f"<div class='card'><h3>{esc(STR['brief'][lang])}</h3>"
                f"<pre style='white-space:pre-wrap'>{esc(brief)}</pre>"
                f"<p class='muted'>Copy/paste manually. This system never sends messages.</p>"
                f"<p><a href='/opp?id={oid}&{_keep(qs)}'>← back to opportunity</a></p></div>")

    def spec(self, qs):
        try:
            oid = int(qs.get("id", ["0"])[0])
        except ValueError:
            oid = 0
        spec = PIPE.opportunity_spec(self.db_path, oid)
        if not spec:
            return self._send("not found", code=404)
        return self._send(json.dumps(spec, ensure_ascii=False, indent=2), "application/json")


def serve(db_path, host, port):
    Handler.db_path = db_path
    httpd = HTTPServer((host, port), Handler)
    print(f"dashboard: http://{host}:{port}/ (Ctrl+C to stop)")
    httpd.serve_forever()
