"""Phase 17 pacing-execution tests — approval, EDL compat, mapping, CLI, E2E.

Pure/project tests use hand-written artifacts + real upstream approvals
(captions, pacing). Visual approvals are hand-forged with correct hashes
(real approve_caption_visual needs ffprobe). Render/media tests are
ffmpeg-gated and skip without a binary; preflight-failure tests run here.
"""
import copy
import json
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests" / "fixtures"

from engine.core.models import (
    PacingExecutionApproval,
    PacingExecutionOp,
    PacingExecutionPlan,
)
from engine.core.project_store import (
    create_project,
    load_project,
    project_dir,
    write_artifact,
)
from engine.editing import caption_pacing_execution as px
from engine.editing.caption_pacing import (
    _media_hash as _pacing_media_hash,
    _stable_hash as _pacing_stable_hash,
)


@pytest.fixture(scope="module", autouse=True)
def fixtures():
    for name in ("tone_5s.mp4", "speech_video.mp4"):
        assert (FIX / name).is_file(), f"missing fixture {name}"


@pytest.fixture()
def need_ffmpeg():
    import shutil
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        pytest.skip("ffmpeg/ffprobe not on PATH")


# ---------- builders ----------

def _w(text, s, e):
    return {"text": text, "start": s, "end": e, "probability": 0.9}


def _cue(cid, s, e, words):
    refs = [_w(t, ws, we) for t, ws, we in words]
    text = " ".join(t for t, _, _ in words)
    return {"cue_id": cid, "start": s, "end": e, "text": text, "lines": [text],
            "word_refs": refs, "language": "en", "confidence": 0.9}


def _base_cues():
    return [_cue("c1", 0.5, 1.8, [("hello", 0.5, 1.0), ("world", 1.2, 1.8)]),
            _cue("c2", 2.1, 2.9, [("gone", 2.1, 2.5), ("soon", 2.6, 2.9)]),
            _cue("c3", 3.5, 4.5, [("still", 3.5, 4.0), ("here", 4.1, 4.5)])]


def _base_edl():
    return {"decisions": [
        {"decision_id": "k1", "action": "KEEP", "start": 0.0, "end": 2.0, "reason": "t"},
        {"decision_id": "2.0", "action": "REMOVE", "start": 2.0, "end": 3.0, "reason": "t"},
        {"decision_id": "k2", "action": "KEEP", "start": 3.0, "end": 5.0, "reason": "t"}],
        "duration": 5.0}


def _base_transcript():
    return {"language": "en", "segments": [{
        "id": 0, "start": 0.5, "end": 4.5, "text": "hello world end. gone soon next here.",
        "words": [_w("hello", 0.5, 1.0), _w("world", 1.2, 1.8),
                  _w("end.", 1.85, 2.0), _w("gone", 2.1, 2.5),
                  _w("soon", 2.6, 2.9), _w("next", 3.5, 4.0),
                  _w("here.", 4.1, 4.5)]}]}


def _project_basic(cues=None, edl=None, transcript=None):
    """Hand artifacts + real caption/pacing approvals. Returns pid."""
    from engine.editing.caption_pacing import (
        approve_caption_pacing,
        run_caption_pacing_for_project,
    )
    from engine.subtitles.captions import approve_captions
    p = create_project(str(FIX / "tone_5s.mp4"))
    write_artifact(p.id, "analysis", "scenes.json",
                   {"scenes": [{"scene_id": 0, "start": 0, "end": 2.5},
                                {"scene_id": 1, "start": 2.5, "end": 5}]})
    write_artifact(p.id, "edit", "edit_decision.json", edl or _base_edl())
    write_artifact(p.id, "captions", "caption_plan.json",
                   {"schema_version": "caption-plan-1.0", "source": "t",
                    "transcript_hash": "h", "style": "default", "language": "en",
                    "expected_duration": 5.0, "config": {}, "warnings": [],
                    "cues": cues if cues is not None else _base_cues()})
    write_artifact(p.id, "analysis", "transcript.json",
                   transcript or _base_transcript())
    approve_captions(p.id, mode="sidecar")
    run_caption_pacing_for_project(p.id)
    approve_caption_pacing(p.id)
    return p.id


