"""Phase 13 approval tests — RECOMMENDED vs APPROVED boundary (no rendering)."""
import json
import subprocess
import sys
import time
from dataclasses import asdict
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests" / "fixtures"
SRC = str(FIX / "tone_5s.mp4")
BROLL = str(FIX / "broll_test.mp4")


@pytest.fixture(scope="module", autouse=True)
def fixtures():
    import shutil
    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg not on PATH")
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "make_test_media.py"), "--all"],
                       capture_output=True, text=True, timeout=600)
    assert r.returncode == 0, f"fixture build failed: {r.stderr[-1500:]}"
    assert (FIX / "broll_test.mp4").is_file()

from engine.core.models import BrollAsset, ExecutionOp, ExecutionPlanModel, PlanApproval
from engine.core.project_store import create_project, project_dir, write_artifact
from engine.editing.approval import (
    ApprovalError,
    approve_plan,
    load_approval,
    plan_hash,
    register_asset,
    validate_approval,
)


def _cut(did, s, e, verdict):
    return {"decision_id": did, "start": s, "end": e, "verdict": verdict,
            "base_action": "REMOVE", "priority": "medium", "confidence": 0.7,
            "factors": [], "alternatives": []}


def _broll(s, e, reason="visual_stagnation", recommended=True):
    return {"start": s, "end": e, "duration": e - s, "reason": reason,
            "desired_visual_type": "supporting_footage", "semantic_topic": "",
            "transcript_ref": {}, "priority": "medium", "recommended": recommended,
            "confidence": 0.6, "evidence": []}


def _jump(s, e, mitigations):
    return {"gap_start": s, "gap_end": e, "severity": "medium",
            "recommended_mitigations": mitigations, "priority": "medium",
            "confidence": 0.55, "evidence": []}


def _plan(cuts=(), broll=(), jumps=(), duration=5.0, source=None):
    return {"schema_version": "editor-plan-1.0", "project": "p", "source": source or SRC,
            "duration": duration,
            "editing_style": {"name": "general"}, "hook": {},
            "story_structure": [], "density_windows": [], "pacing_analysis": [],
            "cut_plan": list(cuts), "jump_strategy": list(jumps),
            "broll_plan": list(broll), "visual_change_plan": [], "audio_plan": [],
            "repetition_candidates": [], "quality_risks": [], "conflicts": [],
            "warnings": [], "evidence_index": [], "engine_version": "phase12-1.0",
            "processing_s": 0.0, "cached": False}


def _analyses():
    return {"audio_analysis.json": {"silence": []},
            "transcript.json": {"segments": []},
            "scenes.json": {"scenes": [{"scene_id": 0, "start": 0.0, "end": 5.0}]},
            "media_info.json": {"video_codec": "h264", "duration": 5.0}}


def _project(tag, plan, analyses=None, source=None, intel=None):
    p = create_project(source or SRC)
    for name, payload in (analyses if analyses is not None else _analyses()).items():
        write_artifact(p.id, "analysis", name, payload)
    write_artifact(p.id, "editing", "editor_plan.json", plan)
    if intel is not None:
        write_artifact(p.id, "edit", "edit_intelligence.json", intel)
    hook_tag = f"{tag}_{time.time_ns()}"
    (project_dir(p.id) / "tag.txt").write_text(hook_tag)
    return p


def test_model_serialization():
    a = BrollAsset(asset_id="b1", path="/x.mp4", media_hash="ab",
                   duration=4.0, width=640, height=360, fps=30.0, has_audio=True,
                   source_type="local", validation_status="valid")
    d = asdict(a)
    assert d["source_type"] == "local" and d["validation_status"] == "valid"
    assert set(asdict(PlanApproval())) >= {"plan_hash", "approved_cuts",
                                           "broll_assignments", "status"}
    assert set(asdict(ExecutionOp())) >= {"operation_id", "source_start",
                                          "output_start", "layer", "approval_state"}
    assert set(asdict(ExecutionPlanModel())) >= {"operations", "expected_duration",
                                                 "assets"}


def test_approval_creation():
    p = _project("t", _plan(cuts=[_cut("edl_0001", 1, 2, "approve"),
                                  _cut("edl_0002", 3, 4, "approve_with_mitigation")]))
    res = approve_plan(p.id)
    a = res["approval"]
    assert {c["decision_id"] for c in a["approved_cuts"]} == {"edl_0001", "edl_0002"}
    assert a["status"] == "approved" and a["schema_version"] == "approval-1.0"
    assert (project_dir(p.id) / "editing" / "approved_edit_plan.json").is_file()
    assert validate_approval(p.id)["approval"] == a  # roundtrip


def test_non_approved_verdicts_never_execute():
    p = _project("t", _plan(cuts=[_cut("a", 1, 2, "reject"),
                                  _cut("b", 2, 3, "downgrade_keep"),
                                  _cut("c", 3, 4, "investigate")]))
    a = approve_plan(p.id)["approval"]
    assert a["approved_cuts"] == []


def test_unsafe_cut_skipped_by_default_explicit_fails():
    intel = {"cut_safety": [{"decision_id": "edl_0001", "status": "UNSAFE",
                             "evidence": []}]}
    p = _project("t", _plan(cuts=[_cut("edl_0001", 1, 2, "approve"),
                                  _cut("edl_0002", 3, 4, "approve")]))
    write_artifact(p.id, "edit", "edit_intelligence.json", intel)
    a = approve_plan(p.id)["approval"]
    assert [c["decision_id"] for c in a["approved_cuts"]] == ["edl_0002"]
    assert any("UNSAFE" in w for w in a["warnings"])
    with pytest.raises(ApprovalError, match="UNSAFE"):
        approve_plan(p.id, include=["edl_0001"])


