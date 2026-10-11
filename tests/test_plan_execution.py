"""Phase 13 timeline composition + dry-run tests (dry-run renders nothing)."""
import json
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests" / "fixtures"
SRC = str(FIX / "tone_5s.mp4")
BROLL = str(FIX / "broll_test.mp4")

from engine.core.project_store import create_project, project_dir, write_artifact
from engine.rendering.execution import RenderError
from engine.rendering.plan_execute import compose_timeline, dry_run_plan


@pytest.fixture(scope="module", autouse=True)
def fixtures():
    import shutil
    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg not on PATH")
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "make_test_media.py"), "--all"],
                       capture_output=True, text=True, timeout=600)
    assert r.returncode == 0


def _edl_raw(decisions, duration, source=None):
    seq = 0
    out = []
    for action, s, e in decisions:
        seq += 1
        out.append({"decision_id": f"edl_{seq:04d}", "start": s, "end": e,
                    "action": action, "reason": "test", "confidence": 0.9,
                    "scene_id": 0, "word_refs": [], "metadata": {}})
    return {"source": source or SRC, "duration": duration, "decisions": out,
            "policy": {}, "analysis_refs": {}, "warnings": []}


def _approval(assignments=(), cuts=()):
    return {"schema_version": "approval-1.0", "plan_hash": "x",
            "source_fingerprint": {}, "analysis_hashes": {},
            "approved_cuts": [{"decision_id": d, "verdict": "approve"} for d in cuts],
            "broll_assignments": list(assignments),
            "jump_approvals": [], "status": "approved", "warnings": [],
            "approved_at": "t", "approver": "test"}


def _assign(s, e, aid="broll_test", path=None, placement="overlay"):
    return {"opportunity": {"start": s, "end": e, "kind": "opportunity"},
            "start": s, "end": e,
            "asset_id": aid, "asset_path": path or BROLL, "asset_hash": "h",
            "asset_start": 0.0, "asset_end": e - s, "audio_mode": "mute",
            "fit": "cover", "placement": placement}
    return {"opportunity": {"start": s, "end": e, "kind": "opportunity"},
            "asset_id": aid, "asset_path": path or BROLL, "asset_hash": "h",
            "asset_start": 0.0, "asset_end": e - s, "audio_mode": "mute",
            "fit": "cover", "placement": placement}


def _proj(tag, edl, plan_extra_approval=None):
    p = create_project(SRC)
    for name, payload in ({"audio_analysis.json": {"silence": []},
                           "transcript.json": {"segments": []},
                           "scenes.json": {"scenes": [{"scene_id": 0, "start": 0.0, "end": 5.0}]},
                           "media_info.json": {"video_codec": "h264", "duration": 5.0}}).items():
        write_artifact(p.id, "analysis", name, payload)
    write_artifact(p.id, "edit", "edit_decision.json", edl)
    return p


def test_replacement_timeline_offsets():
    edl = _edl_raw([("KEEP", 0, 5)], 5.0)
    plan = compose_timeline(edl, _approval(assignments=[_assign(1, 3)]))
    assert [(o.action, o.source_start, o.source_end, o.output_start, o.output_end)
            for o in plan.operations] == [
        ("keep", 0.0, 1.0, 0.0, 1.0),
        ("broll_overlay", 1.0, 3.0, 1.0, 3.0),
        ("keep", 3.0, 5.0, 3.0, 5.0)]
    assert plan.expected_duration == 5.0
    assert plan.operations[1].layer == "overlay"
    assert plan.operations[1].asset_id == "broll_test"


def test_multiple_clips_ordered():
    edl = _edl_raw([("KEEP", 0, 5)], 5.0)
    plan = compose_timeline(edl, _approval(assignments=[_assign(0, 1), _assign(3, 4)]))
    kinds = [o.action for o in plan.operations]
    assert kinds == ["broll_overlay", "keep", "broll_overlay", "keep"]
    outs = [(o.output_start, o.output_end) for o in plan.operations]
    assert outs == [(0.0, 1.0), (1.0, 3.0), (3.0, 4.0), (4.0, 5.0)]  # contiguous


def test_adjacent_boundaries():
    edl = _edl_raw([("KEEP", 0, 5)], 5.0)
    plan = compose_timeline(edl, _approval(assignments=[_assign(1, 2), _assign(2, 3)]))
    assert len(plan.operations) == 4  # keep, ov, ov, keep (no gap, no overlap)
    assert plan.expected_duration == 5.0


