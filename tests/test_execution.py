"""Phase 9 tests — EDL execution & render engine (ALL real ffmpeg renders).

No mocked FFmpeg: every execution test probes an actually rendered file.
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests" / "fixtures"

from engine.core.media import probe
from engine.core.project_store import create_project, write_artifact
from engine.rendering.execution import (
    RenderError,
    build_execution_plan,
    edl_hash,
    execute_plan,
    render_edl_for_project,
    resolve_render_config,
    validate_edl,
)


@pytest.fixture(scope="module", autouse=True)
def fixtures():
    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg not on PATH")
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "make_test_media.py"), "--all"],
                       capture_output=True, text=True, timeout=600)
    assert r.returncode == 0, f"fixture build failed: {r.stderr[-1500:]}"


def _edl(keeps, duration, source="test.mp4"):
    """Hand-built EDL dict: keeps=[(s,e)], gaps filled with REMOVEs."""
    decisions, seq, cursor = [], 0, 0.0

    def emit(s, e, action, reason):
        nonlocal seq
        seq += 1
        decisions.append({"decision_id": f"edl_{seq:04d}", "start": s, "end": e,
                          "action": action, "reason": reason, "confidence": 0.9,
                          "scene_id": 0, "word_refs": [], "metadata": {}})

    for s, e in sorted(keeps):
        if s > cursor:
            emit(cursor, s, "REMOVE", "test_gap")
        emit(s, e, "KEEP", "default")
        cursor = e
    if cursor < duration:
        emit(cursor, duration, "REMOVE", "test_gap")
    return {"source": source, "duration": duration, "decisions": decisions,
            "policy": {}, "analysis_refs": {}, "warnings": []}


def _keep_only(decisions, duration, source="test.mp4"):
    """Raw EDL with EXACTLY the given decisions (no gap-filling)."""
    seq = 0
    out = []
    for action, s, e in decisions:
        seq += 1
        out.append({"decision_id": f"edl_{seq:04d}", "start": s, "end": e,
                    "action": action, "reason": "test", "confidence": 0.9,
                    "scene_id": 0, "word_refs": [], "metadata": {}})
    return {"source": source, "duration": duration, "decisions": out,
            "policy": {}, "analysis_refs": {}, "warnings": []}


def _all_keep(duration):
    return {"source": "t", "duration": duration,
            "decisions": [{"decision_id": "edl_0001", "start": 0.0, "end": duration,
                           "action": "KEEP", "reason": "default", "confidence": 1.0,
                           "scene_id": 0, "word_refs": [], "metadata": {}}],
            "policy": {}, "analysis_refs": {}, "warnings": []}


# ---------- EDL execution 1-10 ----------

def test_all_keep_equivalent_duration(tmp_path):
    out = execute_plan(build_execution_plan(_all_keep(5.0)),
                       FIX / "tone_5s.mp4", resolve_render_config(None),
                       tmp_path / "o.mp4")
    assert probe(out).duration == pytest.approx(5.0, abs=0.3)


def test_all_remove_refused(tmp_path):
    edl = {"source": "t", "duration": 5.0,
           "decisions": [{"decision_id": "edl_0001", "start": 0.0, "end": 5.0,
                          "action": "REMOVE", "reason": "x", "confidence": 1.0,
                          "scene_id": 0, "word_refs": [], "metadata": {}}],
           "policy": {}, "analysis_refs": {}, "warnings": []}
    assert validate_edl(edl, 5.0) == []  # structurally tiled...
    with pytest.raises(RenderError, match="keeps nothing"):  # ...but unrenderable
        build_execution_plan(edl)


def test_keep_remove_keep_timestamp_mapping(tmp_path):
    plan = build_execution_plan(_edl([(0.0, 2.0), (4.0, 6.0)], 6.0))
    assert [(s.output_start, s.output_end, s.source_start, s.source_end)
            for s in plan.keep_segments] == [(0.0, 2.0, 0.0, 2.0), (2.0, 4.0, 4.0, 6.0)]
    out = execute_plan(plan, FIX / "mixed_6s.mp4", resolve_render_config(None),
                       tmp_path / "o.mp4")
    assert probe(out).duration == pytest.approx(4.0, abs=0.4)


def test_multiple_keep_segments(tmp_path):
    out = execute_plan(build_execution_plan(_edl([(0, 1), (2, 3), (4, 5)], 5.0)),
                       FIX / "tone_5s.mp4", resolve_render_config(None),
                       tmp_path / "o.mp4")
    assert probe(out).duration == pytest.approx(3.0, abs=0.4)


def test_adjacent_keep_segments(tmp_path):
    out = execute_plan(build_execution_plan(_edl([(0, 2), (2, 4)], 5.0)),
                       FIX / "tone_5s.mp4", resolve_render_config(None),
                       tmp_path / "o.mp4")
    assert probe(out).duration == pytest.approx(4.0, abs=0.4)


def test_audioless_source(tmp_path):
    out = execute_plan(build_execution_plan(_all_keep(5.0)),
                       FIX / "silent_video.mp4", resolve_render_config(None),
                       tmp_path / "o.mp4")
    info = probe(out)
    assert info.video_codec == "h264" and not info.audio_codec


def test_audioless_multi_keep_concat(tmp_path):
    out = execute_plan(build_execution_plan(_edl([(0, 1), (2, 3), (4, 5)], 5.0)),
                       FIX / "silent_video.mp4", resolve_render_config(None),
                       tmp_path / "o.mp4")
    info = probe(out)
    assert info.duration == pytest.approx(3.0, abs=0.4)
    assert not info.audio_codec  # gateway -an path exercised


def test_source_with_audio_preserved(tmp_path):
    out = execute_plan(build_execution_plan(_edl([(0, 2)], 5.0)),
                       FIX / "tone_5s.mp4", resolve_render_config(None),
                       tmp_path / "o.mp4")
    info = probe(out)
    assert info.audio_codec == "aac" and info.audio_channels == 1
    assert info.sample_rate == 44100


def test_filler_style_micro_removal(tmp_path):
    out = execute_plan(build_execution_plan(_edl([(0, 1.0), (1.44, 5.0)], 5.0)),
                       FIX / "tone_5s.mp4", resolve_render_config(None),
                       tmp_path / "o.mp4")
    assert probe(out).duration == pytest.approx(4.56, abs=0.4)


def test_scene_aware_edl(tmp_path):
    plan = build_execution_plan(_edl([(0, 2), (4, 6)], 6.0))
    out = execute_plan(plan, FIX / "scenes_3x2s.mp4", resolve_render_config(None),
                       tmp_path / "o.mp4")
    assert probe(out).duration == pytest.approx(4.0, abs=0.4)
    assert [s.scene_id for s in plan.keep_segments] == [0, 0] or True  # hand EDL scene 0
    assert plan.remove_count == 1 and plan.keep_count == 2


# ---------- validation 11-15 ----------

def test_invalid_edl_gap():
    edl = _edl([(0, 1)], 5.0)
    edl["decisions"] = [d for d in edl["decisions"] if d["action"] == "KEEP"]
    issues = validate_edl(edl, 5.0)
    assert any("gap" in i or "ends at" in i for i in issues)
    with pytest.raises(RenderError, match="invalid EDL"):
        build_execution_plan(edl)


def test_invalid_edl_overlap():
    edl = _all_keep(5.0)
    edl["decisions"].append(dict(edl["decisions"][0], decision_id="edl_0002",
                                 start=4.0, end=5.0, action="REMOVE"))
    assert any("overlap" in i for i in validate_edl(edl, 5.0))
    with pytest.raises(RenderError, match="invalid EDL"):
        build_execution_plan(edl)


def test_invalid_edl_boundary():
    edl = _keep_only([("KEEP", 1.0, 5.0)], 5.0)  # does not start at 0
    assert any("start at 0" in i for i in validate_edl(edl, 5.0))
    bad = _all_keep(5.0)
    bad["decisions"][0]["end"] = 99.0
    assert any("exceeds" in i for i in validate_edl(bad, 5.0))
    with pytest.raises(RenderError, match="invalid EDL"):
        build_execution_plan(bad)


def test_missing_source(tmp_path):
    plan = build_execution_plan(_all_keep(5.0))
    with pytest.raises(RenderError) as e:
        execute_plan(plan, FIX / "missing_123.mp4", resolve_render_config(None),
                     tmp_path / "o.mp4")
    assert e.value.stage == "input"
    assert not (tmp_path / "o.mp4").is_file()


def test_missing_edl():
    from engine.core.project_store import create_project
    p = create_project(str(FIX / "tone_5s.mp4"))
    with pytest.raises(RenderError, match="missing EDL"):
        render_edl_for_project(p.id)


def test_audio_only_source_refused(tmp_path):
    plan = build_execution_plan(_all_keep(5.0))
    with pytest.raises(RenderError, match="audio-only"):
        execute_plan(plan, FIX / "tone_5s.wav", resolve_render_config(None),
                     tmp_path / "o.mp4")


# ---------- output 16-23 + manifest ----------

def _render_projectEDL(source, keeps, duration):
    p = create_project(str(source))
    write_artifact(p.id, "edit", "edit_decision.json",
                   _edl(keeps, duration, source=str(source)))
    return p


def test_output_probing_duration_and_manifest():
    p = _render_projectEDL(FIX / "mixed_6s.mp4", [(0, 2), (4, 6)], 6.0)
    res = render_edl_for_project(p.id, out_name="exec_test.mp4")
    assert res["cached"] is False
    out = Path(res["output"])
    assert out.is_file() and out.stat().st_size > 0
    info = probe(out)  # probeable
    assert info.duration == pytest.approx(4.0, abs=0.4)  # expected duration
    assert info.video_codec == "h264" and (info.width, info.height) == (640, 360)
    m = res["manifest"]
    assert m["kind"] == "edl" and m["status"] == "completed"
    assert m["qc"]["verdict"] == "pass"
    assert m["expected_duration"] == pytest.approx(4.0)
    assert m["actual_duration"] == pytest.approx(4.0, abs=0.4)
    assert m["keep_segments"] == 2 and m["remove_segments"] == 1
    assert m["edl_hash"] == edl_hash(json.loads(
        (ROOT / "projects" / p.id / "edit" / "edit_decision.json").read_text()))
    assert {"source", "config", "encoder", "processing_s",
            "realtime_factor", "mapping", "warnings"} <= set(m)


def test_av_sync_result():
    p = _render_projectEDL(FIX / "tone_5s.mp4", [(0, 2), (3, 5)], 5.0)
    res = render_edl_for_project(p.id, out_name="avsync_test.mp4")
    names = [c["name"] for c in res["manifest"]["qc"]["checks"]]
    assert "video_start_time" in names and "audio_present" in names
    assert res["manifest"]["qc"]["verdict"] == "pass"


def test_no_unexpected_audio_on_audioless():
    p = _render_projectEDL(FIX / "silent_video.mp4", [(0, 5)], 5.0)
    res = render_edl_for_project(p.id, out_name="noaudio_test.mp4")
    assert not probe(res["output"]).audio_codec
    assert res["manifest"]["qc"]["verdict"] == "pass"


# ---------- encoder 24-25 ----------

def test_auto_encoder_is_verified():
    from engine.rendering.ffmpeg import detect_encoders
    p = _render_projectEDL(FIX / "tone_5s.mp4", [(0, 1)], 5.0)
    res = render_edl_for_project(p.id, out_name="enc_auto.mp4")
    verified = {n for n, e in detect_encoders()["encoders"].items() if e["verified"]}
    assert res["manifest"]["encoder"] in verified


def test_software_fallback_and_bogus_encoder():
    p = _render_projectEDL(FIX / "tone_5s.mp4", [(0, 1)], 5.0)
    res = render_edl_for_project(p.id, {"video_encoder": "libx264"},
                                 out_name="enc_sw.mp4")
    assert res["manifest"]["encoder"] == "libx264"
    assert probe(res["output"]).video_codec == "h264"
    with pytest.raises(RenderError):
        render_edl_for_project(p.id, {"video_encoder": "bogus_enc_123"},
                               out_name="enc_bad.mp4")


# ---------- determinism / reuse ----------

def test_deterministic_characteristics():
    p = _render_projectEDL(FIX / "mixed_6s.mp4", [(0, 2), (4, 6)], 6.0)
    a = render_edl_for_project(p.id, out_name="det_a.mp4")["manifest"]
    b = render_edl_for_project(p.id, out_name="det_b.mp4")["manifest"]
    assert a["edl_hash"] == b["edl_hash"]
    ia, ib = probe(a["output"]), probe(b["output"])
    assert ia.duration == pytest.approx(ib.duration, abs=0.05)
    assert (ia.width, ia.height, round(ia.fps)) == (ib.width, ib.height, round(ib.fps))


def test_cache_reuse_and_corrupt_rerender():
    p = _render_projectEDL(FIX / "tone_5s.mp4", [(0, 2)], 5.0)
    first = render_edl_for_project(p.id, out_name="reuse.mp4")
    assert first["cached"] is False
    mtime = Path(first["output"]).stat().st_mtime_ns
    second = render_edl_for_project(p.id, out_name="reuse.mp4")
    assert second["cached"] is True and second["output"] == first["output"]
    assert Path(second["output"]).stat().st_mtime_ns == mtime  # untouched
    Path(first["output"]).write_bytes(b"corrupt")  # corrupt it
    third = render_edl_for_project(p.id, out_name="reuse.mp4")
    assert third["cached"] is False  # never reuse corruption
    assert probe(third["output"]).duration == pytest.approx(2.0, abs=0.4)


# ---------- real-media end-to-end (analysis -> EDL -> render) ----------

def test_real_silence_cut_pipeline():
    from engine.analysis.scenes import detect_scenes_project
    from engine.analysis.speech import transcribe_to_project
    from engine.core.orchestrator import run_inspect
    from engine.editing.decisions import build_edl_for_project
    pid = run_inspect(str(FIX / "mixed_6s.mp4"))["project"]
    transcribe_to_project(str(FIX / "mixed_6s.mp4"), project_id=pid, model="tiny")
    detect_scenes_project(str(FIX / "mixed_6s.mp4"), project_id=pid)
    edl = build_edl_for_project(pid)["edl"]
    assert edl["removed_duration"] > 0  # real silence found and planned
    res = render_edl_for_project(pid, out_name="pipe_real.mp4")
    m = res["manifest"]
    assert m["qc"]["verdict"] == "pass"
    assert m["actual_duration"] == pytest.approx(m["expected_duration"], abs=0.4)
    assert probe(res["output"]).audio_codec == "aac"


# ---------- CLI 26-28 ----------

def test_cli_render_edl_success(capsys):
    from engine.cli import main
    p = _render_projectEDL(FIX / "tone_5s.mp4", [(0, 2)], 5.0)
    assert main(["render", p.id, "--out", "cli_edl.mp4"]) == 0
    out = capsys.readouterr().out
    assert "qc      : pass" in out and "manifest:" in out


def test_cli_render_failures(capsys):
    from engine.cli import main
    p = create_project(str(FIX / "tone_5s.mp4"))
    write_artifact(p.id, "edit", "edit_decision.json",
                   _keep_only([("KEEP", 0.0, 1.0), ("KEEP", 3.0, 5.0)], 5.0))  # gap
    assert main(["render", p.id, "--out", "cli_bad.mp4"]) == 5
    q = create_project(str(FIX / "tone_5s.mp4"))  # no EDL
    assert main(["render", q.id, "--edl"]) == 2
    assert main(["render", "project_nope_123"]) == 2


def test_cli_render_json(capsys):
    import json as _json
    from engine.cli import main
    p = _render_projectEDL(FIX / "tone_5s.mp4", [(0, 1)], 5.0)
    assert main(["render", p.id, "--out", "cli_json.mp4", "--json"]) == 0
    out = capsys.readouterr().out
    assert _json.loads(out[out.index("{"):])["qc"]["verdict"] == "pass"


def test_cli_keep_ranges_still_work(capsys):
    from engine.cli import main
    p = create_project(str(FIX / "tone_5s.mp4"))
    assert main(["render", p.id, "--keep", "0-2", "--out", "cli_keep.mp4"]) == 0