def test_plan_change_invalidates():
    p = _project("t", _plan(cuts=[_cut("edl_0001", 1, 2, "approve")]))
    approve_plan(p.id)
    plan = json.loads((project_dir(p.id) / "editing" / "editor_plan.json").read_text())
    plan["cut_plan"].append(_cut("edl_0009", 0, 1, "approve"))
    (project_dir(p.id) / "editing" / "editor_plan.json").write_text(json.dumps(plan))
    with pytest.raises(ApprovalError, match="plan changed"):
        validate_approval(p.id)


def test_source_change_invalidates(tmp_path):
    target = tmp_path / "src.mp4"
    target.write_bytes((FIX / "tone_5s.mp4").read_bytes())
    p = _project("t", _plan(), analyses=None)
    # Re-point project at the tmp copy, then approve.
    from engine.core.project_store import load_project, save_project
    proj = load_project(p.id)
    proj.input_path = str(target)
    save_project(proj)
    approve_plan(p.id)
    with target.open("r+b") as fh:
        fh.write(b"\x00")
    with pytest.raises(ApprovalError, match="source"):
        validate_approval(p.id)


def test_analysis_change_invalidates():
    p = _project("t", _plan())
    approve_plan(p.id)
    write_artifact(p.id, "analysis", "audio_analysis.json", {"silence": [{"a": 1}]})
    with pytest.raises(ApprovalError, match="audio_analysis"):
        validate_approval(p.id)


def test_missing_and_invalid_approval():
    p = create_project(SRC)
    with pytest.raises(ApprovalError, match="approval"):
        load_approval(p.id)
    with pytest.raises(ApprovalError, match="approval"):
        validate_approval(p.id)
    (project_dir(p.id) / "editing").mkdir(parents=True, exist_ok=True)
    (project_dir(p.id) / "editing" / "approved_edit_plan.json").write_text("{bad")
    with pytest.raises(ApprovalError):
        load_approval(p.id)


def test_broll_valid_asset_and_mapping():
    p = _project("t", _plan(broll=[_broll(0, 12)]))
    res = approve_plan(p.id, broll_map=[f"0-4={BROLL}"])
    a = res["approval"]
    assert len(a["broll_assignments"]) == 1
    asn = a["broll_assignments"][0]
    assert asn["asset_path"] == BROLL and asn["audio_mode"] == "mute"
    assert asn["fit"] == "cover" and asn["asset_end"] == 4.0
    assert asn["opportunity"] == {"start": 0, "end": 12, "kind": "opportunity"}
    assert asn["asset_hash"]
    assert a["status"] == "approved"


def test_broll_missing_invalid_short_long():
    p = _project("t", _plan(broll=[_broll(0, 12)]))
    with pytest.raises(ApprovalError, match="not found"):
        approve_plan(p.id, broll_map=["0-4=/nope/missing.mp4"])
    txt = ROOT / "projects" / p.id / "note.txt"
    txt.write_text("not media")
    with pytest.raises(ApprovalError, match="invalid"):
        approve_plan(p.id, broll_map=["0-4=" + str(txt)])
    with pytest.raises(ApprovalError, match="too short"):
        approve_plan(p.id, broll_map=["0-10=" + BROLL])  # asset is 4 s
    ok = approve_plan(p.id, broll_map=["0-2=" + BROLL])  # long asset trimmed
    assert ok["approval"]["broll_assignments"][0]["asset_end"] == 2.0


def test_broll_fit_audio_modes_and_ambiguous():
    p = _project("t", _plan(broll=[_broll(0, 12), _broll(0, 6)]))
    with pytest.raises(ApprovalError, match="ambiguous"):
        approve_plan(p.id, broll_map=["0-4=" + BROLL])
    res = approve_plan(p.id, broll_map=["8-10=" + BROLL],
                       broll_fit="contain", broll_audio="original")
    asn = res["approval"]["broll_assignments"][0]
    assert (asn["fit"], asn["audio_mode"]) == ("contain", "original")
    with pytest.raises(ApprovalError, match="unsupported.*mix"):
        approve_plan(p.id, broll_map=["8-10=" + BROLL], broll_audio="mix")
    with pytest.raises(ApprovalError, match="unsupported.*duck"):
        approve_plan(p.id, broll_map=["8-10=" + BROLL], broll_audio="duck")
    with pytest.raises(ApprovalError, match="unsupported.*fit"):
        approve_plan(p.id, broll_map=["8-10=" + BROLL], broll_fit="stretch")


def test_jump_mitigations_gated():
    p = _project("t", _plan(jumps=[_jump(1, 2, ["accept_cut", "reframe_later", "broll"])]))
    a = approve_plan(p.id)["approval"]
    j = a["jump_approvals"][0]
    assert j["approved_mitigations"] == ["accept_cut"]
    assert "reframe_later" in j["unsupported"]


def test_register_asset_fields():
    a = register_asset(BROLL, asset_id="city")
    assert a.asset_id == "city" and a.source_type == "local"
    assert (a.duration, a.width, a.height) == (4.0, 640, 360)
    assert a.has_audio is True and a.validation_status == "valid"
    assert a.media_hash and a.aspect_ratio == "640:360"
    with pytest.raises(ApprovalError, match="not found"):
        register_asset("/nope/x.mp4")


def test_cli_approve_plan(capsys):
    from engine.cli import main
    p = _project("t", _plan(cuts=[_cut("edl_0001", 1, 2, "approve")]))
    assert main(["approve-plan", p.id]) == 0
    out = capsys.readouterr().out
    assert "cuts    : 1 approved" in out
    assert main(["approve-plan", "project_nope_123"]) == 2
    q = create_project(SRC)  # no editor plan
    assert main(["approve-plan", q.id]) == 2
