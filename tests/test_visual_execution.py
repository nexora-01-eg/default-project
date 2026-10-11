"""Phase 24 tests — visual-op derivation, approval, validation, dry-run.

Pure/project tests only (no ffmpeg): derivation + approval + validation +
dry-run are fully verified. Media rendering is environment-blocked and
honestly absent (no stubs).
"""
import copy
import json
from pathlib import Path

import pytest

from engine.core.project_store import (
    create_project,
    project_dir,
    write_artifact,
)
from engine.editing import visual_execution as vx


FIX = Path(__file__).resolve().parents[1] / "tests" / "fixtures"


def _rec(rid, action, s, e, safety="SAFE"):
    return {"recommendation_id": rid, "action": action, "start": s,
            "end": e, "scene_id": 0, "priority": "medium", "confidence": 0.7,
            "reason": "t", "evidence": [{"k": "v"}],
            "supporting_signals": [], "safety_status": safety,
            "affected_caption_ids": []}


def _cand(rid, path, duration=10.0, prov="KNOWN", ver="PASS"):
    return {"recommendation_id": rid, "asset_id": f"asset-{rid}",
            "path": path, "duration": duration,
            "provenance_status": prov, "verification": ver}


def _project_with_pacing(recs):
    """Hand artifacts + real pacing approval carrying custom recs."""
    from engine.editing.caption_pacing import (
        _media_hash,
        _stable_hash,
        approve_caption_pacing,
    )
    from engine.subtitles.captions import approve_captions
    p = create_project(str(FIX / "tone_5s.mp4"))
    write_artifact(p.id, "analysis", "scenes.json",
                   {"scenes": [{"scene_id": 0, "start": 0, "end": 5}]})
    write_artifact(p.id, "edit", "edit_decision.json",
                   {"decisions": [{"decision_id": "k", "action": "KEEP",
                                    "start": 0, "end": 5, "reason": "t"}],
                    "duration": 5.0})
    write_artifact(p.id, "captions", "caption_plan.json",
                   {"schema_version": "caption-plan-1.0", "source": "t",
                    "transcript_hash": "h", "style": "default",
                    "language": "en", "expected_duration": 5.0,
                    "config": {}, "warnings": [], "cues": []})
    approve_captions(p.id, mode="sidecar")
    proot = project_dir(p.id)
    cap_plan = json.loads((proot / "captions" / "caption_plan.json")
                          .read_text(encoding="utf-8"))
    from engine.core.project_store import load_project
    src = load_project(p.id).input_path
    plan = {"source_hash": _media_hash(src), "edit_plan_hash": "none",
            "caption_plan_hash": _stable_hash(cap_plan),
            "visual_caption_plan_hash": "none", "style": "general",
            "signals": [], "recommendations": recs, "conflicts": [],
            "rejected": [], "safety_summary": {}, "statistics": {},
            "warnings": []}
    (proot / "editing" / "caption_pacing_plan.json").write_text(
        json.dumps(plan, indent=2), encoding="utf-8")
    approve_caption_pacing(p.id)
    return p.id


def test_derive_visual_ops():
    plan = {"recommendations": [
        _rec("r1", "CHANGE_VISUAL", 1.0, 2.0),
        _rec("r2", "ADD_CUTAWAY_OPPORTUNITY", 2.5, 3.5),
        _rec("r3", "TRIM", 0.0, 1.0),
        _rec("r4", "CHANGE_VISUAL", 3.0, 4.0, safety="UNSAFE")]}
    cands = [_cand("r1", str(FIX / "tone_5s.mp4")),
             _cand("r2", str(FIX / "tone_5s.mp4"))]
    ops, unf = vx.derive_visual_ops(plan, cands, 5.0)
    assert [o["op_id"] for o in ops] == ["vx_0001", "vx_0002"]
    assert ops[0]["mode"] == "VISUAL_REPLACE"
    assert ops[1]["mode"] == "CUTAWAY_OVERLAY"
    assert all(o["safety_status"] == "SAFE" for o in ops)
    reasons = {u["recommendation_id"]: u["reason"] for u in unf}
    assert reasons["r4"] == "safety is not SAFE"
    assert "r3" not in reasons  # non-visual recs ignored, not unfulfilled


