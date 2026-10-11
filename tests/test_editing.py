"""Phase 8 tests — edit decision engine (ANALYSIS -> EDL, NO rendering).

Unit tests use hand-built analysis dicts (deterministic). Integration tests
feed REAL Phase 3/5/6/7 artifacts. Nothing here renders video.
"""
import json
import shutil
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests" / "fixtures"

from engine.core.project_store import create_project, write_artifact
from engine.editing.decisions import (
    EditError,
    build_edl,
    build_edl_for_project,
    resolve_policy,
)

POLICY = resolve_policy(None)


def _audio(silences, duration, path="test.mp4"):
    return {"path": path, "audio_present": True, "audio_duration": duration,
            "silence": [{"start": s, "end": e, "duration": e - s} for s, e in silences],
            "non_silent": [], "silence_total_s": sum(e - s for s, e in silences)}


def _transcript(words, fillers=(), language="en", duration=12.0):
    return {"language": language, "duration": duration,
            "segments": [{"id": 0, "text": " ".join(w[0] for w in words),
                          "start": 0.0, "end": duration, "duration": duration,
                          "words": [{"word": w, "start": s, "end": e, "probability": p}
                                    for w, s, e, p in words]}],
            "fillers": [{"word": w, "start": s, "end": e, "segment_id": 0}
                        for w, s, e in fillers],
            "skipped_reason": ""}


def _scenes(spans, duration):
    return {"duration": duration,
            "scenes": [{"scene_id": i, "start": s, "end": e, "duration": e - s,
                        "start_frame": 0, "end_frame": 0}
                       for i, (s, e) in enumerate(spans)]}


def _acts(edl):
    return [(d.action, d.start, d.end, d.reason) for d in edl.decisions]


# ---------- spec example: source coordinates preserved ----------

def test_spec_example_keeps_source_timeline():
    words = [("hello", 0.5, 1.0, 0.9), ("world", 8.5, 9.0, 0.9)]
    edl = build_edl(_audio([(5.0, 8.0)], 12.0), _transcript(words),
                    _scenes([(0.0, 12.0)], 12.0), 12.0, POLICY)
    assert _acts(edl) == [("KEEP", 0.0, 5.15, "default"),
                          ("REMOVE", 5.15, 7.85, "long_silence"),
                          ("KEEP", 7.85, 12.0, "default")]
    assert edl.kept_duration + edl.removed_duration == pytest.approx(12.0)
    assert edl.removal_ratio == pytest.approx(2.7 / 12.0)


def test_tiny_silence_kept():
    edl = build_edl(_audio([(5.0, 5.5)], 12.0), _transcript([]),
                    _scenes([(0.0, 12.0)], 12.0), 12.0, POLICY)
    assert len(edl.decisions) == 1 and edl.decisions[0].action == "KEEP"
    assert edl.removed_duration == 0.0


# ---------- filler rule ----------

def test_filler_removed_with_padding():
    words = [("um", 10.20, 10.48, 0.9), ("hello", 11.0, 11.5, 0.95)]
    edl = build_edl(_audio([], 12.0), _transcript(words, [("um", 10.20, 10.48)]),
                    _scenes([(0.0, 12.0)], 12.0), 12.0, POLICY)
    rem = [d for d in edl.decisions if d.action == "REMOVE"]
    assert len(rem) == 1
    assert (rem[0].start, rem[0].end) == (10.12, 10.56)
    assert rem[0].reason == "filler_word" and rem[0].confidence == 0.9
    assert rem[0].word_refs[0]["word"] == "um"


def test_filler_overlapping_speech_kept_with_warning():
    words = [("um", 10.20, 10.48, 0.9), ("oh", 10.30, 10.60, 0.9)]
    edl = build_edl(_audio([], 12.0), _transcript(words, [("um", 10.20, 10.48)]),
                    _scenes([(0.0, 12.0)], 12.0), 12.0, POLICY)
    assert all(d.action == "KEEP" for d in edl.decisions)
    assert any("overlaps speech" in w for w in edl.warnings)


def test_no_fillers_policy_flag():
    words = [("um", 10.20, 10.48, 0.9)]
    pol = resolve_policy({"edit_remove_fillers": False})
    edl = build_edl(_audio([], 12.0), _transcript(words, [("um", 10.20, 10.48)]),
                    _scenes([(0.0, 12.0)], 12.0), 12.0, pol)
    assert all(d.action == "KEEP" for d in edl.decisions)


# ---------- scene awareness ----------

def test_removal_splits_at_scene_boundary():
    words = [("a", 0.5, 1.0, 0.9), ("b", 25.0, 26.0, 0.9)]
    edl = build_edl(_audio([(8.0, 13.0)], 30.0), _transcript(words),
                    _scenes([(0.0, 10.0), (10.0, 20.0), (20.0, 30.0)], 30.0), 30.0, POLICY)
    rem = [d for d in edl.decisions if d.action == "REMOVE"]
    assert [(r.start, r.end, r.scene_id) for r in rem] == [(8.15, 10.0, 0), (10.0, 12.85, 1)]
    assert all(d.action == "KEEP" or d.scene_id >= 0 for d in edl.decisions)
    assert not any(d.start < 10.0 < d.end for d in edl.decisions)  # no straddle