def _rec(rid, action, s, e, safety="SAFE", scene=-1):
    return {"recommendation_id": rid, "action": action, "start": s, "end": e,
            "scene_id": scene, "priority": "high" if action == "TRIM" else "medium",
            "confidence": 0.7, "reason": "t",
            "evidence": [{"kind": "probe", "source": "test"}],
            "supporting_signals": [], "safety_status": safety,
            "affected_caption_ids": []}


def _forge_pacing(pid, recs):
    """Hand-written pacing plan + real pacing approval (correct bindings)."""
    from engine.editing.caption_pacing import approve_caption_pacing
    proot = project_dir(pid)
    cap_plan = json.loads((proot / "captions" / "caption_plan.json")
                          .read_text(encoding="utf-8"))
    src = load_project(pid).input_path
    plan = {"source_hash": _pacing_media_hash(src),
            "edit_plan_hash": "none",
            "caption_plan_hash": _pacing_stable_hash(cap_plan),
            "visual_caption_plan_hash": "none",
            "style": "general",
            "signals": [], "recommendations": recs, "conflicts": [],
            "rejected": [], "safety_summary": {}, "statistics": {},
            "warnings": []}
    (proot / "editing" / "caption_pacing_plan.json").write_text(
        json.dumps(plan, indent=2), encoding="utf-8")
    return approve_caption_pacing(pid)


def _forge_visual(pid, placements):
    """Hand visual plan + approval with correct hashes (no ffprobe)."""
    from engine.subtitles.visual_captions import (
        _media_hash as _visual_media_hash,
        visual_plan_hash,
    )
    proot = project_dir(pid)
    cap_plan = json.loads((proot / "captions" / "caption_plan.json")
                          .read_text(encoding="utf-8"))
    src = load_project(pid).input_path
    plan = {"schema_version": "visual-caption-plan-1.0",
            "source_hash": _visual_media_hash(src),
            "caption_plan_hash": _pacing_stable_hash(cap_plan),
            "visual_analysis_hash": "none", "style": "default",
            "placements": placements, "emphasis": [], "contexts": [],
            "adaptations": {}, "conflicts": [], "warnings": [],
            "version": "1.0.0"}
    (proot / "captions" / "visual_caption_plan.json").write_text(
        json.dumps(plan, indent=2), encoding="utf-8")
    approval = {"schema_version": "visual-caption-approval-1.0",
                "source_hash": _visual_media_hash(src),
                "caption_plan_hash": plan["caption_plan_hash"],
                "visual_analysis_hash": "none", "style": "default",
                "font_identity": {},
                "visual_plan_hash": visual_plan_hash(plan)}
    (proot / "captions" / "approved_visual_caption_plan.json").write_text(
        json.dumps(approval, indent=2), encoding="utf-8")
    return approval


def _placement(cid, position="bottom"):
    y = {"bottom": 0.92, "center": 0.5, "top": 0.08}[position]
    anchor = {"bottom": "bottom-center", "center": "middle-center",
              "top": "top-center"}[position]
    return {"cue_id": cid, "position": position, "x": 0.5, "y": y,
            "anchor": anchor, "safe_area": {}, "reason": "style_default",
            "confidence": 0.5}


def _hashes(pid, names):
    proot = project_dir(pid)
    return {n: (proot / n).read_bytes() for n in names}


BASE_FILES = ["edit/edit_decision.json", "captions/caption_plan.json",
              "editing/approved_captions.json",
              "editing/caption_pacing_plan.json",
              "editing/approved_caption_pacing_plan.json"]


# ---------- 1. models ----------

def test_model_schemas():
    a = asdict(PacingExecutionApproval())
    assert a["schema_version"] == "pacing-execution-approval-1.0"
    assert a["approval_state"] == "APPROVED"
    o = asdict(PacingExecutionOp(action="TRIM", execution_mode="TRIM"))
    assert o["execution_mode"] == "TRIM"
    pl = asdict(PacingExecutionPlan())
    assert pl["schema_version"] == "caption-pacing-execution-plan-1.0"
    json.loads(json.dumps({"a": a, "o": o, "pl": pl}))
    assert set(px.ACTION_TO_MODE.values()) <= {
        "TRIM", "SPLIT", "VISUAL_CHANGE", "CUTAWAY_OPPORTUNITY", "HOLD", "NOOP"}


