"""CLI: collect | analyze | cycle | serve | doctor | spec | stats | feedback.

Run with the REAL interpreter (bare `python` is a Store shim), e.g.
from this folder:  python.exe -m oppengine.cli doctor
"""
import argparse
import json
import sys
import time
import urllib.request

from . import config as CFG
from . import db as DB
from . import pipeline as PIPE
from .dashboard import serve
from .security import scan_for_secrets


def _cfg(args):
    return CFG.load(getattr(args, "config", "config.yaml"),
                    {"db_path": getattr(args, "db", None)})


def cmd_collect(args):
    cfg = _cfg(args)
    DB.init(cfg["db_path"])
    run = PIPE.collect_cycle(cfg["db_path"], cfg, only=args.source)
    print(json.dumps(run, ensure_ascii=False, indent=2))


def cmd_cycle(args):
    cfg = _cfg(args)
    DB.init(cfg["db_path"])
    if args.loop:
        print(f"cycle every {cfg['cycle_seconds']}s. Ctrl+C to stop.")
        while True:
            run = PIPE.collect_cycle(cfg["db_path"], cfg)
            print(json.dumps(run, ensure_ascii=False))
            time.sleep(cfg["cycle_seconds"])
    else:
        run = PIPE.collect_cycle(cfg["db_path"], cfg)
        print(json.dumps(run, ensure_ascii=False, indent=2))


def cmd_serve(args):
    cfg = _cfg(args)
    DB.init(cfg["db_path"])
    serve(cfg["db_path"], args.host or cfg["dashboard_host"], args.port or cfg["dashboard_port"])


def cmd_doctor(args):
    import os
    cfg = _cfg(args)
    checks = []
    # python + sqlite
    import sqlite3
    checks.append(("python", sys.version.split()[0], True))
    checks.append(("sqlite", sqlite3.sqlite_version, True))
    # db
    try:
        DB.init(cfg["db_path"])
        s = DB.stats(cfg["db_path"])
        checks.append(("db", f"{cfg['db_path']} raw={s['raw_requests']} opps={s['opportunities']}", True))
    except Exception as exc:
        checks.append(("db", str(exc)[:120], False))
    # lmstudio chat + embeddings
    for kind, model, path in [("lmstudio-chat", cfg["chat_model"], "/v1/models"),
                              ("lmstudio-embed", cfg["embed_model"], "/v1/models")]:
        try:
            req = urllib.request.Request(cfg["lmstudio_base"].rstrip("/") + path)
            with urllib.request.urlopen(req, timeout=10) as r:
                data = json.loads(r.read().decode())
            ids = [m.get("id") for m in data.get("data", [])]
            checks.append((kind, f"up models={ids}", model in ids))
        except Exception as exc:
            checks.append((kind, f"DOWN: {str(exc)[:100]} (pipeline falls back to rules)", False))
    # secret scan of repo-tracked text files (tests/ excluded: synthetic fixtures
    # resembling credentials are covered by test_redaction instead)
    hits = 0
    for root, _, files in os.walk("."):
        if any(p in root for p in (".git", ".venv", "__pycache__", "data", "logs",
                                   ".pytest_cache", "tests")):
            continue
        for f in files:
            if f.endswith((".py", ".yaml", ".md", ".txt", ".json")):
                try:
                    with open(os.path.join(root, f), encoding="utf-8", errors="ignore") as fh:
                        if scan_for_secrets(fh.read(200000)):
                            hits += 1
                except OSError:
                    pass
    checks.append(("secret-scan", f"{hits} file(s) with secret-like patterns", hits == 0))
    # Phase 2 components
    try:
        cx = DB.connect(cfg["db_path"])
        try:
            p2 = {}
            for t in ("revenue_signals", "demand_signals", "leads", "opportunity_evidence",
                      "commercial_analysis", "llm_usage"):
                p2[t] = cx.execute(f"SELECT COUNT(*) c FROM {t}").fetchone()["c"]
            ar = cx.execute("SELECT COUNT(*) c FROM raw_requests WHERE language='ar'").fetchone()["c"]
            hi = cx.execute("SELECT COUNT(*) c FROM revenue_signals WHERE level IN ('high','medium')").fetchone()["c"]
            unhealthy = cx.execute("SELECT COUNT(*) c FROM sources WHERE consecutive_errors > 0"
                                   " OR rate_limit_state != ''").fetchone()["c"]
        finally:
            cx.close()
        checks.append(("phase2-tables", f"{p2}", True))
        checks.append(("phase2-demand", f"ar_requests={ar} med/high_signals={hi} unhealthy_sources={unhealthy}", True))
    except Exception as exc:
        checks.append(("phase2-tables", str(exc)[:120], False))
    ok = all(c[2] for c in checks)
    for name, detail, passed in checks:
        print(f"[{'OK' if passed else 'FAIL'}] {name}: {detail}")
    return 0 if ok else 1