# ---------- priority + merging ----------

def test_filler_wins_over_silence_overlap():
    words = [("um", 10.90, 11.10, 0.85), ("hi", 0.5, 1.0, 0.9)]
    edl = build_edl(_audio([(10.0, 12.0)], 12.0), _transcript(words, [("um", 10.90, 11.10)]),
                    _scenes([(0.0, 12.0)], 12.0), 12.0, POLICY)
    rem = [d for d in edl.decisions if d.action == "REMOVE"]
    assert [(r.start, r.end, r.reason) for r in rem] == [
        (10.15, 10.82, "long_silence"), (10.82, 11.18, "filler_word"),
        (11.18, 11.85, "long_silence")]


def test_overlapping_silences_merge():
    edl = build_edl(_audio([(5.0, 8.0), (7.0, 10.0)], 12.0), _transcript([]),
                    _scenes([(0.0, 12.0)], 12.0), 12.0, POLICY)
    rem = [d for d in edl.decisions if d.action == "REMOVE"]
    assert len(rem) == 1 and (rem[0].start, rem[0].end) == (5.15, 9.85)


# ---------- safety: invalid + missing ----------

def test_invalid_timestamps_kept_with_warnings():
    audio = _audio([], 12.0)
    audio["silence"] = [{"start": 9.0, "end": 7.0, "duration": -2.0}]
    tr = _transcript([], [("um", 5.0, 4.0)])
    edl = build_edl(audio, tr, _scenes([(0.0, 12.0)], 12.0), 12.0, POLICY)
    assert all(d.action == "KEEP" for d in edl.decisions)
    assert len(edl.warnings) >= 2


def test_missing_analysis_fails_clearly():
    with pytest.raises(EditError, match="audio"):
        build_edl({}, _transcript([]), _scenes([(0, 12)], 12), 12.0, POLICY)
    with pytest.raises(EditError, match="transcript"):
        build_edl(_audio([], 12), None, _scenes([(0, 12)], 12), 12.0, POLICY)
    with pytest.raises(EditError, match="scene"):
        build_edl(_audio([], 12), _transcript([]), {"scenes": []}, 12.0, POLICY)
    with pytest.raises(EditError, match="duration"):
        build_edl(_audio([], 12), _transcript([]), _scenes([(0, 12)], 12), 0, POLICY)


def test_policy_validation():
    with pytest.raises(EditError):
        resolve_policy({"edit_silence_pad_before": -1.0})
    with pytest.raises(EditError):
        resolve_policy({"edit_min_silence_s": 0})


def test_deterministic_output():
    kwargs = dict(audio=_audio([(5.0, 8.0)], 12.0),
                  transcript=_transcript([("um", 10.2, 10.48, 0.9)],
                                         [("um", 10.2, 10.48)]),
                  scenes=_scenes([(0.0, 12.0)], 12.0), duration=12.0, policy=POLICY)
    a, b = asdict(build_edl(**kwargs)), asdict(build_edl(**kwargs))
    a.pop("generated_at"), b.pop("generated_at")  # wall-clock by design
    assert a == b


# ---------- project / cache / CLI ----------

def _write_project_artifacts(pid, audio, transcript, scenes):
    write_artifact(pid, "analysis", "audio_analysis.json", audio)
    write_artifact(pid, "analysis", "transcript.json", transcript)
    write_artifact(pid, "analysis", "scenes.json", scenes)


def test_project_cache_and_policy_invalidation(tmp_path):
    p = create_project("test.mp4")
    # Unique marker: the edit cache key hashes analysis content, which is
    # identical across runs by design -> salt it for a guaranteed-cold key.
    import time
    audio = _audio([(5.0, 8.0)], 12.0, path=f"test_{time.time_ns()}.mp4")
    _write_project_artifacts(p.id, audio, _transcript([]),
                             _scenes([(0.0, 12.0)], 12.0))
    first = build_edl_for_project(p.id)
    assert first["cached"] is False and first["edl"]["removed_duration"] > 0
    second = build_edl_for_project(p.id)
    assert second["cached"] is True
    assert {k: v for k, v in second["edl"].items() if k != "cached"} == \
           {k: v for k, v in first["edl"].items() if k != "cached"}
    other = build_edl_for_project(p.id, {"edit_min_silence_s": 5.0})
    assert other["cached"] is False  # policy change -> new entry
    assert other["edl"]["removed_duration"] == 0.0  # 3 s silence now kept
    artifact = ROOT / "projects" / p.id / "edit" / "edit_decision.json"
    assert artifact.is_file()