# ---------- 2. approval selection ----------

def test_explicit_approval_required():
    pid = _project_basic()
    with pytest.raises(px.PacingExecutionError):
        px.approve_caption_pacing_execution(pid)
    with pytest.raises(px.PacingExecutionError):
        px.approve_caption_pacing_execution(
            pid, recommendation_ids=["rec_0001"], all_safe=True)
    with pytest.raises(px.PacingExecutionError):
        px.approve_caption_pacing_execution(pid, recommendation_ids=["nope"])


def test_safe_trim_approved():
    pid = _project_basic()
    res = px.approve_caption_pacing_execution(pid, recommendation_ids=["rec_0001"])
    a = res["approval"]
    assert a["approved_recommendation_ids"] == ["rec_0001"]
    assert a["rejected_recommendation_ids"] == []
    assert a["approval_state"] == "APPROVED"
    assert a["generated_execution_policy"]["caption_mode"] == "sidecar"
    assert (project_dir(pid) / "editing" / "approved_caption_pacing_execution.json").is_file()
    assert (project_dir(pid) / "edit" / "caption_pacing_execution_plan.json").is_file()


def test_unapproved_recommendation_not_executed():
    pid = _project_basic()
    _forge_pacing(pid, [_rec("rec_a", "TRIM", 2.0, 3.0),
                        _rec("rec_b", "SPLIT", 4.0, 4.6)])
    res = px.approve_caption_pacing_execution(pid, recommendation_ids=["rec_a"])
    assert res["approval"]["approved_recommendation_ids"] == ["rec_a"]
    dry = px.dry_run_pacing_execution(pid)
    assert [o["recommendation_id"] for o in dry["executable_ops"]] == ["rec_a"]


def test_unsafe_rejected_and_all_safe_skips():
    pid = _project_basic()
    _forge_pacing(pid, [_rec("rec_u", "TRIM", 2.0, 3.0, safety="UNSAFE"),
                        _rec("rec_s", "TRIM", 2.0, 3.0)])
    with pytest.raises(px.PacingExecutionError):
        px.approve_caption_pacing_execution(pid, recommendation_ids=["rec_u"])
    res = px.approve_caption_pacing_execution(pid, all_safe=True)
    assert res["approval"]["approved_recommendation_ids"] == ["rec_s"]
    assert "rec_u" not in res["approval"]["approved_recommendation_ids"]


def test_caution_rejected_by_all_safe():
    pid = _project_basic()
    _forge_pacing(pid, [_rec("rec_c", "TRIM", 2.0, 3.0, safety="CAUTION")])
    with pytest.raises(px.PacingExecutionError):
        px.approve_caption_pacing_execution(pid, all_safe=True)


def test_review_and_planning_only_rejected():
    pid = _project_basic()
    _forge_pacing(pid, [_rec("rec_r", "REVIEW", 1.0, 2.0),
                        _rec("rec_v", "CHANGE_VISUAL", 0.0, 5.0),
                        _rec("rec_k", "KEEP", 0.0, 5.0)])
    for rid in ("rec_r", "rec_v", "rec_k"):
        with pytest.raises(px.PacingExecutionError):
            px.approve_caption_pacing_execution(pid, recommendation_ids=[rid])
    with pytest.raises(px.PacingExecutionError):
        px.approve_caption_pacing_execution(pid, all_safe=True)


# ---------- 3. EDL compatibility ----------

