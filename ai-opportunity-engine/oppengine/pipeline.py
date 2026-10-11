"""Core pipeline: COLLECT -> RAW -> NORMALIZE -> LANG -> AI-DETECT -> REVENUE INTENT ->
EXTRACT -> DEDUP -> SEMANTIC -> CLUSTER -> DEMAND -> FEASIBILITY -> SOLUTIONS ->
GAP -> COMMERCIAL -> SCORE -> LEADS -> REVIEW -> SPEC.
"""
import time

from . import ai_reasoning as AIR
from . import arabic_lang as ARL
from . import cluster as CLU
from . import commercial as COMM
from . import db as DB
from . import demand as DEM
from . import feasibility as FEAS
from . import leads as LEADS
from . import normalize as NZ
from . import qualification as QUAL
from . import region as RG
from . import revenue as REV
from . import scoring as SCORE
from . import solutions as SOL
from . import validation as VAL
from .logging_utils import log
from .sources import registry as REG


def _ensure_qualification(db_path, adapter):
    """Seed a CANDIDATE qualification row once (robots checked inside)."""
    desc = getattr(adapter, "QUALIFY", None)
    if not desc:
        return
    rows = {r["name"]: r for r in QUAL.all_rows(db_path)}
    if adapter.name in rows:
        return
    QUAL.qualify(db_path, name=adapter.name, status="CANDIDATE",
                 reason="auto-seeded by pipeline", **desc)


