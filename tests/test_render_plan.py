"""Phase 13 render/cache/CLI tests — real renders through the plan pipeline."""
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

from engine.core.media import probe
from engine.core.project_store import create_project, project_dir, write_artifact
from engine.rendering.execution import RenderError
from engine.rendering.plan_execute import render_plan_for_project


@pytest.fixture(scope="module", autouse=True)
def fixtures():
    import shutil
    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg not on PATH")
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "make_test_media.py"), "--all"],
                       capture_output=True, text=True, timeout=600)
    assert r.returncode == 0


def _edl(decisions, duration):
    seq, out = 0, []
    for action, s, e in decisions:
        seq += 1
        out.append({"decision_id": f"edl_{seq:04d}", "start": s, "end": e,
                    "action": action, "reason": "test", "confidence": 0.9,
                    "scene_id": 0, "word_refs": [], "metadata": {}})
    return {"source": SRC, "duration": duration, "decisions": out,
            "policy": {}, "analysis_refs": {}, "warnings": []}


def _plan_doc():
    return {"schema_version": "editor-plan-1.0", "project": "p", "source": SRC,
            "duration": 5.0, "editing_style": {"name": "general"},
            "cut_plan": [], "jump_strategy": [], "broll_plan": [], "warnings": []}


def _proj(tag, edl, broll_map=(), audio="mute"):
    from engine.editing.approval import approve_plan
    p = create_project(SRC)
    for name, payload in ({"audio_analysis.json": {"silence": []},
                           "transcript.json": {"segments": []},
                           "scenes.json": {"scenes": [{"scene_id": 0, "start": 0.0, "end": 5.0}]},
                           "media_info.json": {"video_codec": "h264", "duration": 5.0}}).items():
        write_artifact(p.id, "analysis", name, payload)
    write_artifact(p.id, "edit", "edit_decision.json", edl)
    plan = _plan_doc()
    if broll_map:
        plan["broll_plan"] = [{"start": s, "end": e, "duration": e - s,
                               "reason": "visual_stagnation",
                               "desired_visual_type": "supporting_footage",
                               "semantic_topic": "", "transcript_ref": {},
                               "priority": "medium", "recommended": True,
                               "confidence": 0.6, "evidence": []}
                              for s, e, _ in broll_map]
    write_artifact(p.id, "editing", "editor_plan.json", plan)
    maps = [f"{s}-{e}={a}" for s, e, a in broll_map]
    approve_plan(p.id, broll_map=maps or None, broll_audio=audio)
    return p


def test_single_operation_render():
    p = _proj("t", _edl([("KEEP", 0, 5)], 5.0))
    res = render_plan_for_project(p.id, out_name="rp_single.mp4")
    assert res["cached"] is False
    assert probe(res["output"]).duration == pytest.approx(5.0, abs=0.4)
    assert res["manifest"]["qc"]["verdict"] == "pass"


def test_multiple_operations_render():
    p = _proj("t", _edl([("KEEP", 0, 2), ("REMOVE", 2, 3), ("KEEP", 3, 5)], 5.0))
    res = render_plan_for_project(p.id, out_name="rp_multi.mp4")
    # Nothing approved -> REMOVE stays -> full 5 s timeline.
    assert probe(res["output"]).duration == pytest.approx(5.0, abs=0.4)


def test_broll_and_jump_mitigation_render():
    p = _proj("t", _edl([("KEEP", 0, 5)], 5.0), broll_map=[(1, 3, BROLL)])
    res = render_plan_for_project(p.id, out_name="rp_broll.mp4")
    m = res["manifest"]
    assert m["qc"]["verdict"] == "pass"
    assert len(m["assets"]) == 1 and m["broll_mappings"]
    assert any(c["name"].startswith("broll_placed_") for c in m["qc"]["checks"])


def test_audio_preservation():
    p = _proj("t", _edl([("KEEP", 0, 5)], 5.0))
    out = render_plan_for_project(p.id, out_name="rp_audio.mp4")["output"]
    info = probe(out)
    assert info.audio_codec == "aac" and info.audio_channels == 1
    assert abs(info.duration - 5.0) <= 0.4


def test_qc_fields_present():
    p = _proj("t", _edl([("KEEP", 0, 2)], 2.0))
    m = render_plan_for_project(p.id, out_name="rp_qc.mp4")["manifest"]
    names = [c["name"] for c in m["qc"]["checks"]]
    for required in ("duration", "video_codec", "audio_present", "av_sync",
                     "no_unexpected_black", "decode_clean", "silence_expected"):
        assert required in names, required
    assert m["qc"]["verdict"] == "pass"
    for key in ("source", "source_fingerprint", "editor_plan_hash", "approval_hash",
                "execution_plan_hash", "execution_version", "render_config",
                "encoder", "operations", "assets", "broll_mappings", "warnings",
                "qc", "schema_versions"):
        assert key in m, key


def test_cache_reuse_and_invalidation():
    p = _proj("t", _edl([("KEEP", 0, 2)], 2.0))
    first = render_plan_for_project(p.id, out_name="rp_cache.mp4")
    assert first["cached"] is False
    mtime = Path(first["output"]).stat().st_mtime_ns
    second = render_plan_for_project(p.id, out_name="rp_cache.mp4")
    assert second["cached"] is True and second["output"] == first["output"]
    assert Path(second["output"]).stat().st_mtime_ns == mtime
    third = render_plan_for_project(p.id, out_name="rp_cache.mp4",
                                    config_overrides={"preset": "ultrafast"})
    assert third["cached"] is False  # render-config change invalidates


def test_corrupt_output_rerenders():
    p = _proj("t", _edl([("KEEP", 0, 2)], 2.0))
    first = render_plan_for_project(p.id, out_name="rp_corr.mp4")
    Path(first["output"]).write_bytes(b"corrupt")
    again = render_plan_for_project(p.id, out_name="rp_corr.mp4")
    assert again["cached"] is False
    assert probe(again["output"]).duration == pytest.approx(2.0, abs=0.4)


def test_cli_render_plan(capsys):
    from engine.cli import main
    p = _proj("t", _edl([("KEEP", 0, 2)], 2.0))
    assert main(["render-plan", p.id, "--dry-run"]) == 0
    assert "DRY RUN" in capsys.readouterr().out
    assert main(["render-plan", p.id, "--out", "cli_rp.mp4"]) == 0
    out = capsys.readouterr().out
    assert "qc      : pass" in out and "manifest:" in out
    assert main(["render-plan", p.id, "--out", "cli_rp2.mp4", "--json"]) == 0
    assert '"qc"' in capsys.readouterr().out
    q = create_project(SRC)  # no approval
    assert main(["render-plan", q.id]) == 2
    assert main(["render-plan", q.id, "--dry-run"]) == 2
    assert main(["render-plan", "project_nope_123"]) == 2