def test_trim_conflicting_edl_rejected_and_base_untouched():
    pid = _project_basic()
    before = _hashes(pid, BASE_FILES)
    edl_path = project_dir(pid) / "edit" / "edit_decision.json"
    edl = json.loads(edl_path.read_text(encoding="utf-8"))
    for d in edl["decisions"]:
        if d["action"] == "REMOVE":
            d["action"] = "KEEP"
            d["reason"] = "tampered"
    edl_path.write_text(json.dumps(edl, indent=2), encoding="utf-8")
    with pytest.raises(px.PacingExecutionError) as ei:
        px.approve_caption_pacing_execution(pid, recommendation_ids=["rec_0001"])
    assert "conflicts with approved EDL" in str(ei.value)
    after = _hashes(pid, [f for f in BASE_FILES if f != "edit/edit_decision.json"])
    assert {k: v for k, v in before.items() if k != "edit/edit_decision.json"} == after


def test_invalid_source_range_rejected():
    pid = _project_basic()
    _forge_pacing(pid, [_rec("rec_x", "TRIM", -1.0, 2.0)])
    with pytest.raises(px.PacingExecutionError):
        px.approve_caption_pacing_execution(pid, recommendation_ids=["rec_x"])


def test_overlapping_trims_merged_deterministically():
    pid = _project_basic()
    _forge_pacing(pid, [_rec("rec_a", "TRIM", 2.0, 2.95),
                        _rec("rec_b", "TRIM", 2.05, 3.0)])
    res = px.approve_caption_pacing_execution(
        pid, recommendation_ids=["rec_a", "rec_b"])
    plan = res["execution_plan"]
    assert plan["removed_ranges"] == [[2.0, 3.0]]
    assert any("merged" in w for w in plan["warnings"])
    res2 = px.approve_caption_pacing_execution(
        pid, recommendation_ids=["rec_b", "rec_a"])
    assert res2["execution_plan"]["execution_hash"] == plan["execution_hash"]


def _forge_base_approval(pid, approved_ids):
    """Hand editor plan + base approval (correct hashes)."""
    from engine.editing.approval import plan_hash, source_fingerprint
    plan = {"schema_version": "editor-plan-1.0", "source": "t", "style": "general"}
    write_artifact(pid, "editing", "editor_plan.json", plan)
    approval = {"schema_version": "approval-1.0",
                "plan_hash": plan_hash(plan),
                "source_fingerprint": source_fingerprint(load_project(pid).input_path),
                "analysis_hashes": {},
                "approved_cuts": [{"decision_id": did, "verdict": "approved"}
                                  for did in approved_ids],
                "broll_assignments": [], "jump_approvals": [],
                "status": "approved", "warnings": []}
    write_artifact(pid, "editing", "approved_edit_plan.json", approval)
    return approval


def test_base_approval_exclusion_respected():
    pid = _project_basic()
    _forge_base_approval(pid, [])  # nothing approved: TRIM explicitly unapproved
    with pytest.raises(px.PacingExecutionError) as ei:
        px.approve_caption_pacing_execution(pid, recommendation_ids=["rec_0001"])
    assert "left this removal unapproved" in str(ei.value)


def test_base_approval_inclusion_allowed():
    pid = _project_basic()
    _forge_base_approval(pid, ["2.0"])
    res = px.approve_caption_pacing_execution(pid, recommendation_ids=["rec_0001"])
    assert res["approval"]["approved_recommendation_ids"] == ["rec_0001"]
    assert res["approval"]["base_approval_hash"] != "none"


# ---------- 4. caption mapping ----------

def test_caption_preserved_dropped_and_words():
    pid = _project_basic()
    px.approve_caption_pacing_execution(pid, recommendation_ids=["rec_0001"])
    dry = px.dry_run_pacing_execution(pid)
    assert dry["caption_impact"] == {"PRESERVED": 2, "DROPPED": 1}
    assert dry["predicted_duration"] == pytest.approx(4.0)
    cues = px.validate_pacing_execution_approval(pid)["plan"].caption_mapping_preview["cues"]
    cues = {c["cue_id"]: c for c in cues}
    assert cues["c2"]["outcome"] == "DROPPED"
    assert cues["c2"]["dropped_words"] and all(
        w["reason"] == "SOURCE_RANGE_REMOVED" for w in cues["c2"]["dropped_words"])
    assert cues["c1"]["outcome"] == "PRESERVED"
    for c in (cues["c1"], cues["c3"]):
        for w in c["mapped_words"]:
            assert c["output_start"] - 1e-3 <= w["start"] and \
                w["end"] <= c["output_end"] + 1e-3
    texts = [w["text"] for w in cues["c1"]["mapped_words"]]
    assert texts == ["hello", "world"]  # order preserved