def collect_cycle(db_path, cfg, only=None):
    t0 = time.time()
    run = {"started_at": DB.now_iso(), "source": only or "all", "collected": 0,
           "rejected": 0, "analyzed": 0, "ai_failures": 0, "duplicates": 0,
           "opportunities_new": 0, "opportunities_updated": 0, "error": None,
           "llm_attempts": 0, "llm_successes": 0, "llm_failures": 0, "llm_latency_ms": 0}
    live, stubs = REG.all_adapters(cfg)
    for a in live + stubs:
        DB.upsert_source(db_path, a.name, a.kind, a.interval_s,
                         {"reason": getattr(a, "reason", ""),
                          "support_status": getattr(a, "support_status", "LIVE")},
                         langs=getattr(a, "languages", []),
                         source_type=getattr(a, "source_type", ""),
                         enabled=a.enabled() if hasattr(a, "enabled") else True,
                         timeout_s=a.timeout() if hasattr(a, "timeout") else 20)
    try:
        for a in live:
            if only and a.name != only:
                continue
            if hasattr(a, "enabled") and not a.enabled():
                continue
            if not a.due(db_path):
                continue
            items = a.safe_collect(db_path)
            persisted = 0
            for it in items:
                # Phase 3: Arabic-first language verdict (handles Arabizi + dialects later)
                try:
                    it["language"] = ARL.analyze(it.get("original_text", ""))["language"]
                except Exception:
                    it["language"] = NZ.detect_language(it.get("original_text", ""))
                rid = DB.insert_raw(db_path, it)
                if rid:
                    run["collected"] += 1
                    persisted += 1
                else:
                    run["duplicates"] += 1
            _ensure_qualification(db_path, a)
            if persisted > 0 and getattr(a, "QUALIFY", None):
                QUAL.record_scheduled(db_path, a.name, persisted)
        # ANALYZE + REVENUE INTENT + LEADS (rules carry bulk; LLM only for
        # ambiguous revenue or strong candidates needing verification)
        llm_left = cfg.get("max_llm_per_cycle", 4)
        llm_attempts = llm_ok = llm_fail = llm_ms = llm_tok = 0
        for raw in DB.fetch_unanalyzed(db_path, limit=cfg.get("max_analyze_per_cycle", 60)):
            text = raw.get("original_text", "") or ""
            rev = REV.classify_revenue(text)
            rtype, relevance, conf, _ = NZ.classify_request(text)
            ambiguous = (rev["level"] == "unknown" and relevance in ("medium", "high"))
            strong = (rev["level"] in ("high", "medium") and conf < 0.7)
            wants_llm = llm_left > 0 and (ambiguous or strong) and not (
                rtype in ("human_service", "unclear") and relevance == "none")
            res = AIR.analyze(text, raw.get("language") or "unknown", cfg, use_llm=wants_llm)
            if wants_llm:
                llm_left -= 1  # budget counts attempts, not successes
                llm_attempts += 1
                llm_ms += res.get("_llm_latency_ms", 0) or 0
                llm_tok += res.get("_llm_tokens", 0) or 0
                if res.get("provider") == "lmstudio":
                    llm_ok += 1
                else:
                    llm_fail += 1
            DB.insert_normalized(db_path, {"raw_id": raw["id"], **res})
            DB.store_revenue(db_path, raw["id"], rev)
            try:  # Phase 3: dialect + explicit-region verdicts
                DB.store_linguistics(db_path, raw["id"], ARL.analyze(text),
                                     RG.detect_region(text))
            except Exception:
                pass
            try:
                cx0 = DB.connect(db_path)
                rrow = dict(cx0.execute("SELECT * FROM raw_requests WHERE id=?", (raw["id"],)).fetchone())
                cx0.close()
                LEADS.store_lead(db_path, LEADS.extract_lead(rrow))
            except Exception:
                pass
            run["analyzed"] += 1
            if res.get("ai_failure"):
                run["ai_failures"] += 1
            if res.get("ai_relevance") == "none":
                run["rejected"] += 1
        DB.record_llm_usage(db_path, llm_attempts, llm_ok, llm_fail, llm_ms, llm_tok,
                            "lmstudio+rules", cfg.get("chat_model", ""))
        run["llm_attempts"] = llm_attempts
        run["llm_successes"] = llm_ok
        run["llm_failures"] = llm_fail
        run["llm_latency_ms"] = llm_ms
        # CLUSTER
        new, upd = CLU.dedup_cluster(db_path, cfg)
        run["opportunities_new"] = new
        run["opportunities_updated"] = upd
        # DEMAND + COMMERCIAL (evidence layers before feasibility/solutions/score)
        DEM.refresh_all(db_path)
        COMM.refresh_all(db_path)
        # FEASIBILITY + SOLUTIONS (new opportunities only, max 5 github lookups per cycle)
        FEAS.refresh(db_path)
        cx = DB.connect(db_path)
        try:
            fresh = [dict(r) for r in cx.execute(
                "SELECT * FROM opportunities WHERE competition_note IS NULL ORDER BY score DESC LIMIT 5")]
            new_ids = [r["id"] for r in cx.execute(
                "SELECT id FROM opportunities WHERE created_at >= ?", (run["started_at"],))]
        finally:
            cx.close()
        for oid in new_ids:  # attach public leads to fresh opportunities
            try:
                LEADS.refresh_for_opportunity(db_path, oid)
            except Exception:
                pass
        for o in fresh:
            try:
                SOL.discover_for_opportunity(db_path, cfg, o)
            except Exception as exc:
                log("solutions", o.get("title", "")[:60], status="warn",
                    output={"error": str(exc)[:200]})
        # VALIDATE (Phase 3.5: guards + states; never deletes evidence)
        val_results = VAL.revalidate_all(db_path)
        run["spurious"] = sum(1 for v in val_results if v["validation_state"] == "SPURIOUS_MATCH")
        run["validated"] = sum(1 for v in val_results if v["validation_state"] == "VALIDATED_OPPORTUNITY")
        # CROSS-EVIDENCE (Phase 3.5: every high-intent Arabic request searched
        # across all sources for independent evidence of the same problem)
        run["cross_evidence_attached"] = _cross_evidence_sweep(db_path, cfg)
        # SCORE
        SCORE.rescore_all(db_path)
    except Exception as exc:
        run["error"] = str(exc)[:500]
        log("cycle", run["source"], status="error", output={"error": str(exc)[:300]})
    run["finished_at"] = DB.now_iso()
    run["duration_s"] = round(time.time() - t0, 2)
    cx = DB.connect(db_path)
    try:
        try:
            cx.execute("INSERT INTO runs(started_at,finished_at,source,collected,rejected,analyzed,"
                       "ai_failures,duplicates,opportunities_new,opportunities_updated,duration_s,error,"
                       "llm_attempts,llm_successes,llm_failures,llm_latency_ms)"
                       " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                       (run["started_at"], run["finished_at"], run["source"], run["collected"],
                        run["rejected"], run["analyzed"], run["ai_failures"], run["duplicates"],
                        run["opportunities_new"], run["opportunities_updated"],
                        run["duration_s"], run["error"], run.get("llm_attempts", 0),
                        run.get("llm_successes", 0), run.get("llm_failures", 0),
                        run.get("llm_latency_ms", 0)))
        except Exception:
            cx.execute("INSERT INTO runs(started_at,finished_at,source,collected,rejected,analyzed,"
                       "ai_failures,duplicates,opportunities_new,opportunities_updated,duration_s,error)"
                       " VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                       (run["started_at"], run["finished_at"], run["source"], run["collected"],
                        run["rejected"], run["analyzed"], run["ai_failures"], run["duplicates"],
                        run["opportunities_new"], run["opportunities_updated"],
                        run["duration_s"], run["error"]))
        cx.commit()
    finally:
        cx.close()
    log("cycle", run["source"], output=run)
    return run


