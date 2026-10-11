"""Phases 25-26 tests — independent reviewer + repair routing."""
import json
from pathlib import Path

import pytest

from engine.core.project_store import (
    create_project,
    project_dir,
    write_artifact,
)
from engine.review import reviewer, repair

FIX = Path(__file__).resolve().parents[1] / "tests" / "fixtures"


def _project_minimal(with_srt=False):
    p = create_project(str(FIX / "tone_5s.mp4"))
    write_artifact(p.id, "edit", "edit_decision.json",
                   {"decisions": [{"decision_id": "k", "action": "KEEP",
                                    "start": 0, "end": 5, "reason": "t"}],
                    "duration": 5.0})
    if with_srt:
        (project_dir(p.id) / "captions").mkdir(parents=True, exist_ok=True)
        (project_dir(p.id) / "captions" / "out.srt").write_text(
            "1\n00:00:00,500 --> 00:00:01,500\nhello world\n\n"
            "2\n00:00:02,000 --> 00:00:01,000\nbroken\n\n"
            "3\n00:00:03,000 --> 00:00:04,000\n\n",
            encoding="utf-8")
    return p.id


def test_reviewer_disagrees_with_missing_render():
    pid = _project_minimal()
    res = reviewer.review_project(pid)
    assert res["verdict"] == "FAIL"  # no render exists; editor claims nothing
    names = {c["name"]: c["detail"] for c in res["payload"]["checks"]}
    assert "technical:output_exists" in names
    assert (project_dir(pid) / "qc" / "independent_review.json").is_file()


def test_reviewer_never_passes_uninspected_media():
    pid = _project_minimal(with_srt=True)
    (project_dir(pid) / "renders").mkdir(parents=True, exist_ok=True)
    (project_dir(pid) / "renders" / "out.mp4").write_bytes(b"\x00" * 64)
    res = reviewer.review_project(pid)
    assert res["verdict"] in ("FAIL", "REVIEW")
    assert res["verdict"] != "PASS"  # streams unverifiable without ffprobe
    details = {c["name"]: c["detail"] for c in res["payload"]["checks"]}
    from engine.core.media import ffprobe_path
    if ffprobe_path() is None:
        assert "UNKNOWN" in details["technical:stream_probe"]
    else:
        # ffprobe present: reviewer honestly reports unimplemented depth
        assert "REVIEW" in details["technical:stream_probe"]
    assert "FAIL" in details["captions:sidecar_intervals"]  # cue 2 inverted
    assert "FAIL" in details["captions:sidecar_empty"]  # cue 3 empty


def test_reviewer_caption_approval_checked():
    pid = _project_minimal()
    res = reviewer.review_project(pid)
    details = {c["name"]: c["detail"] for c in res["payload"]["checks"]}
    assert "captions:presence" in details  # REVIEW, nothing to audit


def test_repair_routing_and_limits():
    pid = _project_minimal(with_srt=True)
    res = reviewer.review_project(pid)
    routed = repair.classify_failure(res["payload"])
    assert routed
    subs = {r["subsystem"] for r in routed}
    assert any("caption" in s for s in subs)
    plan = repair.plan_repair(pid, res["payload"], max_attempts=2)
    assert plan["action"] == "REPAIR_PLANNED"
    assert all(a["kind"] in ("REPLAN", "REVIEW_AGAIN") for a in plan["actions"])
    # exhaust budget
    repair.record_attempt(pid)
    repair.record_attempt(pid)
    plan2 = repair.plan_repair(pid, res["payload"], max_attempts=2)
    assert plan2["action"] == "BLOCKED_REQUIRES_HUMAN_REVIEW"
    # clean review needs nothing
    clean = {"verdict": "PASS", "checks": []}
    assert repair.plan_repair(pid, clean)["action"] == "NONE"


def test_repair_deterministic():
    pid = _project_minimal()
    res = reviewer.review_project(pid)
    assert repair.classify_failure(res["payload"]) == \
        repair.classify_failure(res["payload"])