def test_partial_caption_overlap_blocked():
    cues = _base_cues() + [_cue("c4", 2.5, 4.0, [("over", 2.5, 3.0), ("lap", 3.5, 4.0)])]
    pid = _project_basic(cues=cues)
    _forge_pacing(pid, [_rec("rec_p", "TRIM", 2.0, 3.0)])
    with pytest.raises(px.PacingExecutionError) as ei:
        px.approve_caption_pacing_execution(pid, recommendation_ids=["rec_p"])
    assert "PARTIAL_CAPTION_OVERLAP" in str(ei.value)


def test_split_cue_via_existing_mapper():
    cues = [_cue("c1", 0.0, 2.0, [("aa", 0.0, 0.5), ("bb", 1.5, 2.0)])]
    tr = {"language": "en", "segments": [{
        "id": 0, "start": 0.0, "end": 2.0, "text": "aa bb",
        "words": [_w("aa", 0.0, 0.5), _w("bb", 1.5, 2.0)]}]}
    pid = _project_basic(cues=cues, transcript=tr)
    _forge_pacing(pid, [_rec("rec_s", "SPLIT", 0.9, 1.1)])
    px.approve_caption_pacing_execution(pid, recommendation_ids=["rec_s"])
    dry = px.dry_run_pacing_execution(pid)
    assert dry["executable_ops"][0]["mode"] == "SPLIT"
    assert dry["predicted_duration"] == pytest.approx(5.0)  # no deletion
    assert dry["caption_impact"] == {"SPLIT": 1}  # existing mapper split cue


# ---------- 5. visual captions ----------

def test_visual_placement_preserved_and_remapped():
    pid = _project_basic()
    _forge_visual(pid, [_placement("c1"), _placement("c3")])
    px.approve_caption_pacing_execution(pid, recommendation_ids=["rec_0001"])
    dry = px.dry_run_pacing_execution(pid)
    vis = dry["visual_caption_impact"]
    assert vis["state"] == "active"
    by_id = {p["cue_id"]: p for p in vis["placements"]}
    assert by_id["c1"]["status"] == "MAPPED" and by_id["c1"]["position"] == "bottom"
    assert by_id["c1"]["output_start"] == pytest.approx(0.5)
    assert vis["failed_checks"] == []


def test_invalid_visual_placement_blocks():
    pid = _project_basic()
    bad = _placement("c1")
    bad["position"] = "sideways"
    _forge_visual(pid, [bad])
    with pytest.raises(px.PacingExecutionError) as ei:
        px.approve_caption_pacing_execution(pid, recommendation_ids=["rec_0001"])
    assert "VISUAL_CAPTION_REVIEW_REQUIRED" in str(ei.value)


def test_visual_approval_required_when_plan_present():
    pid = _project_basic()
    _forge_visual(pid, [_placement("c1")])
    (project_dir(pid) / "captions" / "approved_visual_caption_plan.json").unlink()
    with pytest.raises(px.PacingExecutionError):
        px.approve_caption_pacing_execution(pid, recommendation_ids=["rec_0001"])


def test_rtl_preserved():
    cues = [_cue("c1", 0.5, 1.8, [("مرحبا", 0.5, 1.0), ("بالعالم", 1.2, 1.8)]),
            _cue("c2", 2.1, 2.9, [("gone", 2.1, 2.5), ("soon", 2.6, 2.9)]),
            _cue("c3", 3.5, 4.5, [("still", 3.5, 4.0), ("here", 4.1, 4.5)])]
    pid = _project_basic(cues=cues)
    _forge_visual(pid, [_placement("c1"), _placement("c3")])
    px.approve_caption_pacing_execution(pid, recommendation_ids=["rec_0001"])
    dry = px.dry_run_pacing_execution(pid)
    assert dry["visual_caption_impact"]["failed_checks"] == []
    cues_out = px.validate_pacing_execution_approval(pid)["plan"].caption_mapping_preview["cues"]
    c1 = next(c for c in cues_out if c["cue_id"] == "c1")
    assert c1["outcome"] == "PRESERVED"
    assert [w["text"] for w in c1["mapped_words"]] == ["مرحبا", "بالعالم"]


