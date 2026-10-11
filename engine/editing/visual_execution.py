"""Phase 24 — approval-gated visual execution derivation (adapter only).

Consumes CHANGE_VISUAL / ADD_CUTAWAY_OPPORTUNITY pacing recommendations plus
explicitly bound asset candidates, and derives deterministic, traceable,
reversible visual operations. Approval-gated: nothing executes without
editing/approved_visual_ops.json. Never mutates source media, the base EDL,
or Phase 17 behavior (untouched).

Render note: media rendering requires the FFmpeg binary, which is absent on
this machine. Derivation, approval, validation, and dry-run are fully
verified; the render step is explicitly out of scope until FFmpeg exists
(see module docstring + phase-24 report). No render stubs are provided.
"""
from __future__ import annotations

import time
from dataclasses import asdict

from engine.core.logging_utils import log_event
from engine.core.models import VisualApproval, VisualOp, VisualPlan
from engine.core.project_store import (
    load_project,
    mark_stage,
    project_dir,
    write_artifact,
)

VISUAL_VERSION = "1.0.0"
ENGINE_TAG = "phase24-1.0"
VISUAL_APPROVAL_SCHEMA = "visual-execution-approval-1.0"
VISUAL_ACTIONS = ("CHANGE_VISUAL", "ADD_CUTAWAY_OPPORTUNITY")
ACTION_TO_VISUAL_MODE = {
    "CHANGE_VISUAL": "VISUAL_REPLACE",
    "ADD_CUTAWAY_OPPORTUNITY": "CUTAWAY_OVERLAY",
}


class VisualExecutionError(RuntimeError):
    """Derivation/approval/validation failure (CLI exit 2)."""


def _r6(x: float) -> float:
    return round(float(x), 6)