def _isolate(pid):
    # Project ids have 1-second granularity: a same-second create_project
    # reuses the directory, so wipe analysis state to guarantee preconditions.
    import shutil
    shutil.rmtree(ROOT / "projects" / pid / "analysis", ignore_errors=True)
    (ROOT / "projects" / pid / "analysis").mkdir(parents=True, exist_ok=True)


def test_project_missing_artifacts_fails():
    p = create_project("test.mp4")
    _isolate(p.id)
    with pytest.raises(EditError, match="audio_analysis"):
        build_edl_for_project(p.id)


def test_cli_edit(capsys):
    from engine.cli import main
    p = create_project("test.mp4")
    _write_project_artifacts(p.id, _audio([(5.0, 8.0)], 12.0), _transcript([]),
                             _scenes([(0.0, 12.0)], 12.0))
    assert main(["edit", p.id]) == 0
    out = capsys.readouterr().out
    assert "REMOVE" in out and "nothing rendered" in out
    assert main(["edit", "project_nope_123"]) == 2
    q = create_project("test.mp4")  # no artifacts
    _isolate(q.id)
    assert main(["edit", q.id]) == 2


def test_video_project_without_scenes_fails_loudly():
    p = create_project("test.mp4")
    _isolate(p.id)
    write_artifact(p.id, "analysis", "media_info.json",
                   {"path": "test.mp4", "video_codec": "h264", "duration": 12.0})
    write_artifact(p.id, "analysis", "audio_analysis.json", _audio([], 12.0))
    write_artifact(p.id, "analysis", "transcript.json", _transcript([]))
    with pytest.raises(EditError, match="scenes"):
        build_edl_for_project(p.id)


# ---------- real-analysis integration (no rendering) ----------

@pytest.fixture(scope="module")
def real_projects():
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        pytest.skip("ffmpeg/ffprobe not on PATH")
    from engine.analysis.audio import analyze_audio
    from engine.analysis.scenes import detect_scenes, detect_scenes_project
    from engine.analysis.speech import transcribe_to_project
    from engine.core.media import probe
    from engine.core.orchestrator import run_inspect
    out = {}
    # Speech project: real media + audio + tiny-model transcript (audio-only:
    # scenes are synthesized by the engine with a recorded warning).
    sapi = run_inspect(str(FIX / "speech_sapi.wav"))["project"]
    transcribe_to_project(str(FIX / "speech_sapi.wav"), project_id=sapi, model="tiny")
    out["sapi"] = sapi
    # Silence project: long real silence -> genuine REMOVE decision.
    sil = run_inspect(str(FIX / "silence_5s.wav"))["project"]
    transcribe_to_project(str(FIX / "silence_5s.wav"), project_id=sil, model="tiny")
    out["silence"] = sil
    # Audio-less project: valid all-KEEP EDL.
    na = run_inspect(str(FIX / "silent_video.mp4"))["project"]
    transcribe_to_project(str(FIX / "silent_video.mp4"), project_id=na, model="tiny")
    detect_scenes_project(str(FIX / "silent_video.mp4"), project_id=na)
    out["noaudio"] = na
    return out


def test_real_speech_project_edl_valid(real_projects):
    res = build_edl_for_project(real_projects["sapi"])
    e = res["edl"]
    # Structural guarantees on real data (SAPI has leading/trailing silence,
    # so removals MAY exist — all must be long_silence, never fillers).
    assert e["kept_duration"] + e["removed_duration"] == pytest.approx(e["duration"])
    assert e["removal_ratio"] < 0.5
    assert {d["reason"] for d in e["decisions"]} <= {"default", "long_silence", "filler_word"}
    assert not any(d["reason"] == "filler_word" for d in e["decisions"])
    assert isinstance(e["warnings"], list)
    # Contiguity on the source timeline: decisions tile [0, duration].
    bounds = [(d["start"], d["end"]) for d in e["decisions"]]
    assert bounds[0][0] == pytest.approx(0.0)
    assert bounds[-1][1] == pytest.approx(e["duration"])
    for (_, prev_end), (start, _) in zip(bounds, bounds[1:]):
        assert start == pytest.approx(prev_end)


def test_real_silence_project_removes_interior(real_projects):
    res = build_edl_for_project(real_projects["silence"])
    e = res["edl"]
    rem = [d for d in e["decisions"] if d["action"] == "REMOVE"]
    assert len(rem) == 1 and rem[0]["reason"] == "long_silence"
    assert (rem[0]["start"], rem[0]["end"]) == pytest.approx((0.15, 4.85), abs=0.05)
    # Source coordinates preserved: head and tail KEEPs flank the removal.
    acts = [(d["action"], d["start"], d["end"]) for d in e["decisions"]]
    assert acts[0][0] == "KEEP" and acts[-1][0] == "KEEP"
    assert any("audio-only" in w for w in e["warnings"])  # synth path recorded


def test_real_noaudio_project_all_keep(real_projects):
    res = build_edl_for_project(real_projects["noaudio"])
    assert res["edl"]["removed_duration"] == 0.0