# ---------- 6. approval drift ----------

def test_approval_drift_detection():
    pid = _project_basic()
    px.approve_caption_pacing_execution(pid, recommendation_ids=["rec_0001"])
    assert px.validate_pacing_execution_approval(pid)["approval"]
    # pacing-plan drift
    plan_path = project_dir(pid) / "editing" / "caption_pacing_plan.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    plan["recommendations"].append(_rec("rec_x", "TRIM", 3.5, 4.0))
    plan_path.write_text(json.dumps(plan), encoding="utf-8")
    with pytest.raises(px.PacingExecutionError):
        px.validate_pacing_execution_approval(pid)


def test_caption_drift_detection():
    pid = _project_basic()
    px.approve_caption_pacing_execution(pid, recommendation_ids=["rec_0001"])
    cap_path = project_dir(pid) / "captions" / "caption_plan.json"
    cap = json.loads(cap_path.read_text(encoding="utf-8"))
    cap["cues"].append(_cue("c9", 4.6, 4.9, [("zz", 4.6, 4.9)]))
    cap_path.write_text(json.dumps(cap), encoding="utf-8")
    with pytest.raises(px.PacingExecutionError):
        px.validate_pacing_execution_approval(pid)


def test_source_drift_detection(tmp_path):
    import shutil
    src = tmp_path / "src.mp4"
    shutil.copy(FIX / "tone_5s.mp4", src)
    p = create_project(str(src))
    write_artifact(p.id, "analysis", "scenes.json",
                   {"scenes": [{"scene_id": 0, "start": 0, "end": 5}]})
    write_artifact(p.id, "edit", "edit_decision.json",
                   {"decisions": [{"decision_id": "k", "action": "KEEP",
                                    "start": 0, "end": 5, "reason": "t"}],
                    "duration": 5.0})
    write_artifact(p.id, "captions", "caption_plan.json",
                   {"schema_version": "caption-plan-1.0", "source": "t",
                    "transcript_hash": "h", "style": "default", "language": "en",
                    "expected_duration": 5.0, "config": {}, "warnings": [],
                    "cues": [_cue("c1", 0.5, 1.5, [("hi", 0.5, 1.5)])]})
    from engine.subtitles.captions import approve_captions
    from engine.editing.caption_pacing import (
        approve_caption_pacing, run_caption_pacing_for_project)
    approve_captions(p.id, mode="sidecar")
    run_caption_pacing_for_project(p.id)
    approve_caption_pacing(p.id)
    _forge_pacing(p.id, [_rec("rec_s", "SPLIT", 2.0, 2.5)])
    px.approve_caption_pacing_execution(p.id, recommendation_ids=["rec_s"])
    src.write_bytes(src.read_bytes() + b"\x00")
    with pytest.raises(px.PacingExecutionError):
        px.validate_pacing_execution_approval(p.id)


# ---------- 7. determinism + dry-run + immutability ----------

def test_execution_plan_deterministic():
    pid = _project_basic()
    a1 = px.approve_caption_pacing_execution(pid, recommendation_ids=["rec_0001"])
    a2 = px.approve_caption_pacing_execution(pid, recommendation_ids=["rec_0001"])
    assert a1["approval"]["execution_plan_hash"] == a2["approval"]["execution_plan_hash"]
    assert a1["approval"]["derived_edl_hash"] == a2["approval"]["derived_edl_hash"]
    assert a1["execution_plan"] == a2["execution_plan"]


