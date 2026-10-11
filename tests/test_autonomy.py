"""Phases 27-29 tests — controller, director, memory."""
import json
from pathlib import Path

import pytest

from engine.autonomy import controller, director, memory
from engine.core.project_store import create_project, project_dir

FIX = Path(__file__).resolve().parents[1] / "tests" / "fixtures"


def _pid():
    return create_project(str(FIX / "tone_5s.mp4")).id


def test_director_plan():
    plan = director.plan_production("The speaker explains AI infrastructure.",
                                    style="cinematic", duration_s=60.0,
                                    platform="youtube")
    assert plan["schema_version"] == "director-plan-1.0"
    assert [b["label"] for b in
            [r for r in plan["asset_requirements"] if r["kind"] == "BROLL"]] == \
        ["futuristic server room", "AI chip close-up", "data-center corridor"]
    assert len(plan["story_structure"]) == 3
    assert plan["vertical"] is False
    assert director.plan_production("x", platform="shorts")["vertical"] is True
    assert director.plan_production("x") == director.plan_production("x")
    with pytest.raises(ValueError):
        director.plan_production("x", duration_s=0)


def test_memory_roundtrip_and_secrets():
    pid = _pid()
    memory.remember(pid, "asset_selected",
                    {"asset_id": "X-VID-1", "score": 0.9})
    memory.remember(pid, "asset_rejected",
                    {"asset_id": "X-VID-2", "reason": "aspect"})
    assert len(memory.recall(pid)) == 2
    assert len(memory.recall(pid, kind="asset_rejected")) == 1
    with pytest.raises(ValueError):
        memory.remember(pid, "bogus_kind", {})
    with pytest.raises(ValueError):
        memory.remember(pid, "note", {"api_key": "zzz"})
    path = project_dir(pid) / "memory" / "events.jsonl"
    assert path.is_file()
    assert all("api_key" not in line for line in
               path.read_text(encoding="utf-8").splitlines())


def test_controller_runs_and_checkpoints():
    pid = _pid()
    calls = []

    def ok_runner(p, state):
        calls.append(p)
        return {"status": "OK", "note": "fine"}

    def blocked_runner(p, state):
        return {"status": "BLOCKED", "reason": "no ffmpeg"}

    st = controller.run_pipeline(pid, ["a", "b", "c"],
                                 {"a": ok_runner, "b": blocked_runner,
                                  "c": ok_runner})
    assert calls == [pid]  # stopped at b; c never ran
    assert st["status"] == "BLOCKED"
    assert st["phases"][1]["phase"] == "b"
    spath = project_dir(pid) / "autonomy" / "state.json"
    assert spath.is_file()
    # resume skips completed phases
    st2 = controller.run_pipeline(pid, ["a", "b", "c"],
                                  {"a": ok_runner, "b": ok_runner,
                                   "c": ok_runner})
    assert [p["phase"] for p in st2["phases"] if p["status"] == "OK"] == \
        ["a", "b", "c"]
    assert st2["status"] == "FINAL_PASS"
    assert controller.recover(pid)["status"] == "FINAL_PASS"


def test_controller_isolates_runner_crash():
    pid = _pid()

    def boom(p, state):
        raise RuntimeError("kaput")

    st = controller.run_pipeline(pid, ["x"], {"x": boom})
    assert st["status"] == "FAILED"
    assert "kaput" in st["failures"][0]["detail"]["reason"]