def test_derive_unfulfilled_cases(tmp_path):
    plan = {"recommendations": [_rec("r1", "CHANGE_VISUAL", 1.0, 2.0),
                                _rec("r2", "CHANGE_VISUAL", 2.0, 3.0),
                                _rec("r3", "CHANGE_VISUAL", 3.0, 4.0),
                                _rec("r4", "CHANGE_VISUAL", 0.0, 4.9),
                                _rec("r5", "CHANGE_VISUAL", 9.0, 4.0)]}
    missing = str(tmp_path / "nope.mp4")
    cands = [_cand("r2", missing),
             _cand("r3", str(FIX / "tone_5s.mp4"),
                   prov="REVIEW_REQUIRED"),
             _cand("r4", str(FIX / "tone_5s.mp4"), duration=1.0)]
    ops, unf = vx.derive_visual_ops(plan, cands, 5.0)
    assert ops == []
    by_id = {u["recommendation_id"]: u["reason"] for u in unf}
    assert by_id["r1"] == "no bound asset candidate"
    assert by_id["r2"] == "candidate file missing"
    assert by_id["r3"] == "candidate provenance REVIEW_REQUIRED"
    assert by_id["r4"] == "candidate shorter than span"
    assert by_id["r5"] == "invalid source range"


def test_derive_deterministic():
    plan = {"recommendations": [_rec("b", "CHANGE_VISUAL", 2.0, 3.0),
                                _rec("a", "ADD_CUTAWAY_OPPORTUNITY", 1.0, 2.0)]}
    cands = [_cand("a", str(FIX / "tone_5s.mp4")),
             _cand("b", str(FIX / "tone_5s.mp4"))]
    assert vx.derive_visual_ops(plan, cands, 5.0) == \
        vx.derive_visual_ops(plan, copy.deepcopy(cands), 5.0)


def test_approval_validation_dryrun():
    pid = _project_with_pacing([_rec("r1", "CHANGE_VISUAL", 1.0, 2.0),
                                _rec("r2", "ADD_CUTAWAY_OPPORTUNITY", 2.5, 3.5)])
    cands = [_cand("r1", str(FIX / "tone_5s.mp4")),
             _cand("r2", str(FIX / "tone_5s.mp4"))]
    with pytest.raises(vx.VisualExecutionError):
        vx.approve_visual_ops(pid, candidates=cands)  # nothing implicit
    with pytest.raises(vx.VisualExecutionError):
        vx.approve_visual_ops(pid, op_ids=["vx_9999"], candidates=cands)
    res = vx.approve_visual_ops(pid, op_ids=["vx_0001"], candidates=cands)
    assert res["approval"]["approved_op_ids"] == ["vx_0001"]
    assert res["approval"]["approval_state"] == "APPROVED"
    assert vx.validate_visual_approval(pid)["approval"]
    dry = vx.dry_run_visual_execution(pid)
    assert dry["dry_run"] is True
    assert [o["op_id"] for o in dry["ops"]] == ["vx_0001"]
    # dry-run writes nothing new
    proot = project_dir(pid)
    assert not list((proot / "renders").glob("*.mp4"))


def test_approval_drift():
    pid = _project_with_pacing([_rec("r1", "CHANGE_VISUAL", 1.0, 2.0)])
    cands = [_cand("r1", str(FIX / "tone_5s.mp4"))]
    vx.approve_visual_ops(pid, op_ids=["vx_0001"], candidates=cands)
    plan_path = project_dir(pid) / "editing" / "caption_pacing_plan.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    plan["recommendations"].append(_rec("rx", "TRIM", 0.0, 1.0))
    plan_path.write_text(json.dumps(plan), encoding="utf-8")
    with pytest.raises(vx.VisualExecutionError):
        vx.validate_visual_approval(pid)


def test_models():
    from dataclasses import asdict
    from engine.core.models import VisualApproval, VisualOp, VisualPlan
    assert asdict(VisualPlan())["schema_version"] == "visual-execution-plan-1.0"
    assert asdict(VisualApproval())["schema_version"] == \
        "visual-execution-approval-1.0"
    assert asdict(VisualOp(mode="VISUAL_REPLACE"))["mode"] == "VISUAL_REPLACE"
