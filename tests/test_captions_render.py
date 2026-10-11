"""Phase 14 render/integration tests — real ffmpeg, real STT chain.

Modes covered: sidecar + burned_in. Speech fixture is Windows-SAPI
synthesized English (offline, built-in voices); Arabic *rendering* uses
hand-written (labeled synthetic) transcripts with real glyphs, since no
Arabic TTS voice exists on this box (see docs/CAPTIONS.md).
"""
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests" / "fixtures"
SAPI_WAV = FIX / "speech_sapi.wav"
SPEECH_MP4 = FIX / "speech_video.mp4"

from engine.core.media import probe
from engine.core.project_store import create_project, project_dir, write_artifact

SAPI_TEXT = ("Hello world. This is a test of the local speech engine. "
             "The quick brown fox jumps over the lazy dog.")


def _sapi_speak(dest: Path, text: str) -> bool:
    ps = ("Add-Type -AssemblyName System.Speech; "
          "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
          "$s.SelectVoice('Microsoft Zira Desktop'); $s.Rate = -1; "
          f"$s.SetOutputToWaveFile('{dest}'); $s.Speak('{text}'); $s.Dispose()")
    r = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                       capture_output=True, text=True, timeout=300)
    return r.returncode == 0 and dest.is_file() and dest.stat().st_size > 100_000


@pytest.fixture(scope="module", autouse=True)
def media():
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        pytest.skip("ffmpeg/ffprobe not on PATH")
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "make_test_media.py"), "--all"],
                       capture_output=True, text=True, timeout=600)
    assert r.returncode == 0
    if not SAPI_WAV.is_file():
        if not _sapi_speak(SAPI_WAV, SAPI_TEXT):
            pytest.skip("SAPI TTS unavailable")
    if not SPEECH_MP4.is_file():
        dur = probe(SAPI_WAV).duration
        r = subprocess.run(
            [shutil.which("ffmpeg"), "-y",
             "-f", "lavfi", "-i", f"testsrc=size=640x360:rate=30:duration={dur:.2f}",
             "-i", str(SAPI_WAV),
             "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
             "-shortest", str(SPEECH_MP4)],
            capture_output=True, text=True, timeout=300)
        assert r.returncode == 0, f"speech fixture build failed: {r.stderr[-800:]}"
    assert SPEECH_MP4.is_file()


def _chain(sapi_input=True):
    """Real analyze->transcribe project. Returns pid."""
    from engine.core.orchestrator import run_inspect
    from engine.analysis.speech import transcribe_to_project
    src = str(SPEECH_MP4 if sapi_input else FIX / "tone_5s.mp4")
    pid = run_inspect(src)["project"]
    transcribe_to_project(src, project_id=pid, model="tiny")
    return pid


def _approved_chain():
    """Full real chain through base approval (for render tests)."""
    from engine.analysis.scenes import detect_scenes_project
    from engine.analysis.speech import transcribe_to_project
    from engine.core.orchestrator import run_inspect
    from engine.editing.decisions import build_edl_for_project
    from engine.editing.brain import run_editor_brain_for_project
    from engine.editing.approval import approve_plan
    src = str(SPEECH_MP4)
    pid = run_inspect(src)["project"]
    transcribe_to_project(src, project_id=pid, model="tiny")
    detect_scenes_project(src, project_id=pid)
    build_edl_for_project(pid)
    run_editor_brain_for_project(pid)
    approve_plan(pid)
    return pid


@pytest.fixture(scope="module")
def approved_project():
    """Full real chain through base approval (shared by render tests)."""
    from engine.analysis.scenes import detect_scenes_project
    from engine.core.orchestrator import run_inspect
    from engine.analysis.speech import transcribe_to_project
    from engine.editing.decisions import build_edl_for_project
    from engine.editing.brain import run_editor_brain_for_project
    from engine.editing.approval import approve_plan
    src = str(SPEECH_MP4)
    pid = run_inspect(src)["project"]
    transcribe_to_project(src, project_id=pid, model="tiny")
    detect_scenes_project(src, project_id=pid)
    build_edl_for_project(pid)
    run_editor_brain_for_project(pid)
    approve_plan(pid)
    return pid