def _hex(payload) -> str:
    import hashlib
    import json as _json
    return hashlib.sha256(
        _json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()[:32]


def _load_json(path, what: str, required: bool = True):
    import json
    if not path.is_file():
        if required:
            raise VisualExecutionError(f"missing {what} ({path.name})")
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise VisualExecutionError(f"corrupt {what}: {exc}") from exc


def derive_visual_ops(pacing_plan: dict, candidates: list[dict],
                      duration: float) -> tuple[list[dict], list[dict]]:
    """Derive ops from visual recommendations + explicitly bound candidates.

    Returns (ops, unfulfilled). Candidates bind by recommendation_id only —
    never by guess. Deterministic: sorted input, stable op ids.
    """
    import os
    recs = sorted(pacing_plan.get("recommendations", []) or [],
                  key=lambda r: (float(r.get("start", 0.0)),
                                 str(r.get("recommendation_id", ""))))
    by_rec: dict[str, list[dict]] = {}
    for c in candidates:
        by_rec.setdefault(str(c.get("recommendation_id", "")), []).append(c)
    ops, unfulfilled = [], []
    for rec in recs:
        rid = str(rec.get("recommendation_id", ""))
        action = str(rec.get("action", ""))
        if action not in VISUAL_ACTIONS:
            continue
        s, e = float(rec.get("start", 0.0)), float(rec.get("end", 0.0))
        base = {"recommendation_id": rid, "action": action,
                "source_start": s, "source_end": e}
        if rec.get("safety_status") != "SAFE":
            unfulfilled.append({**base, "reason": "safety is not SAFE"})
            continue
        if not (0 <= s < e <= duration + 0.05):
            unfulfilled.append({**base, "reason": "invalid source range"})
            continue
        cands = sorted(by_rec.get(rid, []),
                       key=lambda c: str(c.get("asset_id", "")))
        if not cands:
            unfulfilled.append({**base, "reason": "no bound asset candidate"})
            continue
        c = cands[0]
        if c.get("verification") == "REJECT":
            unfulfilled.append({**base, "reason": "candidate verification REJECT",
                                "asset_id": c.get("asset_id", "")})
            continue
        if c.get("provenance_status") == "REVIEW_REQUIRED":
            unfulfilled.append({**base, "reason": "candidate provenance REVIEW_REQUIRED",
                                "asset_id": c.get("asset_id", "")})
            continue
        path = str(c.get("path", ""))
        if not path or not os.path.isfile(path):
            unfulfilled.append({**base, "reason": "candidate file missing",
                                "asset_id": c.get("asset_id", "")})
            continue
        if c.get("duration") is not None and \
                float(c["duration"]) + 1e-3 < e - s:
            unfulfilled.append({**base, "reason": "candidate shorter than span",
                                "asset_id": c.get("asset_id", "")})
            continue
        ops.append({**base, "asset_id": str(c.get("asset_id", "")),
                    "asset_path": path,
                    "mode": ACTION_TO_VISUAL_MODE[action],
                    "safety_status": "SAFE",
                    "confidence": float(rec.get("confidence", 0.0)),
                    "reason": f"approved visual {action} [{s}, {e}]",
                    "evidence": list(rec.get("evidence", []) or [])})
    ops.sort(key=lambda o: (o["source_start"], o["recommendation_id"]))
    for i, o in enumerate(ops, 1):
        o["op_id"] = f"vx_{i:04d}"
    return ops, unfulfilled


def _plan_hash(ops: list[dict], unfulfilled: list[dict],
               pacing_hashes: dict) -> str:
    return _hex({"ops": ops, "unfulfilled": unfulfilled,
                 "pacing": pacing_hashes, "version": VISUAL_VERSION})


def approve_visual_ops(project_id: str, op_ids: list[str] | None = None,
                       candidates: list[dict] | None = None,
                       approver: str = "operator") -> dict:
    """Explicit approval of derived visual ops. Fails loudly on any gap."""
    from engine.editing.caption_pacing import validate_caption_pacing_approval
    project = load_project(project_id)
    pid = project.id
    log_file = project_dir(pid) / "logs" / "run.jsonl"
    t0 = time.perf_counter()
    try:
        pacing = validate_caption_pacing_approval(pid)
    except Exception as exc:
        raise VisualExecutionError(f"pacing approval invalid: {exc}") from exc
    edl = _load_json(project_dir(pid) / "edit" / "edit_decision.json",
                     "base EDL (run edit first)")
    duration = float(edl.get("duration") or 0)
    if duration <= 0:
        raise VisualExecutionError("base EDL has no usable duration")
    ops, unfulfilled = derive_visual_ops(pacing["plan"], candidates or [],
                                         duration)
    by_id = {o["op_id"]: o for o in ops}
    if not op_ids:
        raise VisualExecutionError(
            "select operations explicitly; nothing is approved implicitly")
    seen, approved = set(), []
    for oid in op_ids:
        if oid in seen:
            continue
        seen.add(oid)
        if oid not in by_id:
            raise VisualExecutionError(f"unknown visual op {oid!r}")
        approved.append(by_id[oid])
    from engine.editing.caption_pacing_execution import _hex as _stable
    plan_obj = VisualPlan(
        project_id=pid,
        pacing_plan_hash=_stable({k: v for k, v in pacing["plan"].items()}),
        pacing_approval_hash=_stable({k: v for k, v in pacing["approval"].items()
                                      if k != "approved_at"}),
        execution_ops=[VisualOp(
            op_id=o["op_id"], recommendation_id=o["recommendation_id"],
            action=o["action"], source_start=o["source_start"],
            source_end=o["source_end"], asset_id=o["asset_id"],
            asset_path=o["asset_path"], mode=o["mode"],
            safety_status=o["safety_status"], confidence=o["confidence"],
            reason=o["reason"], evidence=o["evidence"]) for o in approved],
        unfulfilled=unfulfilled)
    payload = asdict(plan_obj)
    payload["execution_hash"] = _hex(
        {k: v for k, v in payload.items() if k != "execution_hash"})
    approval = VisualApproval(
        project_id=pid,
        pacing_plan_hash=plan_obj.pacing_plan_hash,
        pacing_approval_hash=plan_obj.pacing_approval_hash,
        approved_op_ids=[o["op_id"] for o in approved],
        execution_hash=payload["execution_hash"],
        approver=approver)
    import datetime
    approval.approved_at = datetime.datetime.now(
        datetime.timezone.utc).isoformat()
    apayload = asdict(approval)
    write_artifact(pid, "editing", "approved_visual_ops.json", apayload)
    write_artifact(pid, "editing", "visual_execution_plan.json", payload)
    mark_stage(project, "visual_execution_approval", "done",
               "editing/approved_visual_ops.json")
    log_event(log_file, "visual_execution", "approve", "ok",
              time.perf_counter() - t0,
              "editing/approved_visual_ops.json",
              {"engine": ENGINE_TAG},
              {"approved": len(approved), "unfulfilled": len(unfulfilled)})
    return {"project": pid, "approval": apayload, "plan": payload}


def validate_visual_approval(project_id: str) -> dict:
    """Revalidate all bindings. Returns {approval, plan} or raises."""
    from engine.editing.caption_pacing import validate_caption_pacing_approval
    from engine.editing.caption_pacing_execution import _hex as _stable
    project = load_project(project_id)
    pid = project.id
    approval = _load_json(
        project_dir(pid) / "editing" / "approved_visual_ops.json",
        "visual approval (run approve-visual-ops first)")
    if approval.get("schema_version") != VISUAL_APPROVAL_SCHEMA:
        raise VisualExecutionError("unsupported visual approval schema")
    try:
        pacing = validate_caption_pacing_approval(pid)
    except Exception as exc:
        raise VisualExecutionError(
            f"pacing approval invalid: {exc}") from exc
    if _stable({k: v for k, v in pacing["plan"].items()}) != \
            approval.get("pacing_plan_hash"):
        raise VisualExecutionError("pacing plan changed: re-approve visual ops")
    if _stable({k: v for k, v in pacing["approval"].items()
                if k != "approved_at"}) != approval.get("pacing_approval_hash"):
        raise VisualExecutionError("pacing approval changed: re-approve visual ops")
    plan = _load_json(project_dir(pid) / "editing" / "visual_execution_plan.json",
                      "visual execution plan")
    if _hex({k: v for k, v in plan.items()
             if k != "execution_hash"}) != approval.get("execution_hash"):
        raise VisualExecutionError("visual plan changed: re-approve visual ops")
    return {"approval": approval, "plan": plan}


def dry_run_visual_execution(project_id: str) -> dict:
    """Preview only. Writes nothing."""
    checked = validate_visual_approval(project_id)
    approval, plan = checked["approval"], checked["plan"]
    return {"project": project_id,
            "approved_op_ids": approval["approved_op_ids"],
            "ops": plan["execution_ops"],
            "unfulfilled": plan["unfulfilled"],
            "dry_run": True}
