"""Phase 17 — approval-gated caption-aware pacing execution (adapter only).

Reads the Phase 16 pacing plan + all prior approvals, validates an explicit
execution approval, translates approved TRIM/SPLIT recommendations into a
derived EDL, and executes through the existing Phase 13 machinery
(compose_timeline -> _execute_ops -> extended_qc) plus the Phase 14 caption
layer (apply_captions) and Phase 15 visual validation.

Never renders directly, never touches FFmpeg outside the gateway, never
mutates base artifacts. Planning-only actions stay metadata.
"""
from __future__ import annotations

import time
from dataclasses import asdict
from pathlib import Path

from engine.core.logging_utils import log_event
from engine.core.models import (
    PacingExecutionApproval,
    PacingExecutionOp,
    PacingExecutionPlan,
)
from engine.core.project_store import (
    load_project,
    mark_stage,
    project_dir,
    write_artifact,
)
from engine.rendering.execution import (
    RenderError,
    edl_hash,
    resolve_render_config,
    validate_edl,
)

EXEC_VERSION = "1.0.0"
ENGINE_TAG = "phase17-1.0"
EXEC_APPROVAL_SCHEMA = "pacing-execution-approval-1.0"
EXEC_PLAN_SCHEMA = "caption-pacing-execution-plan-1.0"
EXECUTABLE_ACTIONS = ("TRIM", "SPLIT")
EXECUTABLE_MODES = ("TRIM", "SPLIT")
ACTION_TO_MODE = {
    "TRIM": "TRIM",
    "SPLIT": "SPLIT",
    "CHANGE_VISUAL": "VISUAL_CHANGE",
    "ADD_CUTAWAY_OPPORTUNITY": "CUTAWAY_OPPORTUNITY",
    "HOLD_LONGER": "HOLD",
    "KEEP": "NOOP",
    "REVIEW": "NOOP",
    "ACCELERATE_VISUAL": "NOOP",
}
_EPS = 1e-3


class PacingExecutionError(RuntimeError):
    """Approval/selection/validation failure (CLI exit 2)."""


def _r6(x: float) -> float:
    return round(float(x), 6)


def _overlap(a: float, b: float, c: float, d: float) -> float:
    return max(0.0, min(b, d) - max(a, c))


