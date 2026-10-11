"""Phase 13 real end-to-end: full chain with a REAL local B-roll asset.

analyze -> transcribe -> scenes -> edit -> edit-analyze -> visual
-> editor-plan -> approve-plan -> dry-run -> render-plan -> QC
No downloads, no mocks, no fakes.
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests" / "fixtures"
SRC = str(FIX / "static_12s.mp4")
BROLL = str(FIX / "broll_test.mp4")


@pytest.fixture(scope="module")
def chain():
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        pytest.skip("ffmpeg/ffprobe not on PATH")
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "make_test_media.py"), "--all"],
                       capture_output=True, text=True, timeout=600)
    assert r.returncode == 0
    for name in ("static_12s.mp4", "broll_test.mp4"):
        assert (FIX / name).is_file(), name
    from engine.analysis.scenes import detect_scenes_project
    from engine.analysis.speech import transcribe_to_project
    from engine.analysis.visual import run_visual_for_project
    from engine.core.orchestrator import run_inspect
    from engine.editing.brain import run_editor_brain_for_project
    from engine.editing.decisions import build_edl_for_project
    from engine.editing.intelligence import run_intelligence_for_project
    pid = run_inspect(SRC)["project"]
    transcribe_to_project(SRC, project_id=pid, model="tiny")
    detect_scenes_project(SRC, project_id=pid)
    build_edl_for_project(pid)
    run_intelligence_for_project(pid)
    run_visual_for_project(pid)
    plan = run_editor_brain_for_project(pid)["plan"]
    assert plan["schema_version"] == "editor-plan-1.0"
    return {"project": pid, "plan": plan}


def _opportunities(plan):
    return [(b["start"], b["end"]) for b in plan.get("broll_plan", [])]


def test_chain_broll_opportunity_exists(chain):
    opps = _opportunities(chain["plan"])
    assert opps, "static 12 s scene must yield a stagnation opportunity"
    s, e = opps[0]
    assert e - s >= 8.0  # long static scene


def test_approve_dry_run_render(chain):
    from engine.cli import main
    from engine.core.project_store import project_dir
    pid = chain["project"]
    s, e = _opportunities(chain["plan"])[0]
    # Partial 4 s mapping inside the 12 s opportunity (asset is 4 s).
    assert main(["approve-plan", pid, "--broll-map", f"{s}-{s + 4}={BROLL}"]) == 0
    approval = json.loads((project_dir(pid) / "editing" / "approved_edit_plan.json")
                          .read_text())
    assert len(approval["broll_assignments"]) == 1
    assert main(["render-plan", pid, "--dry-run"]) == 0
    renders = project_dir(pid) / "renders"
    assert list(renders.glob("plan_*.mp4")) == []  # dry-run rendered nothing
    assert main(["render-plan", pid, "--out", "real_e2e.mp4"]) == 0
    out = renders / "real_e2e.mp4"
    assert out.is_file() and out.stat().st_size > 0
    manifest = json.loads((renders / "real_e2e_plan_manifest.json").read_text())
    assert manifest["status"] == "completed" and manifest["qc"]["verdict"] == "pass"
    assert manifest["kind"] == "plan"
    assert manifest["expected_duration"] == pytest.approx(12.0, abs=0.5)
    assert manifest["actual_duration"] == pytest.approx(12.0, abs=0.5)
    assert manifest["encoder"]
    assert manifest["broll_mappings"]
    assert manifest["assets"]
    chain["manifest"] = manifest
    chain["output"] = str(out)


def test_dialogue_preserved_and_placed(chain):
    from engine.core.media import probe
    info = probe(chain["output"])
    assert info.audio_codec == "aac"  # base dialogue intact under muted overlay
    assert abs(info.duration - 12.0) <= 0.5
    assert (info.width, info.height) == (640, 360)
    assert info.video_codec == "h264"
    qc_names = [c["name"] for c in chain["manifest"]["qc"]["checks"]]
    assert "broll_placed_op_0002" in qc_names or any(
        n.startswith("broll_placed_") and c["passed"]
        for n, c in ((c["name"], c) for c in chain["manifest"]["qc"]["checks"]))


def test_rerun_reuses_cache(chain):
    from engine.rendering.plan_execute import render_plan_for_project
    again = render_plan_for_project(chain["project"], out_name="real_e2e.mp4")
    assert again["cached"] is True
    assert again["output"] == chain["output"]


def test_asset_change_invalidates(chain):
    import shutil as _sh
    from engine.editing.approval import validate_approval
    from engine.rendering.plan_execute import render_plan_for_project
    backup = BROLL + ".bak"
    _sh.copy(BROLL, backup)
    try:
        with open(BROLL, "r+b") as fh:
            fh.seek(1000)
            fh.write(b"\x01\x02\x03\x04")
        with pytest.raises(Exception, match="B-roll asset changed"):
            validate_approval(chain["project"])
        # Approval gone stale -> render refuses too.
        with pytest.raises(Exception):
            render_plan_for_project(chain["project"], out_name="real_e2e.mp4")
    finally:
        _sh.move(backup, BROLL)
    # Restored asset validates again.
    validate_approval(chain["project"])