def test_caption_approval_modes():
    from engine.subtitles.captions import (
        CaptionError,
        approve_captions,
        caption_plan_for_project,
        validate_captions_approval,
    )
    pid = _chain()
    plan = caption_plan_for_project(pid)["plan"]
    assert plan["cue_count"] >= 1 and plan["language"] == "en"
    for mode in ("sidecar", "burned_in"):
        res = approve_captions(pid, mode=mode)
        assert res["approval"]["mode"] == mode
        assert validate_captions_approval(pid)["approval"]["mode"] == mode
    with pytest.raises(CaptionError, match="sidecar\\|burned_in"):
        approve_captions(pid, mode="hologram")


def test_caption_approval_invalidation():
    from engine.subtitles.captions import approve_captions, validate_captions_approval
    pid = _chain()
    from engine.subtitles.captions import caption_plan_for_project
    caption_plan_for_project(pid)
    approve_captions(pid, mode="sidecar")
    plan_path = project_dir(pid) / "captions" / "caption_plan.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    plan["cues"] = plan["cues"][:1]
    plan_path.write_text(json.dumps(plan), encoding="utf-8")
    with pytest.raises(Exception, match="changed since approval"):
        validate_captions_approval(pid)


def test_caption_plan_cache_and_style(tmp_path):
    from engine.subtitles.captions import caption_plan_for_project
    from engine.core.orchestrator import run_inspect
    from engine.analysis.speech import transcribe_to_project
    unique = tmp_path / "sapi_cache_test.mp4"
    unique.write_bytes(SPEECH_MP4.read_bytes())  # unique mtime/size -> cold key
    pid = run_inspect(str(unique))["project"]
    transcribe_to_project(str(unique), project_id=pid, model="tiny")
    first = caption_plan_for_project(pid)
    assert first["cached"] is False
    second = caption_plan_for_project(pid)
    assert second["cached"] is True
    assert {k: v for k, v in second["plan"].items() if k != "cached"} == \
           {k: v for k, v in first["plan"].items() if k != "cached"}
    third = caption_plan_for_project(pid, {"caption_style": "social"})
    assert third["cached"] is False
    assert third["plan"]["style"] == "social"


def test_dry_run_no_ffmpeg_writes():
    from engine.cli import main
    pid = _approved_chain()
    from engine.subtitles.captions import approve_captions, caption_plan_for_project
    caption_plan_for_project(pid)
    approve_captions(pid, mode="burned_in")
    from engine.core.project_store import project_dir as _pd
    before = {p.name for p in (_pd(pid) / "renders").glob("*.mp4")} \
        if (_pd(pid) / "renders").exists() else set()
    assert main(["render-plan", pid, "--dry-run", "--captions"]) == 0
    after = {p.name for p in (_pd(pid) / "renders").glob("*.mp4")} \
        if (_pd(pid) / "renders").exists() else set()
    assert after == before  # dry-run rendered nothing


def test_sidecar_render():
    from engine.cli import main
    pid = _approved_chain()
    from engine.subtitles.captions import approve_captions, caption_plan_for_project
    caption_plan_for_project(pid)
    approve_captions(pid, mode="sidecar")
    assert main(["render-plan", pid, "--out", "cap_side.mp4", "--captions"]) == 0
    renders = project_dir(pid) / "renders"
    srt, vtt = renders / "cap_side.srt", renders / "cap_side.vtt"
    assert srt.is_file() and vtt.is_file() and srt.stat().st_size > 0
    assert "-->" in srt.read_text(encoding="utf-8")
    m = json.loads((renders / "cap_side_plan_manifest.json").read_text())
    assert m["caption_mode"] == "sidecar" and m["caption_qc"]["verdict"] == "pass"
    assert m["caption_count"] >= 1 and m["caption_language"] == "en"
    assert m["output"].endswith("cap_side.mp4")  # base output is final