def cmd_spec(args):
    cfg = _cfg(args)
    spec = PIPE.opportunity_spec(cfg["db_path"], args.id)
    if not spec:
        print("not found", file=sys.stderr)
        return 1
    print(json.dumps(spec, ensure_ascii=False, indent=2))
    return 0


def cmd_stats(args):
    cfg = _cfg(args)
    DB.init(cfg["db_path"])
    print(json.dumps(DB.stats(cfg["db_path"]), ensure_ascii=False, indent=2))


def cmd_feedback(args):
    cfg = _cfg(args)
    cx = DB.connect(cfg["db_path"])
    try:
        cx.execute("INSERT INTO feedback(opportunity_id,decision,reason,created_at) VALUES(?,?,?,?)",
                   (args.id, args.decision, args.reason or "", DB.now_iso()))
        if args.decision in ("ignore", "archive", "already_solved", "too_difficult"):
            st = "archived" if args.decision == "archive" else "rejected"
            cx.execute("UPDATE opportunities SET status=?, updated_at=? WHERE id=?",
                       (st, DB.now_iso(), args.id))
        cx.commit()
        print("recorded")
    finally:
        cx.close()


def cmd_backfill(args):
    """Phase 2 backfill: revenue+leads for pre-Phase-2 rows, demand+commercial for all opps."""
    from . import commercial as COMM
    from . import demand as DEM
    from . import leads as LEADS
    from . import revenue as REV
    cfg = _cfg(args)
    DB.init(cfg["db_path"])
    cx = DB.connect(cfg["db_path"])
    try:
        missing = [dict(r) for r in cx.execute(
            "SELECT r.* FROM raw_requests r LEFT JOIN revenue_signals rs ON rs.request_id=r.id "
            "WHERE rs.id IS NULL")]
        opps = [dict(r) for r in cx.execute("SELECT * FROM opportunities")]
    finally:
        cx.close()
    n_rev = n_lead = 0
    for raw in missing:
        rev = REV.classify_revenue(raw.get("original_text", "") or "")
        DB.store_revenue(cfg["db_path"], raw["id"], rev)
        n_rev += 1
        try:
            LEADS.store_lead(cfg["db_path"], LEADS.extract_lead(raw))
            n_lead += 1
        except Exception:
            pass
    DEM.refresh_all(cfg["db_path"])
    COMM.refresh_all(cfg["db_path"])
    from . import scoring as SCORE
    SCORE.rescore_all(cfg["db_path"])
    cx = DB.connect(cfg["db_path"])
    try:
        for o in opps:
            try:
                LEADS.refresh_for_opportunity(cfg["db_path"], o["id"])
            except Exception:
                pass
    finally:
        cx.close()
    print(json.dumps({"revenue_backfilled": n_rev, "leads_backfilled": n_lead,
                      "opportunities": len(opps)}, ensure_ascii=False))