def _hex(payload, strip: tuple = ()) -> str:
    import hashlib
    import json as _json
    if isinstance(payload, dict):
        payload = {k: v for k, v in payload.items() if k not in strip}
    return hashlib.sha256(
        _json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()[:32]


def _exec_approval_hash(approval: dict) -> str:
    return _hex(approval, strip=("approval_state", "approved_at"))


def _versions() -> dict:
    import platform
    return {"python": platform.python_version(), "engine": "0.1.0"}


# ---------------- loading + validation (no media) ----------------

def _load_json(path: Path, what: str, required: bool = True):
    import json
    if not path.is_file():
        if required:
            raise PacingExecutionError(f"missing {what} ({path.name})")
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PacingExecutionError(f"corrupt {what}: {exc}") from exc


def _load_all(project_id: str, require_exec_approval: bool = True,
              drift_as_validate: bool = False) -> dict:
    """Load + validate every input. drift_as_validate=True (execution path)
    reports underlying-artifact drift as RenderError(stage="validate") so the
    CLI maps it to exit 6; approval problems always stay PacingExecutionError
    (exit 2)."""
    project = load_project(project_id)
    pid = project.id
    proot = project_dir(pid)

    def _drift(exc: Exception, what: str):
        msg = f"{what} invalid: {exc}"
        if drift_as_validate:
            raise RenderError(msg, stage="validate") from exc
        raise PacingExecutionError(msg) from exc

    from engine.editing.caption_pacing import validate_caption_pacing_approval
    try:
        pacing = validate_caption_pacing_approval(pid)
    except Exception as exc:
        _drift(exc, "pacing approval")
    edl = _load_json(proot / "edit" / "edit_decision.json",
                     "base EDL (run edit first)")
    issues = validate_edl(edl)
    if issues:
        _drift(PacingExecutionError(
            f"base EDL invalid: {'; '.join(issues[:5])}"), "base EDL")
    duration = float((edl or {}).get("duration") or 0)
    if duration <= 0:
        _drift(PacingExecutionError("base EDL has no usable duration"),
               "base EDL")

    from engine.subtitles.captions import validate_captions_approval
    try:
        caps = validate_captions_approval(pid)
    except Exception as exc:
        _drift(exc, "caption approval")

    vis_plan = _load_json(proot / "captions" / "visual_caption_plan.json",
                          "visual caption plan", required=False)
    vis_approval = None
    if vis_plan is not None:
        from engine.subtitles.visual_captions import validate_visual_approval
        try:
            vis_approval = validate_visual_approval(pid)
        except Exception as exc:
            _drift(exc, "visual-caption approval")

    base_approval, base_approved_ids = None, set()
    if (proot / "editing" / "approved_edit_plan.json").is_file():
        from engine.editing.approval import validate_approval
        try:
            base_approval = validate_approval(pid)
        except Exception as exc:
            _drift(exc, "base edit approval")
        base_approved_ids = {str(c.get("decision_id", ""))
                             for c in base_approval["approval"].get("approved_cuts", [])}

    exec_approval = _load_json(
        proot / "editing" / "approved_caption_pacing_execution.json",
        "pacing execution approval (run approve-caption-pacing-execution first)",
        required=require_exec_approval)
    if exec_approval is not None:
        if exec_approval.get("schema_version") != EXEC_APPROVAL_SCHEMA:
            raise PacingExecutionError("unsupported execution approval schema")
        if exec_approval.get("approval_state") not in ("APPROVED", "EXECUTED"):
            raise PacingExecutionError(
                f"execution approval state {exec_approval.get('approval_state')!r} "
                f"is not executable")

    warnings = []
    if base_approval is None:
        warnings.append("no approved base edit plan: pacing execution approval "
                        "is the sole authority for this render")
    return {"project": project, "pid": pid, "duration": duration,
            "edl": edl, "pacing": pacing,
            "captions": caps, "visual_plan": vis_plan,
            "visual_approval": vis_approval,
            "base_approval": base_approval,
            "base_approved_ids": base_approved_ids,
            "exec_approval": exec_approval, "warnings": warnings}


def _identity_hashes(bundle: dict) -> dict:
    from engine.subtitles.captions import caption_plan_hash
    caps, pacing = bundle["captions"], bundle["pacing"]
    cap_plan, cap_appr = caps["plan"], caps["approval"]
    out = {
        "source_hash": pacing["approval"].get("source_hash", ""),
        "edit_plan_hash": edl_hash(bundle["edl"]),
        "base_approval_hash": _hex(bundle["base_approval"]["approval"])
        if bundle["base_approval"] else "none",
        "caption_plan_hash": caption_plan_hash(cap_plan),
        "caption_approval_hash": _hex({
            "plan": caption_plan_hash(cap_plan),
            "mode": cap_appr.get("mode", ""),
            "style": cap_appr.get("style", ""),
            "font": cap_appr.get("font", {})}),
        "caption_mode": cap_appr.get("mode", "sidecar"),
        "pacing_plan_hash": _hex(pacing["plan"],
                                 strip=("cached",)),
        "pacing_approval_hash": _hex(pacing["approval"],
                                     strip=("approved_at",)),
        "style": pacing["plan"].get("style", "general"),
    }
    if bundle["visual_plan"] is not None:
        from engine.subtitles.visual_captions import visual_plan_hash
        out["visual_caption_plan_hash"] = visual_plan_hash(bundle["visual_plan"])
        out["visual_caption_approval_hash"] = _hex({
            "plan": out["visual_caption_plan_hash"],
            "style": bundle["visual_approval"]["approval"].get("style", "")})
    else:
        out["visual_caption_plan_hash"] = "none"
        out["visual_caption_approval_hash"] = "none"
    return out


# ---------------- candidate validation ----------------

def _edl_cover(bundle: dict, s: float, e: float) -> list[str]:
    """Base-EDL REMOVE decision_ids containing [s, e]."""
    return [str(d.get("decision_id", ""))
            for d in bundle["edl"].get("decisions", []) or []
            if d.get("action") == "REMOVE"
            and float(d["start"]) - 0.05 <= s and e <= float(d["end"]) + 0.05]


def _cue_straddles(cues: list[dict], s: float, e: float) -> list[str]:
    """Cue ids overlapping [s, e] without being fully contained."""
    bad = []
    for c in cues:
        cs, ce = float(c["start"]), float(c["end"])
        if _overlap(cs, ce, s, e) > _EPS and not (cs >= s - _EPS and ce <= e + _EPS):
            bad.append(str(c.get("cue_id", "")))
    return bad


def _validate_candidate(bundle: dict, rec: dict, strict: bool
                        ) -> tuple[dict | None, dict | None]:
    """Returns (spec, rejection). Strict (explicit selection) raises."""
    rid = str(rec.get("recommendation_id", ""))
    action = str(rec.get("action", ""))
    s, e = float(rec.get("start", 0.0)), float(rec.get("end", 0.0))
    dur = bundle["duration"]

    def _fail(reason: str):
        rej = {"recommendation_id": rid, "action": action, "reason": reason}
        if strict:
            raise PacingExecutionError(f"recommendation {rid}: {reason}")
        return None, rej

    if action not in EXECUTABLE_ACTIONS:
        return _fail(f"planning-only action {action}: never executable, "
                     f"preserved as metadata")
    if rec.get("safety_status") != "SAFE":
        return _fail(f"safety {rec.get('safety_status')!r} is not executable "
                     f"(only SAFE)")
    if not (0 <= s < e <= dur + 0.05):
        return _fail(f"invalid source range [{s}, {e}] for duration {dur}")
    if action == "TRIM":
        covering = _edl_cover(bundle, s, e)
        if not covering:
            return _fail("pacing recommendation conflicts with approved EDL "
                         "(no base REMOVE covers this span)")
        if bundle["base_approval"] is not None and \
                not (set(covering) & bundle["base_approved_ids"]):
            return _fail("base approval left this removal unapproved: "
                         "pacing must not override it")
        cues = bundle["captions"]["plan"].get("cues", [])
        bad = _cue_straddles(cues, s, e)
        if bad:
            return _fail(f"PARTIAL_CAPTION_OVERLAP on {bad}: trim would cut "
                         f"through a cue boundary")
    return {"rec": rec, "mode": ACTION_TO_MODE[action]}, None


# ---------------- mapping previews ----------------

def _preview_mapping(bundle: dict, trims: list[tuple]) -> dict:
    """Run the Phase 14 mapper over the derived keeps. Pure computation."""
    from engine.subtitles.captions import map_cues_to_output
    cues = bundle["captions"]["plan"].get("cues", [])
    dur = bundle["duration"]
    bounds = sorted({0.0, dur} | {s for s, _ in trims} | {e for _, e in trims})
    keeps, cursor = [], 0.0
    for a, b in zip(bounds, bounds[1:]):
        if b - a <= _EPS:
            continue
        mid = (a + b) / 2.0
        if any(s - _EPS <= mid <= e + _EPS for s, e in trims):
            continue
        keeps.append((a, b))
        cursor += b - a
    mapped, warnings, stats = map_cues_to_output(cues, keeps)
    by_source: dict[str, list] = {}
    for m in mapped:
        by_source.setdefault(str(m.get("source_cue_id", "")), []).append(m)
    cues_out = []
    for c in cues:
        cid = str(c.get("cue_id", ""))
        subs = by_source.get(cid, [])
        src_words = c.get("word_refs", []) or []
        if not subs:
            cues_out.append({"cue_id": cid, "outcome": "DROPPED",
                             "source_start": c["start"], "source_end": c["end"],
                             "output_start": None, "output_end": None,
                             "words_preserved": 0,
                             "words_dropped": len(src_words),
                             "dropped_words": [
                                 {"text": w.get("text", ""), "start": w.get("start"),
                                  "end": w.get("end"),
                                  "reason": "SOURCE_RANGE_REMOVED"} for w in src_words],
                             "evidence": "no surviving words in kept ranges"})
            continue
        kept_words = sum(len(m.get("word_refs", []) or []) for m in subs)
        expected = " ".join(str(w.get("text", "")) for m in subs
                            for w in (m.get("word_refs", []) or []))
        got = " ".join(w for m in subs
                      for w in str(m.get("text", "")).split())
        if expected.split() != got.split():
            raise PacingExecutionError(
                f"caption text integrity failed for {cid}: mapped text does not "
                f"match surviving words")
        for m in subs:
            for w in (m.get("word_refs", []) or []):
                if not (m["start"] - 1e-3 <= float(w["start"]) and
                        float(w["end"]) <= m["end"] + 1e-3):
                    raise PacingExecutionError(
                        f"mapped word outside mapped cue for {cid}")
        outcome = "SPLIT" if len(subs) > 1 else (
            "PRESERVED" if kept_words == len(src_words) else "TRIMMED")
        cues_out.append({"cue_id": cid, "outcome": outcome,
                         "source_start": c["start"], "source_end": c["end"],
                         "output_start": subs[0]["start"],
                         "output_end": subs[-1]["end"],
                         "words_preserved": kept_words,
                         "words_dropped": len(src_words) - kept_words,
                         "dropped_words": [],
                         "mapped_words": [
                             {"text": w.get("text", ""), "start": w.get("start"),
                              "end": w.get("end")} for m in subs
                             for w in (m.get("word_refs", []) or [])],
                         "evidence": f"{kept_words}/{len(src_words)} words survive"})
    return {"keeps": [[round(a, 6), round(b, 6)] for a, b in keeps],
            "predicted_duration": round(cursor, 6),
            "cues": cues_out,
            "mapper_warnings": warnings, "mapper_stats": stats,
            "mapped": mapped}


def _preview_visual(bundle: dict, preview: dict) -> dict:
    """Map visual placements through the preview; run existing visual QC."""
    if bundle["visual_plan"] is None:
        return {"state": "absent", "placements": [], "failed_checks": []}
    from engine.subtitles.render import _resolve_visual_state, _visual_qc_checks
    caps = bundle["captions"]
    style = caps["approval"].get("style", "default")
    font = caps["approval"].get("font", {}) or {}
    visual_state = _resolve_visual_state(bundle["pid"], preview["mapped"],
                                         style, font)
    if not visual_state.get("active"):
        return {"state": "inactive",
                "warnings": visual_state.get("warnings", []),
                "placements": [], "failed_checks": []}
    cues = {c["cue_id"]: c for c in preview["cues"]}
    placements = []
    for p in bundle["visual_plan"].get("placements", []) or []:
        cid = str(p.get("cue_id", ""))
        cout = cues.get(cid)
        placements.append({"cue_id": cid,
                           "position": p.get("position", ""),
                           "status": "MAPPED" if cout and cout["outcome"] != "DROPPED"
                           else "DROPPED",
                           "output_start": cout["output_start"] if cout else None,
                           "output_end": cout["output_end"] if cout else None})
    failed = [c for c in _visual_qc_checks(preview["mapped"], visual_state)
              if not c.get("passed")]
    return {"state": "active", "placements": placements,
            "failed_checks": failed}


# ---------------- derive EDL + execution plan ----------------

def _merge_trims(trims: list[tuple]) -> tuple[list[tuple], list[str]]:
    ordered = sorted(trims, key=lambda t: (t[0], t[1]))
    merged: list[list] = []
    notes: list[str] = []
    for s, e, rid in ordered:
        if merged and s <= merged[-1][1] + _EPS:
            merged[-1][1] = max(merged[-1][1], e)
            merged[-1][2].append(rid)
            notes.append(f"merged overlapping trims {merged[-1][2]}")
        else:
            merged.append([s, e, [rid]])
    return [(round(s, 6), round(e, 6), rids) for s, e, rids in merged], notes


def _derive_edl(bundle: dict, trims: list[tuple]) -> tuple[dict, list[str]]:
    """Derived EDL: KEEP-all except approved TRIMs. Base EDL untouched."""
    dur = bundle["duration"]
    trims = [(max(0.0, min(float(s), dur)), max(0.0, min(float(e), dur)), r)
             for s, e, r in trims if min(float(e), dur) > max(0.0, float(s)) + _EPS]
    merged, notes = _merge_trims(trims)
    bounds = sorted({0.0, dur} | {s for s, _, _ in merged} | {e for _, e, _ in merged})
    decisions, seq = [], 0
    for a, b in zip(bounds, bounds[1:]):
        if b - a <= _EPS:
            continue
        mid = (a + b) / 2.0
        hit = next(((s, e, r) for s, e, r in merged if s - _EPS <= mid <= e + _EPS), None)
        seq += 1
        if hit:
            decisions.append({"decision_id": f"px_{seq:04d}", "start": round(a, 6),
                              "end": round(b, 6), "action": "REMOVE",
                              "reason": "pacing_trim", "confidence": 0.7,
                              "scene_id": -1, "word_refs": [],
                              "metadata": {"derived_by": ENGINE_TAG,
                                           "recommendations": hit[2]}})
        else:
            decisions.append({"decision_id": f"px_{seq:04d}", "start": round(a, 6),
                              "end": round(b, 6), "action": "KEEP",
                              "reason": "pacing_keep", "confidence": 1.0,
                              "scene_id": -1, "word_refs": [],
                              "metadata": {"derived_by": ENGINE_TAG}})
    # Merge adjacent same-action segments for a minimal plan.
    compact = []
    for d in decisions:
        if compact and compact[-1]["action"] == d["action"] and \
                abs(compact[-1]["end"] - d["start"]) <= _EPS:
            compact[-1]["end"] = d["end"]
            recs = compact[-1]["metadata"].get("recommendations", [])
            recs.extend(d["metadata"].get("recommendations", []))
            compact[-1]["metadata"]["recommendations"] = recs
        else:
            compact.append(d)
    for i, d in enumerate(compact, 1):
        d["decision_id"] = f"px_{i:04d}"
    derived = {"source": bundle["edl"].get("source", ""),
               "duration": dur, "decisions": compact,
               "decision_count": len(compact),
               "derived_by": ENGINE_TAG,
               "derived_from": "edit/edit_decision.json"}
    issues = validate_edl(derived)
    if issues:
        raise PacingExecutionError(
            f"derived EDL invalid: {'; '.join(issues[:5])}")
    return derived, notes


def _build_exec_plan(bundle: dict, idents: dict, approved: list[dict],
                     rejected: list[dict], trims: list[tuple],
                     preview: dict, vis_preview: dict,
                     merge_notes: list[str]) -> PacingExecutionPlan:
    ops: list[PacingExecutionOp] = []
    cursor_map: list[tuple] = []
    cursor = 0.0
    for a, b in preview["keeps"]:
        cursor_map.append((a, b, round(cursor, 6)))
        cursor += b - a

    def _to_out(t: float) -> float:
        for a, b, o in cursor_map:
            if a - _EPS <= t <= b + _EPS:
                return round(o + max(0.0, t - a), 6)
        return round(cursor, 6)

    seq = [0]
    for spec in approved:
        rec = spec["rec"]
        s, e = _r6(rec["start"]), _r6(rec["end"])
        seq[0] += 1
        if spec["mode"] == "TRIM":
            ops.append(PacingExecutionOp(
                op_id=f"px_op_{seq[0]:04d}",
                recommendation_id=str(rec.get("recommendation_id", "")),
                action="TRIM", source_start=s, source_end=e,
                output_start=_r6(sum(b - a for a, b in preview["keeps"]
                                     if b <= s + _EPS)),
                output_end=0.0, scene_id=int(rec.get("scene_id", -1)),
                caption_ids=[c["cue_id"] for c in preview["cues"]
                             if c["outcome"] == "DROPPED" and
                             _overlap(c["source_start"], c["source_end"], s, e) > _EPS],
                safety_status="SAFE", confidence=float(rec.get("confidence", 0.0)),
                reason=f"approved pacing TRIM [{s}, {e}]",
                evidence_refs=list(rec.get("evidence", []) or []),
                execution_mode="TRIM"))
            ops[-1].output_end = ops[-1].output_start
        else:  # SPLIT: boundary preserved, no media delta
            ops.append(PacingExecutionOp(
                op_id=f"px_op_{seq[0]:04d}",
                recommendation_id=str(rec.get("recommendation_id", "")),
                action="SPLIT", source_start=s, source_end=e,
                output_start=_to_out(s), output_end=_to_out(e),
                scene_id=int(rec.get("scene_id", -1)), caption_ids=[],
                safety_status="SAFE", confidence=float(rec.get("confidence", 0.0)),
                reason="approved pacing SPLIT: boundary preserved, no deletion",
                evidence_refs=list(rec.get("evidence", []) or []),
                execution_mode="SPLIT",
                warnings=["split has no timeline effect in Phase 17"]))
    ops.sort(key=lambda o: (o.source_start, o.source_end, o.op_id))
    for i, o in enumerate(ops, 1):
        o.op_id = f"px_op_{i:04d}"
    removed = [[s, e] for s, e, _ in trims]
    preserved = [[a, b] for a, b in preview["keeps"]]
    mapping = [{"source_start": a, "source_end": b, "output_start": o,
                "output_end": round(o + (b - a), 6)} for a, b, o in cursor_map]
    safety_counts: dict[str, int] = {}
    for o in ops:
        safety_counts[o.safety_status] = safety_counts.get(o.safety_status, 0) + 1
    plan = PacingExecutionPlan(
        project_id=bundle["pid"], source_hash=idents["source_hash"],
        pacing_plan_hash=idents["pacing_plan_hash"],
        pacing_approval_hash=idents["pacing_approval_hash"],
        caption_plan_hash=idents["caption_plan_hash"],
        visual_caption_plan_hash=idents["visual_caption_plan_hash"],
        execution_ops=ops, source_to_output_mapping=mapping,
        removed_ranges=removed, preserved_ranges=preserved,
        caption_mapping_preview={k: v for k, v in preview.items() if k != "mapped"},
        visual_caption_mapping_preview=vis_preview,
        safety_summary={"counts": safety_counts,
                        "executable_modes": list(EXECUTABLE_MODES)},
        rejected_ops=rejected,
        warnings=list(bundle["warnings"]) + list(merge_notes))
    plan.base_execution_plan_hash = ""  # filled after derived EDL hash
    return plan


def _derive_all(bundle: dict, approved: list[dict], rejected: list[dict]
                ) -> tuple[dict, PacingExecutionPlan]:
    idents = _identity_hashes(bundle)
    trims, merge_notes = _merge_trims(
        [(float(s["rec"]["start"]), float(s["rec"]["end"]),
          str(s["rec"].get("recommendation_id", "")))
         for s in approved if s["mode"] == "TRIM"])
    preview = _preview_mapping(bundle, [(s, e) for s, e, _ in trims])
    vis_preview = _preview_visual(bundle, preview)
    if vis_preview.get("failed_checks"):
        first = vis_preview["failed_checks"][0]
        raise PacingExecutionError(
            f"VISUAL_CAPTION_REVIEW_REQUIRED: {first.get('name')} "
            f"({first.get('detail')})")
    derived_edl, edl_notes = _derive_edl(bundle, trims)
    plan = _build_exec_plan(bundle, idents, approved, rejected, trims,
                            preview, vis_preview, merge_notes + edl_notes)
    plan.base_execution_plan_hash = edl_hash(derived_edl)
    payload = asdict(plan)
    plan.execution_hash = _hex(payload, strip=("execution_hash", "cached"))
    return derived_edl, plan


# ---------------- approval ----------------

def approve_caption_pacing_execution(
        project_id: str, recommendation_ids: list[str] | None = None,
        all_safe: bool = False, approver: str = "operator") -> dict:
    """Explicit execution approval. Never approves implicitly."""
    if recommendation_ids and all_safe:
        raise PacingExecutionError(
            "--recommendation-id and --all-safe are mutually exclusive")
    project = load_project(project_id)
    pid = project.id
    log_file = project_dir(pid) / "logs" / "run.jsonl"
    t0 = time.perf_counter()
    bundle = _load_all(pid, require_exec_approval=False)
    recs = {str(r.get("recommendation_id", "")): r
            for r in bundle["pacing"]["plan"].get("recommendations", [])}
    approved, rejected = [], []
    if all_safe:
        for rid, rec in sorted(recs.items()):
            if rec.get("action") not in EXECUTABLE_ACTIONS or \
                    rec.get("safety_status") != "SAFE":
                continue
            spec, rej = _validate_candidate(bundle, rec, strict=False)
            if spec is not None:
                approved.append(spec)
            if rej is not None:
                rejected.append(rej)
        if not approved:
            raise PacingExecutionError(
                "no SAFE executable recommendations without conflicts")
    else:
        if not recommendation_ids:
            raise PacingExecutionError(
                "select recommendations with --recommendation-id or --all-safe; "
                "nothing is approved implicitly")
        seen = set()
        for rid in recommendation_ids:
            if rid in seen:
                continue
            seen.add(rid)
            rec = recs.get(rid)
            if rec is None:
                raise PacingExecutionError(f"unknown recommendation {rid!r}")
            spec, _ = _validate_candidate(bundle, rec, strict=True)
            approved.append(spec)
    idents = _identity_hashes(bundle)
    derived_edl, plan = _derive_all(bundle, approved, rejected)
    approval = PacingExecutionApproval(
        project_id=pid, source_hash=idents["source_hash"],
        edit_plan_hash=idents["edit_plan_hash"],
        base_approval_hash=idents["base_approval_hash"],
        caption_plan_hash=idents["caption_plan_hash"],
        caption_approval_hash=idents["caption_approval_hash"],
        visual_caption_plan_hash=idents["visual_caption_plan_hash"],
        visual_caption_approval_hash=idents["visual_caption_approval_hash"],
        pacing_plan_hash=idents["pacing_plan_hash"],
        pacing_approval_hash=idents["pacing_approval_hash"],
        style=idents["style"],
        config_hash=_hex({"caption_mode": idents["caption_mode"],
                          "style": idents["style"],
                          "executable_modes": list(EXECUTABLE_MODES)}),
        code_version=ENGINE_TAG,
        approved_recommendation_ids=[str(s["rec"].get("recommendation_id", ""))
                                     for s in approved],
        rejected_recommendation_ids=[r["recommendation_id"] for r in rejected],
        generated_execution_policy={
            "selection": "all-safe" if all_safe else "explicit",
            "caption_mode": idents["caption_mode"],
            "executable_modes": list(EXECUTABLE_MODES),
            "trim_count": sum(1 for s in approved if s["mode"] == "TRIM"),
            "split_count": sum(1 for s in approved if s["mode"] == "SPLIT")},
        approval_state="APPROVED",
        derived_edl_hash=edl_hash(derived_edl),
        execution_plan_hash=plan.execution_hash,
        approver=approver)
    import datetime
    approval.approved_at = datetime.datetime.now(
        datetime.timezone.utc).isoformat()
    payload = asdict(approval)
    write_artifact(pid, "editing", "approved_caption_pacing_execution.json", payload)
    write_artifact(pid, "edit", "caption_pacing_execution_plan.json", asdict(plan))
    mark_stage(project, "pacing_execution_approval", "done",
               "editing/approved_caption_pacing_execution.json")
    log_event(log_file, "pacing_execution", "approve", "ok",
              time.perf_counter() - t0,
              "editing/approved_caption_pacing_execution.json", _versions(),
              {"approved": len(approved), "rejected": len(rejected)})
    return {"project": pid, "approval": payload,
            "execution_plan": asdict(plan)}


def validate_pacing_execution_approval(project_id: str,
                                         drift_as_validate: bool = False) -> dict:
    """Revalidate all bindings. Returns {approval} or raises."""
    bundle = _load_all(project_id, require_exec_approval=True,
                       drift_as_validate=drift_as_validate)
    approval = bundle["exec_approval"]
    idents = _identity_hashes(bundle)
    for key in ("source_hash", "edit_plan_hash", "base_approval_hash",
                "caption_plan_hash", "caption_approval_hash",
                "visual_caption_plan_hash", "visual_caption_approval_hash",
                "pacing_plan_hash", "pacing_approval_hash", "style"):
        if approval.get(key) != idents[key]:
            raise PacingExecutionError(
                f"execution approval drift on {key}: re-approve execution")
    recs = {str(r.get("recommendation_id", "")): r
            for r in bundle["pacing"]["plan"].get("recommendations", [])}
    for rid in approval.get("approved_recommendation_ids", []):
        if rid not in recs:
            raise PacingExecutionError(
                f"approved recommendation {rid} vanished: re-approve execution")
    _, plan = _derive_all(
        bundle,
        [{"rec": recs[rid], "mode": ACTION_TO_MODE.get(
            str(recs[rid].get("action", "")), "NOOP")}
         for rid in approval.get("approved_recommendation_ids", [])],
        [])
    if plan.execution_hash != approval.get("execution_plan_hash"):
        raise PacingExecutionError(
            "derived execution changed since approval: re-approve execution")
    return {"approval": approval, "bundle": bundle, "plan": plan}


# ---------------- dry run ----------------

def dry_run_pacing_execution(project_id: str) -> dict:
    """Planning metadata only. Writes nothing (no media, no artifacts)."""
    checked = validate_pacing_execution_approval(project_id)
    approval, plan = checked["approval"], checked["plan"]
    bundle = checked["bundle"]
    payload = asdict(plan)
    cue_counts: dict[str, int] = {}
    for c in payload["caption_mapping_preview"].get("cues", []):
        cue_counts[c["outcome"]] = cue_counts.get(c["outcome"], 0) + 1
    recs = bundle["pacing"]["plan"].get("recommendations", [])
    planning_only = sorted(str(r.get("recommendation_id", "")) for r in recs
                           if str(r.get("action", "")) not in EXECUTABLE_ACTIONS)
    return {"project": approval["project_id"],
            "approved_recommendation_ids": approval["approved_recommendation_ids"],
            "rejected_recommendation_ids": approval["rejected_recommendation_ids"],
            "recommendations_planning_only": planning_only,
            "executable_ops": [
                {"op_id": o.op_id, "recommendation_id": o.recommendation_id,
                 "mode": o.execution_mode, "source": [o.source_start, o.source_end],
                 "output": [o.output_start, o.output_end],
                 "safety": o.safety_status} for o in plan.execution_ops],
            "rejected_ops": payload["rejected_ops"],
            "removed_ranges": payload["removed_ranges"],
            "preserved_ranges": payload["preserved_ranges"],
            "caption_impact": cue_counts,
            "visual_caption_impact": payload["visual_caption_mapping_preview"],
            "safety": payload["safety_summary"],
            "warnings": payload["warnings"],
            "predicted_duration": payload["caption_mapping_preview"].get(
                "predicted_duration"),
            "caption_mode": approval["generated_execution_policy"].get("caption_mode"),
            "dry_run": True}


# ---------------- execution ----------------

def _preflight() -> dict:
    from engine.core.media import ffprobe_path
    from engine.rendering.ffmpeg import which_ffmpeg
    ffmpeg = which_ffmpeg()
    ffprobe = ffprobe_path()
    if ffmpeg is None or ffprobe is None:
        missing = [n for n, v in (("ffmpeg", ffmpeg), ("ffprobe", ffprobe))
                   if v is None]
        raise RenderError(
            f"preflight failure: {', '.join(missing)} MISSING on PATH "
            f"(FFmpeg: {'AVAILABLE' if ffmpeg else 'MISSING'}, "
            f"FFprobe: {'AVAILABLE' if ffprobe else 'MISSING'}). "
            f"No render attempted, nothing reported EXECUTED.",
            stage="execute")
    return {"ffmpeg": ffmpeg, "ffprobe": ffprobe}


def _find_pacing_manifest(renders_dir: Path, identity: dict,
                          expected_duration: float, tol: float):
    import json
    from engine.core.media import probe
    for cand in sorted(renders_dir.glob("*_pacing_manifest.json")):
        try:
            data = json.loads(cand.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if data.get("kind") != "pacing-execution" or \
                data.get("status") != "completed":
            continue
        if any(data.get(k) != v for k, v in identity.items()):
            continue
        out = data.get("output", "")
        if not out or not Path(out).is_file() or Path(out).stat().st_size == 0:
            continue
        try:
            if abs(probe(out).duration - expected_duration) > tol:
                continue
        except Exception:
            continue
        return cand
    return None


def execute_caption_pacing_for_project(
        project_id: str, config_overrides: dict | None = None,
        out_name: str | None = None, force: bool = False) -> dict:
    """Full flow: validate -> derive -> Phase 13 execute -> captions -> QC
    -> manifest. Raises PacingExecutionError (approval) or RenderError."""
    from engine.rendering.plan_execute import (
        PLAN_EXEC_VERSION,
        _execute_ops,
        _resolve_encoder_name,
        compose_timeline,
        extended_qc,
    )
    from engine.rendering.execution import RENDERER_VERSION
    project = load_project(project_id)
    pid = project.id
    log_file = project_dir(pid) / "logs" / "run.jsonl"
    try:
        config = resolve_render_config(config_overrides)
    except RenderError as exc:
        raise RenderError(str(exc), stage="input") from exc
    renders_dir = project_dir(pid) / "renders"
    renders_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()

    checked = validate_pacing_execution_approval(pid, drift_as_validate=True)
    approval = checked["approval"]
    bundle, plan = checked["bundle"], checked["plan"]
    try:
        _preflight()
    except RenderError as exc:
        mark_stage(project, "pacing_execution", "failed", str(exc)[:300])
        raise

    from engine.core.media import probe
    try:
        info = probe(project.input_path)
    except Exception as exc:
        raise RenderError(f"cannot probe source: {exc}", stage="input") from exc

    derived_edl, _ = _derive_all(
        bundle,
        [{"rec": r, "mode": ACTION_TO_MODE.get(str(r.get("action", "")), "NOOP")}
         for r in bundle["pacing"]["plan"].get("recommendations", [])
         if str(r.get("recommendation_id", "")) in
         set(approval.get("approved_recommendation_ids", []))],
        [])
    if edl_hash(derived_edl) != approval.get("derived_edl_hash"):
        raise RenderError("derived EDL changed since approval: re-approve execution",
                          stage="validate")
    derived_approval = {
        "approved_cuts": [
            {"decision_id": d["decision_id"], "verdict": "approved"}
            for d in derived_edl["decisions"] if d["action"] == "REMOVE"],
        "broll_assignments": []}
    timeline = compose_timeline(derived_edl, derived_approval)
    try:
        resolved_encoder, enc_reason = _resolve_encoder_name(config, log_file)
    except RenderError as exc:
        mark_stage(project, "pacing_execution", "failed", str(exc)[:300])
        raise
    identity = {"source": project.input_path,
                "base_edl_hash": edl_hash(bundle["edl"]),
                "base_approval_hash": _hex(bundle["base_approval"]["approval"])
                if bundle["base_approval"] else "none",
                "caption_plan_hash": approval["caption_plan_hash"],
                "caption_approval_hash": approval["caption_approval_hash"],
                "visual_caption_plan_hash": approval["visual_caption_plan_hash"],
                "visual_caption_approval_hash": approval["visual_caption_approval_hash"],
                "pacing_plan_hash": approval["pacing_plan_hash"],
                "pacing_approval_hash": approval["pacing_approval_hash"],
                "pacing_execution_approval_hash": _exec_approval_hash(approval),
                "execution_plan_hash": approval["execution_plan_hash"],
                "caption_mode": approval["generated_execution_policy"].get("caption_mode"),
                "style": approval.get("style", ""),
                "encoder": resolved_encoder,
                "render_config": asdict_config(config),
                "code_version": ENGINE_TAG,
                "execution_version": PLAN_EXEC_VERSION,
                "renderer_version": RENDERER_VERSION}
    tol = config.duration_tol if config.accurate else max(config.duration_tol, 1.0)
    base_cached = False
    if not force:
        reuse = _find_pacing_manifest(renders_dir, identity,
                                      timeline.expected_duration, tol)
        if reuse is not None:
            import json
            manifest = json.loads(reuse.read_text(encoding="utf-8"))
            manifest["cached"] = True
            _mark_executed(pid, project)
            log_event(log_file, "pacing_execution", "reuse", "ok",
                      time.perf_counter() - t0, manifest.get("output", ""),
                      _versions(), {"expected_s": timeline.expected_duration})
            mark_stage(project, "pacing_execution", "done",
                       f"renders/{reuse.name}")
            return {"project": pid, "cached": True, "manifest": manifest,
                    "output": manifest.get("output", "")}
    import datetime
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    dst = renders_dir / (out_name or f"pacing_{stamp}.mp4")
    work = renders_dir / f"_pacing_{time.time_ns()}"
    log_event(log_file, "pacing_execution", "validate", "ok", 0.0, "",
              _versions(),
              {"ops": len(timeline.operations),
               "expected_s": timeline.expected_duration})
    try:
        out, (encoder, enc_reason) = _execute_ops(
            timeline, {}, project.input_path, info, config, dst, work, log_file)
    except RenderError as exc:
        mark_stage(project, "pacing_execution", "failed", str(exc)[:300])
        log_event(log_file, "pacing_execution", "execute", "failed",
                  time.perf_counter() - t0, str(exc)[:300], _versions(), {})
        raise
    qc = extended_qc(out, project.input_path, timeline, {}, config,
                     encoder, info, timeout=config.timeout, log_file=log_file)
    proc_s = round(time.perf_counter() - t0, 3)
    from engine.subtitles.render import apply_captions
    keeps4 = [(o.source_start, o.source_end, o.output_start, o.output_end)
              for o in timeline.operations if o.action == "keep"]
    final_output = str(out)
    caption_section: dict = {}
    if qc["verdict"] != "pass":
        manifest = _manifest(pid, project, info, approval, bundle, plan,
                             derived_edl, timeline, identity, encoder,
                             enc_reason, config, final_output, qc, {},
                             proc_s, base_cached)
        _write_manifest(pid, project, manifest, final_output, log_file,
                        proc_s, status="qc_failed")
        raise RenderError(
            f"pacing QC failed: {qc.get('suggested_fix', '')}", stage="validate")
    try:
        cap = apply_captions(pid, str(out), keeps4, config, log_file)
    except RenderError as exc:
        mark_stage(project, "pacing_execution", "failed", str(exc)[:300])
        log_event(log_file, "pacing_execution", "captions", "failed",
                  time.perf_counter() - t0, str(exc)[:300], _versions(), {})
        raise
    final_output = cap["output"]
    caption_section = {
        "caption_plan_hash": cap.get("caption_plan_hash", ""),
        "caption_style": cap.get("style", ""),
        "caption_mode": cap.get("mode", ""),
        "caption_font": cap.get("font", {}),
        "caption_count": cap.get("cue_count", 0),
        "caption_language": cap.get("language", ""),
        "caption_warnings": cap.get("warnings", []),
        "caption_qc": cap.get("caption_qc", {}),
        "caption_files": cap.get("files", {}),
        "visual_plan_hash": cap.get("visual_plan_hash", ""),
        "visual_approval": cap.get("visual_approval", "absent"),
        "visual_placements": cap.get("visual_placements", 0),
        "visual_emphasis_cues": cap.get("visual_emphasis_cues", 0)}
    log_event(log_file, "pacing_execution", "captions", "ok",
              time.perf_counter() - t0, final_output, _versions(),
              {"mode": cap.get("mode", ""), "cues": cap.get("cue_count", 0)})
    manifest = _manifest(pid, project, info, approval, bundle, plan,
                         derived_edl, timeline, identity, encoder,
                         enc_reason, config, final_output, qc,
                         caption_section, proc_s, base_cached)
    _write_manifest(pid, project, manifest, final_output, log_file, proc_s,
                    status="completed")
    _mark_executed(pid, project)
    return {"project": pid, "cached": manifest["cached"],
            "manifest": manifest, "output": final_output}


def asdict_config(config) -> dict:
    from dataclasses import asdict as _asdict
    return _asdict(config)


def _manifest(pid: str, project, info, approval: dict, bundle: dict,
              plan: PacingExecutionPlan, derived_edl: dict,
              timeline, identity: dict, encoder: str, enc_reason: str,
              config, final_output: str, qc: dict, caption_section: dict,
              proc_s: float, base_cached: bool) -> dict:
    import json
    from engine.core.media import probe
    from engine.rendering.plan_execute import _exec_hash
    payload = asdict(plan)
    recs = bundle["pacing"]["plan"].get("recommendations", [])
    planning_only = sorted(str(r.get("recommendation_id", "")) for r in recs
                           if str(r.get("action", "")) not in EXECUTABLE_ACTIONS)
    return {
        "kind": "pacing-execution",
        "status": "completed" if qc["verdict"] == "pass" else "qc_failed",
        "project": pid, "source": project.input_path,
        "source_hash": approval["source_hash"],
        "base_edl_hash": edl_hash(bundle["edl"]),
        "base_approval_hash": identity["base_approval_hash"],
        "caption_plan_hash": approval["caption_plan_hash"],
        "caption_approval_hash": approval["caption_approval_hash"],
        "visual_caption_plan_hash": approval["visual_caption_plan_hash"],
        "visual_caption_approval_hash": approval["visual_caption_approval_hash"],
        "pacing_plan_hash": approval["pacing_plan_hash"],
        "pacing_approval_hash": approval["pacing_approval_hash"],
        "pacing_execution_approval_hash": identity["pacing_execution_approval_hash"],
        "derived_edl_hash": approval["derived_edl_hash"],
        "execution_plan_hash": approval["execution_plan_hash"],
        "execution_hash": plan.execution_hash,
        "code_version": identity["code_version"],
        "timeline_execution_hash": _exec_hash(timeline),
        "execution_version": identity["execution_version"],
        "renderer_version": identity["renderer_version"],
        "gateway_version": "ffmpeg-gateway-1.0",
        "style": approval.get("style", ""),
        "encoder": encoder, "encoder_reason": enc_reason,
        "render_config": identity["render_config"],
        "operations": [asdict(o) for o in timeline.operations],
        "pacing_ops": payload["execution_ops"],
        "rejected_ops": payload["rejected_ops"],
        "recommendations_approved": approval["approved_recommendation_ids"],
        "recommendations_executed": [
            o["recommendation_id"] for o in payload["execution_ops"]],
        "recommendations_rejected": approval["rejected_recommendation_ids"],
        "recommendations_planning_only": planning_only,
        "output": final_output, "output_name": Path(final_output).name,
        "source_duration": info.duration,
        "expected_duration": timeline.expected_duration,
        "actual_duration": round(probe(final_output).duration, 3)
        if Path(final_output).is_file() else 0.0,
        "warnings": payload["warnings"], "qc": qc,
        "processing_s": proc_s,
        "realtime_factor": round(timeline.expected_duration / proc_s, 2)
        if proc_s > 0 else 0.0,
        "cached": bool(base_cached),
        **caption_section}


def _write_manifest(pid: str, project, manifest: dict, final_output: str,
                    log_file: Path, proc_s: float, status: str):
    import json
    (project_dir(pid) / "renders" /
     (Path(final_output).stem + "_pacing_manifest.json")).write_text(
        json.dumps(manifest, indent=2), encoding="utf-8")
    mark_stage(project, "pacing_execution",
               "done" if status == "completed" else "validation_failed",
               f"renders/{Path(final_output).stem}_pacing_manifest.json")
    log_event(log_file, "pacing_execution", "qc",
              "ok" if status == "completed" else "failed",
              proc_s, final_output, _versions(),
              {"expected_s": manifest["expected_duration"],
               "actual_s": manifest["actual_duration"],
               "qc": manifest["qc"]["verdict"]})
    if status != "completed":
        raise RenderError(
            f"pacing QC failed: {manifest['qc'].get('suggested_fix', '')}",
            stage="validate")


def _mark_executed(pid: str, project):
    import json
    path = project_dir(pid) / "editing" / "approved_caption_pacing_execution.json"
    approval = json.loads(path.read_text(encoding="utf-8"))
    if approval.get("approval_state") != "EXECUTED":
        approval["approval_state"] = "EXECUTED"
        path.write_text(json.dumps(approval, indent=2), encoding="utf-8")
