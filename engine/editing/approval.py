"""Phase 13 — explicit approval boundary: RECOMMENDED -> APPROVED (-> EXECUTED).

The Editor Brain never authorizes rendering. This module snapshots WHAT was
approved (cuts, B-roll assignments, jump mitigations) with hashes that make
any later change (plan, source, analyses, assets) invalidate the approval.
Timestamps are informational only and never hashed.
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict
from pathlib import Path

from engine.core.logging_utils import log_event
from engine.core.media import MediaProbeError, probe
from engine.core.models import BrollAsset, PlanApproval
from engine.core.pipeline import cache_key, cached, store
from engine.core.project_store import (
    load_project,
    mark_stage,
    project_dir,
    write_artifact,
)
from engine.editing.decisions import hash_analysis

APPROVAL_VERSION = "approval-1.0"
_HASH_SAMPLE_BYTES = 4 * 1024 * 1024


class ApprovalError(RuntimeError):
    pass


def _versions() -> dict:
    import platform
    return {"python": platform.python_version(), "engine": "0.1.0"}


def file_pin(path: str | Path) -> dict:
    """Content pin: size + mtime + sha256(first 4 MB). Missing -> ApprovalError."""
    p = Path(path)
    if not p.is_file():
        raise ApprovalError(f"file not found: {p}")
    try:
        st = p.stat()
        h = hashlib.sha256()
        with p.open("rb") as fh:
            h.update(fh.read(_HASH_SAMPLE_BYTES))
        return {"path": str(p), "size": st.st_size, "mtime_ns": st.st_mtime_ns,
                "media_hash": h.hexdigest()[:32]}
    except OSError as exc:
        raise ApprovalError(f"unreadable file {p}: {exc}") from exc


def source_fingerprint(path: str | Path) -> dict:
    return file_pin(path)


def asset_hash(path: str | Path) -> str:
    return file_pin(path)["media_hash"]


def plan_hash(plan: dict) -> str:
    canonical = {k: v for k, v in plan.items() if k not in ("processing_s", "cached")}
    return hashlib.sha256(
        json.dumps(canonical, sort_keys=True, default=str).encode()).hexdigest()[:32]


def register_asset(path: str | Path, asset_id: str = "") -> BrollAsset:
    """Validate a local asset file and describe it. Invalid -> status invalid
    (caller decides fail vs skip); missing -> ApprovalError."""
    p = Path(path)
    if not p.is_file():
        raise ApprovalError(f"B-roll asset not found: {p}")
    pin = file_pin(p)
    try:
        info = probe(p)
    except MediaProbeError as exc:
        return BrollAsset(asset_id=asset_id or p.stem, path=str(p),
                          media_hash=pin["media_hash"], source_type="local",
                          validation_status="invalid",
                          validation_errors=[str(exc)])
    errors: list[str] = []
    if not info.video_codec:
        errors.append("no video stream")
    if info.duration <= 0:
        errors.append("unknown duration")
    w, h, fps = info.width, info.height, info.fps
    return BrollAsset(
        asset_id=asset_id or p.stem, path=str(p), media_hash=pin["media_hash"],
        duration=round(info.duration, 3), width=w, height=h,
        fps=round(fps, 3), has_audio=bool(info.audio_codec),
        source_type="local",
        aspect_ratio=f"{w}:{h}" if w and h else "",
        codec=info.video_codec or "", pixel_format="",
        validation_status="valid" if not errors else "invalid",
        validation_errors=errors,
        metadata={"size": pin["size"], "mtime_ns": pin["mtime_ns"]})


def _load_json(path: Path, what: str) -> dict:
    if not path.is_file():
        raise ApprovalError(f"missing {what} ({path.name})")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ApprovalError(f"corrupt {what}: {exc}") from exc


def _parse_broll_map(entries: list[str]) -> list[dict]:
    """Parse ["START-END=PATH[@OFFSET]", ...] into assignment requests."""
    out = []
    for entry in entries or []:
        try:
            span, rest = entry.split("=", 1)
            s_raw, e_raw = span.split("-", 1)
            if "@" in rest:
                path_raw, off_raw = rest.rsplit("@", 1)
                offset = float(off_raw)
            else:
                path_raw, offset = rest, 0.0
            s, e = float(s_raw), float(e_raw)
        except ValueError:
            raise ApprovalError(f"bad --broll-map entry {entry!r}: "
                                f"expected START-END=PATH[@OFFSET]") from None
        if not e > s:
            raise ApprovalError(f"bad --broll-map span in {entry!r}")
        if offset < 0:
            raise ApprovalError(f"negative asset offset in {entry!r}")
        out.append({"start": s, "end": e, "path": path_raw, "offset": offset})
    return out


def _match_span(request: dict, candidates: list[dict], tol: float = 0.05) -> dict | None:
    """Match a request span to the opportunity/jump gap CONTAINING it.

    Partial mapping is allowed (a 4 s asset may cover the first 4 s of a
    12 s opportunity); the executed span is always the request span itself.
    Ambiguous containment across several candidates is an error.
    """
    hits = [c for c in candidates
            if float(c["start"]) - tol <= request["start"]
            and request["end"] <= float(c["end"]) + tol]
    if len(hits) > 1:
        raise ApprovalError(f"ambiguous --broll-map span {request['start']}-"
                            f"{request['end']}: contained in {len(hits)} opportunities")
    return hits[0] if hits else None


def approve_plan(project_id: str, *, include: list[str] | None = None,
                 exclude: list[str] | None = None,
                 broll_map: list[str] | None = None,
                 broll_audio: str = "mute", broll_fit: str = "cover",
                 approver: str = "operator") -> dict:
    """Create the immutable approval snapshot. Returns {project, approval}."""
    if broll_audio not in ("mute", "original"):
        raise ApprovalError(f"unsupported B-roll audio mode {broll_audio!r} "
                            f"in Phase 13 (mute|original only; mix/duck unsupported)")
    if broll_fit not in ("cover", "contain", "crop", "letterbox"):
        raise ApprovalError(f"unsupported fit {broll_fit!r} "
                            f"(cover|contain|crop|letterbox only)")
    project = load_project(project_id)
    pid = project.id
    log_file = project_dir(pid) / "logs" / "run.jsonl"
    t0 = time.perf_counter()

    plan = _load_json(project_dir(pid) / "editing" / "editor_plan.json",
                      "editor plan (run editor-plan first)")
    if plan.get("schema_version") != "editor-plan-1.0":
        raise ApprovalError(f"unsupported editor plan schema "
                            f"{plan.get('schema_version')!r}")
    try:
        src_info = probe(project.input_path)
    except MediaProbeError as exc:
        raise ApprovalError(str(exc)) from exc
    fingerprint = source_fingerprint(project.input_path)

    analyses: dict[str, dict] = {}
    for name in ("audio_analysis.json", "transcript.json", "scenes.json"):
        p = project_dir(pid) / "analysis" / name
        if p.is_file():
            try:
                analyses[name] = json.loads(p.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                raise ApprovalError(f"corrupt analysis artifact {name}: {exc}") from exc
    analysis_hashes = {k: hash_analysis(v) for k, v in analyses.items()}

    intel_safety: dict[str, str] = {}
    intel_path = project_dir(pid) / "edit" / "edit_intelligence.json"
    if intel_path.is_file():
        try:
            intel = json.loads(intel_path.read_text(encoding="utf-8"))
            for s in intel.get("cut_safety", []) or []:
                intel_safety[str(s.get("decision_id"))] = str(s.get("status"))
        except json.JSONDecodeError:
            pass  # unreadable intelligence: safety unknown, cuts need verdicts anyway

    warnings: list[str] = []
    approved_cuts: list[dict] = []
    for cut in plan.get("cut_plan", []) or []:
        did, verdict = str(cut.get("decision_id", "")), str(cut.get("verdict", ""))
        if exclude and did in exclude:
            continue
        if include is not None and did not in include:
            continue
        safety = intel_safety.get(did, "unknown")
        if safety == "UNSAFE":
            if include is not None and did in include:
                raise ApprovalError(f"refusing explicit approval of UNSAFE cut {did}")
            warnings.append(f"UNSAFE cut {did} left unapproved")
            continue
        if verdict in ("approve", "approve_with_mitigation"):
            if verdict == "approve_with_mitigation":
                warnings.append(f"cut {did} approved WITHOUT mitigation "
                                f"(mitigations need separate asset mapping)")
            approved_cuts.append({"decision_id": did, "verdict": verdict,
                                  "start": cut.get("start"), "end": cut.get("end")})
        # reject / downgrade_keep / investigate / candidate_for_trim:
        # never executed (recorded implicitly by absence).

    assignments: list[dict] = []
    assets: dict[str, dict] = {}
    requests = _parse_broll_map(broll_map)
    opportunities = plan.get("broll_plan", []) or []
    jump_gaps = [{"start": j.get("gap_start"), "end": j.get("gap_end"),
                  "kind": "jump_gap",
                  "mitigations": j.get("recommended_mitigations", [])}
                 for j in plan.get("jump_strategy", []) or []]
    for req in requests:
        target = _match_span(req, opportunities)
        kind = "opportunity"
        if target is None:
            target = _match_span(req, jump_gaps)
            kind = "jump_gap"
        if target is None:
            raise ApprovalError(
                f"--broll-map span {req['start']}-{req['end']} matches no B-roll "
                f"opportunity or jump gap in the plan")
        asset = register_asset(req["path"])
        if asset.validation_status != "valid":
            raise ApprovalError(f"B-roll asset invalid {req['path']}: "
                                f"{'; '.join(asset.validation_errors)}")
        need = round(req["end"] - req["start"], 3)
        if req["offset"] + need > asset.duration + 1e-6:
            raise ApprovalError(f"B-roll asset {req['path']} too short: need "
                                f"{need}s from offset {req['offset']}s, asset "
                                f"is {asset.duration}s (no looping in Phase 13)")
        aid = asset.asset_id
        n = 2
        while aid in assets:
            aid = f"{asset.asset_id}_{n}"
            n += 1
        asset.asset_id = aid
        assets[aid] = asdict(asset)
        assignments.append({"opportunity": {"start": target["start"],
                                            "end": target["end"], "kind": kind},
                            "start": req["start"], "end": req["end"],
                            "asset_id": aid, "asset_path": asset.path,
                            "asset_hash": asset.media_hash,
                            "asset_start": req["offset"],
                            "asset_end": round(req["offset"] + need, 3),
                            "audio_mode": broll_audio, "fit": broll_fit,
                            "placement": "overlay"})

    jump_approvals: list[dict] = []
    for j in plan.get("jump_strategy", []) or []:
        ok = [m for m in (j.get("recommended_mitigations", []) or [])
              if m in ("accept_cut", "preserve_section")]
        unsupported = [m for m in (j.get("recommended_mitigations", []) or [])
                       if m not in ("accept_cut", "preserve_section", "broll",
                                    "cutaway", "alternate_visual")]
        jump_approvals.append({"gap_start": j.get("gap_start"),
                               "gap_end": j.get("gap_end"),
                               "approved_mitigations": ok,
                               "unsupported": [m for m in
                                               (j.get("recommended_mitigations", []) or [])
                                               if m in ("reframe_later", "transition_later")]
                               + unsupported})

    approval = PlanApproval(
        plan_hash=plan_hash(plan), source_fingerprint=fingerprint,
        analysis_hashes=analysis_hashes, approved_cuts=approved_cuts,
        broll_assignments=assignments, jump_approvals=jump_approvals,
        warnings=warnings, approver=approver)
    payload = asdict(approval)
    write_artifact(pid, "editing", "approved_edit_plan.json", payload)
    mark_stage(project, "approval", "done", "editing/approved_edit_plan.json")
    log_event(log_file, "approval", "approve", "ok", time.perf_counter() - t0,
              "editing/approved_edit_plan.json", _versions(),
              {"cuts": len(approved_cuts), "broll": len(assignments),
               "warnings": len(warnings)})
    return {"project": pid, "approval": payload}


def load_approval(project_id: str) -> dict:
    project = load_project(project_id)
    return _load_json(project_dir(project.id) / "editing" / "approved_edit_plan.json",
                      "approval (run approve-plan first)")


def validate_approval(project_id: str) -> dict:
    """Revalidate immutability: plan, source, analyses, assets. Returns
    {approval, plan} or raises ApprovalError naming the drift."""
    import json as _json
    project = load_project(project_id)
    pid = project.id
    approval = load_approval(pid)
    if approval.get("schema_version") != APPROVAL_VERSION:
        raise ApprovalError(f"unsupported approval schema "
                            f"{approval.get('schema_version')!r}")
    plan = _load_json(project_dir(pid) / "editing" / "editor_plan.json",
                      "editor plan")
    if plan_hash(plan) != approval.get("plan_hash"):
        raise ApprovalError("editor plan changed since approval: re-approve")
    if source_fingerprint(project.input_path) != approval.get("source_fingerprint"):
        raise ApprovalError("source media changed since approval: re-approve")
    for name, pinned in (approval.get("analysis_hashes", {}) or {}).items():
        p = project_dir(pid) / "analysis" / name
        if not p.is_file():
            raise ApprovalError(f"analysis artifact {name} vanished since approval")
        try:
            current = hash_analysis(_json.loads(p.read_text(encoding="utf-8")))
        except _json.JSONDecodeError as exc:
            raise ApprovalError(f"analysis artifact {name} unreadable: {exc}") from exc
        if current != pinned:
            raise ApprovalError(f"analysis artifact {name} changed since approval")
    for a in approval.get("broll_assignments", []) or []:
        current = file_pin(a["asset_path"])["media_hash"]
        if current != a.get("asset_hash"):
            raise ApprovalError(f"B-roll asset changed since approval: {a['asset_path']}")
    return {"approval": approval, "plan": plan}


def _versions() -> dict:
    import platform
    return {"python": platform.python_version(), "engine": "0.1.0"}