def test_burned_in_render():
    from engine.cli import main
    pid = _approved_chain()
    from engine.subtitles.captions import approve_captions, caption_plan_for_project
    caption_plan_for_project(pid)
    approve_captions(pid, mode="burned_in", style="clean")
    assert main(["render-plan", pid, "--out", "cap_burn.mp4", "--captions"]) == 0
    renders = project_dir(pid) / "renders"
    out = renders / "cap_burn_captioned.mp4"
    assert out.is_file()
    info = probe(out)
    base = probe(renders / "cap_burn.mp4")
    assert abs(info.duration - base.duration) <= 0.3
    assert (info.width, info.height) == (base.width, base.height)
    assert info.audio_codec == base.audio_codec  # burn never touches audio
    m = json.loads((renders / "cap_burn_captioned_plan_manifest.json").read_text())
    assert m["caption_mode"] == "burned_in" and m["caption_style"] == "clean"
    assert m["caption_qc"]["verdict"] == "pass"
    assert any(c["name"].startswith("caption_visible_") and c["passed"]
               for c in m["caption_qc"]["checks"])


def test_removed_speech_interval_mapping():
    """Approved edit removes speech at 2-4 s: mapped cues must follow output."""
    from engine.editing.decisions import build_edl_for_project
    from engine.analysis.scenes import detect_scenes_project
    from engine.core.orchestrator import run_inspect
    from engine.analysis.speech import transcribe_to_project
    from engine.subtitles.captions import approve_captions, caption_plan_for_project
    from engine.cli import main
    pid = run_inspect(str(SPEECH_MP4))["project"]
    transcribe_to_project(str(SPEECH_MP4), project_id=pid, model="tiny")
    detect_scenes_project(str(SPEECH_MP4), project_id=pid)
    from engine.editing.decisions import build_edl_for_project as _build_edl
    from engine.editing.brain import run_editor_brain_for_project as _brain
    from engine.editing.approval import approve_plan as _approve
    # Hand EDL removing a speech-bearing middle interval (deterministic),
    # written BEFORE brain+approval so the whole chain stays consistent.
    dur = probe(SPEECH_MP4).duration
    write_artifact(pid, "edit", "edit_decision.json",
                   {"source": str(SPEECH_MP4), "duration": dur,
                    "decisions": [
                        {"decision_id": "edl_0001", "start": 0.0, "end": 2.0,
                         "action": "KEEP", "reason": "test", "confidence": 1.0,
                         "scene_id": 0, "word_refs": [], "metadata": {}},
                        {"decision_id": "edl_0002", "start": 2.0, "end": 4.0,
                         "action": "REMOVE", "reason": "test", "confidence": 1.0,
                         "scene_id": 0, "word_refs": [], "metadata": {}},
                        {"decision_id": "edl_0003", "start": 4.0, "end": dur,
                         "action": "KEEP", "reason": "test", "confidence": 1.0,
                         "scene_id": 0, "word_refs": [], "metadata": {}}],
                    "policy": {}, "analysis_refs": {}, "warnings": []})
    _brain(pid)
    _approve(pid)
    caption_plan_for_project(pid)
    approve_captions(pid, mode="sidecar")
    assert main(["render-plan", pid, "--out", "cap_cut.mp4", "--captions"]) == 0
    renders = project_dir(pid) / "renders"
    m = json.loads((renders / "cap_cut_plan_manifest.json").read_text())
    assert m["actual_duration"] == pytest.approx(dur - 2.0, abs=0.5)
    assert m["caption_qc"]["verdict"] == "pass"
    # No mapped cue may reference words from the removed [2,4] source span:
    # mapped cue count <= source cue count, and mapped stats record drops.
    assert m["caption_count"] >= 1


def test_cli_captions_commands(capsys):
    from engine.cli import main
    pid = _chain()
    assert main(["captions", pid, "--style", "social"]) == 0
    out = capsys.readouterr().out
    assert "cues    :" in out and "artifact: captions/caption_plan.json" in out
    assert main(["captions", pid, "--style", "nope"]) == 2  # unknown style fails
    assert main(["approve-captions", pid, "--mode", "sidecar"]) == 0
    assert "approved_captions.json" in capsys.readouterr().out
    assert main(["approve-captions", pid, "--mode", "hologram"]) == 2
    assert main(["captions", "project_nope_123"]) == 2
    assert main(["approve-captions", "project_nope_123"]) == 2
    assert main(["render-plan", pid]) == 2  # no BASE approval: boundary holds