def cmd_arabic_backfill(args):
    """Phase 3 backfill: language/dialect/region verdicts for all analyzed rows."""
    from . import arabic_lang as ARL
    from . import region as RG
    cfg = _cfg(args)
    DB.init(cfg["db_path"])
    cx = DB.connect(cfg["db_path"])
    try:
        rows = [dict(r) for r in cx.execute(
            "SELECT r.id, r.original_text FROM raw_requests r "
            "JOIN normalized n ON n.raw_id=r.id "
            "WHERE COALESCE(n.dialect,'')=''")]
    finally:
        cx.close()
    n = 0
    for raw in rows:
        text = raw.get("original_text", "") or ""
        try:
            lang = ARL.analyze(text)
            if lang.get("language") in ("ar", "en"):
                cx = DB.connect(cfg["db_path"])
                try:
                    cx.execute("UPDATE raw_requests SET language=? WHERE id=?",
                               (lang["language"], raw["id"]))
                    cx.commit()
                finally:
                    cx.close()
            DB.store_linguistics(cfg["db_path"], raw["id"], lang, RG.detect_region(text))
            n += 1
        except Exception:
            pass
    print(json.dumps({"linguistics_backfilled": n}, ensure_ascii=False))


def cmd_qualify(args):
    """Phase 3: record a source candidate (robots checked live, no ingestion)."""
    from . import qualification as QUAL
    cfg = _cfg(args)
    DB.init(cfg["db_path"])
    row = QUAL.qualify(cfg["db_path"], name=args.name, url=args.url, language=args.lang,
                       category=args.category, public_access=args.access,
                       authentication_required=args.auth,
                       technical_access=args.technical, terms_risk=args.risk,
                       expected_signal_quality=args.quality,
                       polling_interval=args.interval, status=args.status, reason=args.reason)
    print(json.dumps(row, ensure_ascii=False, indent=2))


def cmd_revalidate(args):
    """Phase 3.5: recompute guards + validation states for all opportunities.

    Evidence is never deleted; spurious clusters are marked, not removed."""
    from . import validation as VAL
    cfg = _cfg(args)
    DB.init(cfg["db_path"])
    results = VAL.revalidate_all(cfg["db_path"])
    by_state = {}
    for r in results:
        by_state[r["validation_state"]] = by_state.get(r["validation_state"], 0) + 1
    print(json.dumps({"total": len(results), "by_state": by_state,
                      "details": results}, ensure_ascii=False, indent=2))


def main(argv=None):
    ap = argparse.ArgumentParser(prog="oppengine")
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--db", default=None)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("collect"); c.add_argument("--source", default=None)
    c.set_defaults(fn=cmd_collect)
    c = sub.add_parser("cycle"); c.add_argument("--loop", action="store_true")
    c.set_defaults(fn=cmd_cycle)
    c = sub.add_parser("serve"); c.add_argument("--host", default=None); c.add_argument("--port", type=int, default=None)
    c.set_defaults(fn=cmd_serve)
    c = sub.add_parser("doctor"); c.set_defaults(fn=cmd_doctor)
    c = sub.add_parser("spec"); c.add_argument("id", type=int); c.set_defaults(fn=cmd_spec)
    c = sub.add_parser("stats"); c.set_defaults(fn=cmd_stats)
    c = sub.add_parser("feedback"); c.add_argument("id", type=int)
    c.add_argument("decision", choices=["interesting", "ignore", "already_solved", "too_difficult",
                                        "investigate", "build", "contact_manually", "archive"])
    c.add_argument("--reason", default=""); c.set_defaults(fn=cmd_feedback)
    c = sub.add_parser("backfill"); c.set_defaults(fn=cmd_backfill)
    c = sub.add_parser("arabic-backfill"); c.set_defaults(fn=cmd_arabic_backfill)
    c = sub.add_parser("qualify"); c.add_argument("name"); c.add_argument("url")
    c.add_argument("--lang", default="ar"); c.add_argument("--category", default="")
    c.add_argument("--access", default=""); c.add_argument("--auth", action="store_true")
    c.add_argument("--technical", default=""); c.add_argument("--risk", default="")
    c.add_argument("--quality", default=""); c.add_argument("--interval", type=int, default=7200)
    c.add_argument("--status", default="CANDIDATE"); c.add_argument("--reason", default="")
    c.set_defaults(fn=cmd_qualify)
    c = sub.add_parser("revalidate"); c.set_defaults(fn=cmd_revalidate)
    args = ap.parse_args(argv)
    rc = args.fn(args)
    return rc or 0


if __name__ == "__main__":
    raise SystemExit(main())