def test_dry_run_writes_nothing():
    pid = _project_basic()
    px.approve_caption_pacing_execution(pid, recommendation_ids=["rec_0001"])
    proot = project_dir(pid)
    before = {str(p.relative_to(proot)): p.stat().st_mtime_ns for p in proot.rglob("*")
              if p.is_file()}
    dry = px.dry_run_pacing_execution(pid)
    after = {str(p.relative_to(proot)): p.stat().st_mtime_ns for p in proot.rglob("*")
             if p.is_file()}
    assert before == after
    assert dry["dry_run"] is True
    assert not list((proot / "renders").glob("*.mp4"))


def _ffmpeg_absent():
    from engine.core.media import ffprobe_path
    from engine.rendering.ffmpeg import which_ffmpeg
    return which_ffmpeg() is None or ffprobe_path() is None


def test_base_artifacts_immutable():
    pid = _project_basic()
    before = _hashes(pid, BASE_FILES)
    px.approve_caption_pacing_execution(pid, recommendation_ids=["rec_0001"])
    px.dry_run_pacing_execution(pid)
    from engine.cli import main
    if _ffmpeg_absent():
        assert main(["execute-caption-pacing", pid]) == 5  # no ffmpeg here
    else:
        assert main(["execute-caption-pacing", pid]) == 0  # real render
    assert _hashes(pid, BASE_FILES) == before


def test_pacing_plan_untouched_by_execution_layer():
    pid = _project_basic()
    plan_path = project_dir(pid) / "editing" / "caption_pacing_plan.json"
    before = plan_path.read_bytes()
    px.approve_caption_pacing_execution(pid, recommendation_ids=["rec_0001"])
    px.dry_run_pacing_execution(pid)
    assert plan_path.read_bytes() == before


# ---------- 8. CLI ----------