def test_sequential_deterministic():
    edl = _edl_raw([("KEEP", 0, 2), ("REMOVE", 2, 3), ("KEEP", 3, 5)], 5.0)
    from engine.rendering.plan_execute import compose_timeline as ct
    from dataclasses import asdict
    a, b = ct(edl, _approval()), ct(edl, _approval())
    assert asdict(a) == asdict(b)
    assert [(o.action, o.source_start, o.source_end) for o in a.operations] == [
        ("keep", 0.0, 2.0), ("keep", 2.0, 3.0), ("keep", 3.0, 5.0)]  # unapproved REMOVE stays KEEP


def test_unapproved_removes_stay_keep():
    edl = _edl_raw([("KEEP", 0, 2), ("REMOVE", 2, 3), ("KEEP", 3, 5)], 5.0)
    plan = compose_timeline(edl, _approval())  # nothing approved
    assert all(o.action == "keep" for o in plan.operations)
    assert plan.expected_duration == 5.0


def test_conflicting_assignments_fail():
    edl = _edl_raw([("KEEP", 0, 5)], 5.0)
    with pytest.raises(RenderError, match="overlapping"):
        compose_timeline(edl, _approval(assignments=[_assign(1, 3), _assign(2, 4)]))


def test_outside_assignment_fails_clamped_warns():
    edl = _edl_raw([("KEEP", 0, 2), ("REMOVE", 2, 3), ("KEEP", 3, 5)], 5.0)
    with pytest.raises(RenderError, match="outside all"):
        compose_timeline(edl, _approval(assignments=[_assign(8, 9)]))
    plan = compose_timeline(edl, _approval(assignments=[_assign(1, 4)],
                                          cuts=["edl_0002"]))
    assert any("clamped" in w for w in plan.warnings)  # spans the REMOVE gap
    assert plan.expected_duration == 4.0  # keeps total, overlays preserve duration


def test_unsupported_edl_action_fails():
    edl = _edl_raw([("ZOOM", 0, 5)], 5.0)
    with pytest.raises(RenderError, match="invalid base EDL"):
        compose_timeline(edl, _approval())


def test_empty_keeps_refused():
    from engine.editing.approval import ApprovalError  # noqa (import surface check)
    edl = _edl_raw([("REMOVE", 0, 5)], 5.0)
    with pytest.raises(RenderError, match="keeps nothing"):
        compose_timeline(edl, _approval(cuts=["edl_0001"]))


def test_dry_run_renders_nothing():
    from engine.editing.approval import approve_plan
    p = _proj("t", _edl_raw([("KEEP", 0, 5)], 5.0))
    from engine.core.project_store import load_project
    import json as _json
    plan_doc = {"schema_version": "editor-plan-1.0", "project": p.id, "source": SRC,
                "duration": 5.0, "editing_style": {"name": "general"},
                "cut_plan": [], "jump_strategy": [],
                "broll_plan": [{"start": 1.0, "end": 3.0, "duration": 2.0,
                                "reason": "visual_stagnation",
                                "desired_visual_type": "supporting_footage",
                                "semantic_topic": "", "transcript_ref": {},
                                "priority": "medium", "recommended": True,
                                "confidence": 0.6, "evidence": []}],
                "warnings": []}
    write_artifact(p.id, "editing", "editor_plan.json", plan_doc)
    approve_plan(p.id, broll_map=[f"1-3={BROLL}"])
    before = set((project_dir(p.id) / "renders").glob("plan_*.mp4")) \
        if (project_dir(p.id) / "renders").exists() else set()
    res = dry_run_plan(p.id)
    assert res["expected_duration"] == 5.0
    assert len(res["operations"]) == 3
    assert res["assets"] and "smoke tests skipped" in res["encoder"]
    assert res["qc_plan"] and res["warnings"] == []
    after = set((project_dir(p.id) / "renders").glob("plan_*.mp4")) \
        if (project_dir(p.id) / "renders").exists() else set()
    assert after == before  # absolutely no render occurred


def test_dry_run_without_approval_fails():
    from engine.rendering.plan_execute import dry_run_plan as dr
    from engine.rendering.execution import RenderError as RE
    p = create_project(SRC)
    with pytest.raises((RE, Exception), match="approval"):
        dr(p.id)