def _cross_evidence_sweep(db_path, cfg):
    """Search independent evidence for every high-intent Arabic request.

    Returns count of attached cross-evidence rows. Only real matches passing
    guard + similarity are recorded; nothing is invented."""
    cx = DB.connect(db_path)
    try:
        rows = [dict(r) for r in cx.execute(
            "SELECT n.raw_id, m.opportunity_id FROM revenue_signals rs "
            "JOIN raw_requests r ON r.id=rs.request_id "
            "LEFT JOIN normalized n ON n.raw_id=r.id "
            "LEFT JOIN opportunity_members m ON m.normalized_id=n.id "
            "WHERE r.language='ar' AND rs.level='high' AND n.id IS NOT NULL")]
    finally:
        cx.close()
    attached = 0
    for row in rows:
        try:
            matches = VAL.evidence_search(db_path, cfg, row["raw_id"])
        except Exception:
            continue
        if matches and row.get("opportunity_id"):
            try:
                attached += VAL.attach_cross_evidence(db_path, row["opportunity_id"], matches)
            except Exception:
                pass
    if attached:
        log("cross-evidence", "sweep", output={"attached": attached, "requests": len(rows)})
    return attached


def opportunity_spec(db_path, opp_id):
    """Build opportunity_spec.json payload for future OpenCode handoff."""
    cx = DB.connect(db_path)
    try:
        o = cx.execute("SELECT * FROM opportunities WHERE id=?", (opp_id,)).fetchone()
        if not o:
            return None
        o = dict(o)
        members = [dict(r) for r in cx.execute(
            "SELECT n.*, r.source, r.source_url, r.author, r.collected_at FROM opportunity_members m "
            "JOIN normalized n ON n.id=m.normalized_id JOIN raw_requests r ON r.id=n.raw_id "
            "WHERE m.opportunity_id=?", (opp_id,))]
        sols = [dict(r) for r in cx.execute("SELECT * FROM solutions WHERE opportunity_id=?", (opp_id,))]
        fb = [dict(r) for r in cx.execute("SELECT * FROM feedback WHERE opportunity_id=?", (opp_id,))]
    finally:
        cx.close()
    import json
    ev = {}
    try:
        ev = json.loads(o.get("evidence") or "{}")
    except Exception:
        pass
    return {
        "problem": o.get("normalized_problem"), "category": o.get("category"),
        "evidence": {"request_count": o.get("request_count"), "sources": ev.get("sources"),
                     "score": o.get("score"), "scoring": ev.get("scoring"),
                     "requests": [{"source": m.get("source"), "url": m.get("source_url"),
                                   "text": (m.get("normalized_text") or "")[:500]} for m in members]},
        "requirements": sorted({r for m in members for r in
                                (json.loads(m.get("requirements") or "[]") if isinstance(m.get("requirements"), str) else [])}),
        "constraints": sorted({c for m in members for c in
                               (json.loads(m.get("constraints") or "[]") if isinstance(m.get("constraints"), str) else [])}),
        "suggested_architecture": o.get("suggested_solution") or "",
        "local_capabilities": {"feasibility": o.get("local_feasibility"), "why": o.get("local_why")},
        "external_dependencies": [], "existing_solutions": sols, "gap": o.get("gap_analysis"),
        "mvp_scope": f"Smallest useful slice of: {o.get('title')}",
        "test_requirements": ["evidence links resolve", "no fabricated demand", "arabic+english fixtures"],
        "feedback_history": fb, "generated_at": DB.now_iso(),
    }