def test_cli_approve_and_dry_run(capsys):
    from engine.cli import main
    pid = _project_basic()
    assert main(["approve-caption-pacing-execution", pid,
                 "--recommendation-id", "rec_0001"]) == 0
    assert main(["execute-caption-pacing", pid, "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "rec_0001" in out and "DRY RUN" in out


def test_cli_errors():
    from engine.cli import main
    pid = _project_basic()
    assert main(["approve-caption-pacing-execution", pid]) == 2
    assert main(["approve-caption-pacing-execution", pid,
                 "--recommendation-id", "rec_0001", "--all-safe"]) == 2
    assert main(["approve-caption-pacing-execution", "project_19000101_000000",
                 "--all-safe"]) == 2
    assert main(["execute-caption-pacing", pid, "--dry-run"]) == 2  # no approval yet


@pytest.mark.skipif(not _ffmpeg_absent(),
                      reason="requires missing ffmpeg/ffprobe")
def test_cli_execute_no_ffmpeg_reports_preflight():
    from engine.cli import main
    pid = _project_basic()
    px.approve_caption_pacing_execution(pid, recommendation_ids=["rec_0001"])
    assert main(["execute-caption-pacing", pid]) == 5
    appr = json.loads((project_dir(pid) / "editing" /
                       "approved_caption_pacing_execution.json").read_text(encoding="utf-8"))
    assert appr["approval_state"] == "APPROVED"  # never EXECUTED
    assert not list((project_dir(pid) / "renders").glob("*.mp4"))


# ---------- 9. execution failures (no ffmpeg) ----------

@pytest.mark.skipif(not _ffmpeg_absent(),
                      reason="requires missing ffmpeg/ffprobe")
def test_execute_missing_ffmpeg_fails_explicitly():
    from engine.rendering.execution import RenderError
    pid = _project_basic()
    px.approve_caption_pacing_execution(pid, recommendation_ids=["rec_0001"])
    with pytest.raises(RenderError) as ei:
        px.execute_caption_pacing_for_project(pid)
    assert "MISSING" in str(ei.value)
    assert ei.value.stage == "execute"
    assert not list((project_dir(pid) / "renders").glob("*.mp4"))


def test_execute_bogus_encoder_fails_explicitly():
    from engine.rendering.execution import RenderError
    pid = _project_basic()
    px.approve_caption_pacing_execution(pid, recommendation_ids=["rec_0001"])
    with pytest.raises(RenderError):
        px.execute_caption_pacing_for_project(
            pid, config_overrides={"video_encoder": "bogus_encoder_xyz"})
    assert not list((project_dir(pid) / "renders").glob("*.mp4"))
    appr = json.loads((project_dir(pid) / "editing" /
                       "approved_caption_pacing_execution.json").read_text(encoding="utf-8"))
    assert appr["approval_state"] != "EXECUTED"


# ---------- 10. real E2E (ffmpeg-gated) ----------

def test_real_chain_e2e(need_ffmpeg):
    from engine.analysis.scenes import detect_scenes_project
    from engine.analysis.speech import transcribe_to_project
    from engine.analysis.visual import run_visual_for_project
    from engine.core.orchestrator import run_inspect
    from engine.editing.brain import run_editor_brain_for_project
    from engine.editing.caption_pacing import (
        approve_caption_pacing,
        run_caption_pacing_for_project,
    )
    from engine.editing.decisions import build_edl_for_project
    from engine.editing.intelligence import run_intelligence_for_project
    from engine.subtitles.captions import approve_captions, caption_plan_for_project
    from engine.subtitles.visual_captions import (
        approve_caption_visual, caption_visual_for_project)
    src = str(FIX / "speech_video.mp4")
    pid = run_inspect(src)["project"]
    transcribe_to_project(src, project_id=pid, model="tiny")
    detect_scenes_project(src, project_id=pid)
    build_edl_for_project(pid)
    run_intelligence_for_project(pid)
    run_visual_for_project(pid)
    run_editor_brain_for_project(pid)
    caption_plan_for_project(pid)
    approve_captions(pid, mode="sidecar")
    caption_visual_for_project(pid)
    approve_caption_visual(pid)
    pacing = run_caption_pacing_for_project(pid)["plan"]
    approve_caption_pacing(pid)
    base_files = ["edit/edit_decision.json", "captions/caption_plan.json",
                  "editing/approved_captions.json",
                  "captions/visual_caption_plan.json",
                  "captions/approved_visual_caption_plan.json",
                  "editing/caption_pacing_plan.json",
                  "editing/approved_caption_pacing_plan.json"]
    before = _hashes(pid, base_files)

    safe_trims = [r["recommendation_id"] for r in pacing["recommendations"]
                  if r["action"] == "TRIM" and r["safety_status"] == "SAFE"]
    assert safe_trims, "fixture must yield at least one SAFE TRIM"
    rid = safe_trims[0]
    appr = px.approve_caption_pacing_execution(pid, recommendation_ids=[rid])
    assert appr["approval"]["approved_recommendation_ids"] == [rid]
    dry = px.dry_run_pacing_execution(pid)
    assert dry["predicted_duration"] > 0

    before_dur = json.loads((project_dir(pid) / "edit" / "edit_decision.json")
                            .read_text(encoding="utf-8"))["duration"]
    res = px.execute_caption_pacing_for_project(pid)
    manifest = res["manifest"]
    assert manifest["status"] == "completed"
    assert manifest["qc"]["verdict"] == "pass"
    assert manifest["recommendations_executed"] == [rid]
    assert manifest["caption_qc"]["verdict"] == "pass"
    assert manifest["actual_duration"] == pytest.approx(dry["predicted_duration"], abs=0.5)
    assert manifest["actual_duration"] < before_dur
    assert Path(res["output"]).is_file()
    assert _hashes(pid, base_files) == before  # immutables unchanged

    again = px.execute_caption_pacing_for_project(pid)
    assert again["cached"] is True
    assert again["manifest"]["execution_hash"] == manifest["execution_hash"]

    cap = json.loads((project_dir(pid) / "captions" / "caption_plan.json")
                     .read_text(encoding="utf-8"))
    cap["cues"].append(_cue("c9", 0.1, 0.4, [("zz", 0.1, 0.4)]))
    (project_dir(pid) / "captions" / "caption_plan.json").write_text(
        json.dumps(cap), encoding="utf-8")
    from engine.rendering.execution import RenderError
    with pytest.raises(RenderError) as ei:
        px.execute_caption_pacing_for_project(pid)
    assert ei.value.stage == "validate"  # drift is a validation failure
