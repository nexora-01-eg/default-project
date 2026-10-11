"""Phase 12 tests — editor brain (planning only, NO rendering).

Hand-built analysis dicts for determinism; real full-chain at the end.
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

from engine.core.project_store import create_project, write_artifact
from engine.editing.brain import (
    BrainError,
    build_editor_plan,
    resolve_conflict,
    resolve_style,
    run_editor_brain_for_project,
)


def _audio(silences=(), duration=12.0, loud_i="-16.0"):
    return {"path": "t", "audio_present": True, "audio_duration": duration,
            "silence": [{"start": s, "end": e, "duration": e - s} for s, e in silences],
            "loudness": {"input_i": loud_i}}


def _transcript(words, fillers=(), language="en", duration=12.0):
    return {"language": language, "duration": duration,
            "segments": [{"id": 0, "text": " ".join(w[0] for w in words),
                          "start": 0.0, "end": duration,
                          "words": [{"word": w, "start": s, "end": e, "probability": p}
                                    for w, s, e, p in words]}],
            "fillers": [{"word": w, "start": s, "end": e, "segment_id": 0}
                        for w, s, e in fillers],
            "skipped_reason": ""}


def _scenes(spans, duration=None):
    dur = duration if duration is not None else spans[-1][1]
    return {"duration": dur,
            "scenes": [{"scene_id": i, "start": s, "end": e, "duration": e - s,
                        "start_frame": 0, "end_frame": 0} for i, (s, e) in enumerate(spans)]}


def _edl(decisions, duration, source="t"):
    seq = 0
    out = []
    for action, s, e, reason in decisions:
        seq += 1
        out.append({"decision_id": f"edl_{seq:04d}", "start": s, "end": e,
                    "action": action, "reason": reason, "confidence": 0.9,
                    "scene_id": 0, "word_refs": [], "metadata": {}})
    return {"source": source, "duration": duration, "decisions": out,
            "policy": {}, "analysis_refs": {}, "warnings": []}


def _intel(safety=(), reps=(), jumps=()):
    return {"cut_safety": [{"decision_id": d, "status": s, "evidence": []}
                           for d, s in safety],
            "repetitions": list(reps), "jump_cuts": list(jumps)}


def _visual(summaries=(), continuity=()):
    return {"scene_summaries": list(summaries), "continuity": list(continuity),
            "static_spans": []}


def _vsum(sid, motion=0.0):
    return {"scene_id": sid, "motion_mean": motion}


def _plan(**kw):
    base = dict(audio=_audio(), transcript=_transcript([]),
                scenes=_scenes([(0, 12)], 12.0),
                edl=_edl([("KEEP", 0, 12, "default")], 12.0),
                intel=_intel(), visual=None, refined=None,
                duration=12.0, style=resolve_style("general"))
    base.update(kw)
    return build_editor_plan(**base)


# ---------- styles ----------

def test_styles_resolve_and_aggressive():
    assert len(__import__("engine.editing.brain", fromlist=["STYLES"]).STYLES) == 11
    g = resolve_style("general")
    assert (g.pacing, g.broll_intensity, g.repetition_policy) == ("normal", "low", "investigate")
    assert resolve_style("podcast").broll_intensity == "off"
    assert resolve_style("social_short").pacing == "brisk"
    a = resolve_style("general", aggressive=True)
    assert a.silence_tolerance_s == g.silence_tolerance_s * 0.5
    assert a.broll_intensity == "medium"  # stepped up, still explicit
    t = resolve_style("general", target_duration=60.0)
    assert t.target_duration == 60.0
    with pytest.raises(BrainError):
        resolve_style("nope")
    with pytest.raises(BrainError):
        resolve_style("general", target_duration=-5)


# ---------- hook ----------

def test_hook_strong_opening():
    words = [("what", 0.5, 0.8, 0.9), ("is", 0.8, 1.0, 0.9), ("this?", 1.0, 1.5, 0.9)]
    plan = _plan(transcript=_transcript(words))
    h = plan.hook
    assert h.recommended_opening_strategy == "keep_as_is"
    assert any(s["signal"] == "question_present" and s["value"] for s in h.hook_strength_signals)
    assert h.removable_preamble == []


def test_hook_preamble():
    words = [("um", 2.0, 2.3, 0.9), ("hello", 3.0, 3.5, 0.9)]
    plan = _plan(audio=_audio([(0.0, 1.8)]),
                 transcript=_transcript(words, [("um", 2.0, 2.3)]))
    h = plan.hook
    assert h.recommended_opening_strategy == "trim_preamble"
    assert h.removable_preamble and h.removable_preamble[0]["reason"] == "leading_silence"


def test_hook_weak_and_missing_words():
    plan = _plan(transcript=_transcript([]))
    assert plan.hook.recommended_opening_strategy == "investigate"
    assert "no transcript words" in plan.hook.limitation


# ---------- structure ----------

def test_structure_simple_and_cta():
    words = [("hello", 0.5, 1.0, 0.9), ("bye", 11.0, 11.5, 0.9)]
    plan = _plan(transcript=_transcript(words), scenes=_scenes([(0, 12)], 12.0))
    assert [s.classification for s in plan.story_structure] == ["hook"]
    words2 = words + [("subscribe", 6.0, 6.5, 0.9)]
    plan2 = _plan(transcript=_transcript(words2),
                  scenes=_scenes([(0, 4), (4, 8), (8, 12)], 12.0))
    by_id = {s.segment_id: s for s in plan2.story_structure}
    assert by_id[1].classification == "call_to_action" and by_id[1].confidence == 0.7
    assert by_id[0].classification == "hook"


def test_structure_uncertain():
    plan = _plan(transcript=_transcript([]), scenes=_scenes([(0, 12)], 12.0))
    assert plan.story_structure[0].classification == "unknown"
    assert plan.story_structure[0].confidence <= 0.2


# ---------- pacing ----------

def test_pacing_slow_static_scene():
    plan = _plan(scenes=_scenes([(0, 1), (1, 3), (3, 15)], 15.0),
                 visual=_visual([_vsum(0, 0.2), _vsum(1, 0.2), _vsum(2, 0.0)]),
                 transcript=_transcript([("a", 4.0, 4.5, 0.9)], duration=15.0),
                 edl=_edl([("KEEP", 0, 15, "default")], 15.0))
    verdicts = {r["scope"]: r["verdict"] for r in plan.pacing_analysis}
    assert verdicts["scene_2"] == "add_visual_change"
    plan2 = _plan(scenes=_scenes([(0, 1), (1, 3), (3, 15)], 15.0),
                  visual=_visual([_vsum(0, 0.2), _vsum(1, 0.2), _vsum(2, 0.0)]),
                  transcript=_transcript([], duration=15.0),
                  edl=_edl([("KEEP", 0, 15, "default")], 15.0))
    verdicts2 = {r["scope"]: r["verdict"] for r in plan2.pacing_analysis}
    assert verdicts2["scene_2"] == "tighten"  # long, sparse, static, speechless


def test_pacing_fast_and_mixed():
    scenes = _scenes([(i, i + 1) for i in range(12)], 12.0)
    plan = _plan(scenes=scenes, transcript=_transcript([]))
    assert any(r["verdict"] == "maintain" for r in plan.pacing_analysis)


def test_pacing_static_with_speech():
    words = [("talk", i + 0.1, i + 0.9, 0.9) for i in range(10)]
    plan = _plan(scenes=_scenes([(0, 12)], 12.0),
                 visual=_visual([_vsum(0, motion=0.0)]),
                 transcript=_transcript(words))
    rec = next(r for r in plan.pacing_analysis if r["scope"] == "scene_0")
    assert rec["verdict"] == "add_visual_change"  # speech matters: change visuals, not words


# ---------- cuts ----------

def _cutplan(**kw):
    base = dict(audio=_audio(), transcript=_transcript([("hi", 0.5, 1.0, 0.9)]),
                scenes=_scenes([(0, 12)], 12.0),
                edl=_edl([("KEEP", 0, 5, "default"), ("REMOVE", 5, 8, "long_silence"),
                          ("KEEP", 8, 12, "default")], 12.0),
                intel=_intel(safety=[("edl_0002", "SAFE")]), visual=None,
                refined=None, duration=12.0, style=resolve_style("general"))
    base.update(kw)
    return build_editor_plan(**base)


def test_cut_safe_approve():
    plan = _cutplan()
    assert [(c.decision_id, c.verdict) for c in plan.cut_plan] == [("edl_0002", "approve")]


def test_cut_unsafe_reject_and_conflict():
    plan = _cutplan(intel=_intel(safety=[("edl_0002", "UNSAFE")]))
    assert plan.cut_plan[0].verdict == "reject"
    assert plan.cut_plan[0].priority == "high"
    assert any(c.winner == "keep" for c in plan.conflicts)


def test_cut_sentence_split_reject():
    words = [("first", 4.0, 4.8, 0.9), ("second", 8.2, 9.0, 0.9)]
    plan = _cutplan(transcript=_transcript(words))
    assert plan.cut_plan[0].verdict == "reject"


def test_cut_filler_and_silence_evidence():
    words = [("um", 5.2, 5.5, 0.9), ("ok", 9.0, 9.5, 0.9)]
    edl = _edl([("KEEP", 0, 5, "default"), ("REMOVE", 5, 5.7, "filler_word"),
                ("KEEP", 5.7, 12, "default")], 12.0)
    edl["decisions"][1]["word_refs"] = [{"word": "um", "start": 5.2, "end": 5.5,
                                         "segment_id": 0}]
    plan = _cutplan(edl=edl, transcript=_transcript(words, [("um", 5.2, 5.5)]),
                    intel=_intel(safety=[("edl_0002", "SAFE")]))
    assert plan.cut_plan[0].verdict == "approve"
    assert any(f["evidence_type"] == "base_evidence" for f in plan.cut_plan[0].factors)


def test_cut_jump_mitigation_low_tolerance():
    edl = _edl([("KEEP", 0, 5, "default"), ("REMOVE", 5, 6, "long_silence"),
                ("KEEP", 6, 12, "default")], 12.0)
    plan = _cutplan(edl=edl, visual=_visual([_vsum(0, motion=0.0)]),
                    style=resolve_style("talking_head"),
                    intel=_intel(safety=[("edl_0002", "SAFE")]))
    assert plan.cut_plan[0].verdict == "approve_with_mitigation"
    assert "broll_cover" in plan.cut_plan[0].alternatives


# ---------- b-roll ----------

def test_broll_static_talking_head():
    words = [("talk", i + 0.1, i + 0.8, 0.9) for i in range(0, 12, 2)]
    plan = _plan(scenes=_scenes([(0, 12)], 12.0),
                 visual=_visual([_vsum(0, motion=0.0)]),
                 transcript=_transcript(words),
                 style=resolve_style("talking_head"))
    assert len(plan.broll_plan) == 1
    b = plan.broll_plan[0]
    assert b.reason == "visual_stagnation" and b.recommended is True
    assert b.desired_visual_type == "supporting_footage"


def test_broll_concrete_topic():
    words = [("product", 1.0, 1.5, 0.9), ("product", 5.0, 5.5, 0.9),
             ("great", 9.0, 9.5, 0.9)]
    plan = _plan(scenes=_scenes([(0, 12)], 12.0),
                 visual=_visual([_vsum(0, motion=0.0)]),
                 transcript=_transcript(words),
                 style=resolve_style("educational"))
    assert "product" in plan.broll_plan[0].semantic_topic


def test_broll_no_evidence_no_plan():
    plan = _plan(scenes=_scenes([(0, 3)], 3.0), visual=None,
                 transcript=_transcript([("hi", 0.5, 1.0, 0.9)]))
    assert plan.broll_plan == []  # no visual data + short scene: honest empty


def test_broll_jump_concealment():
    jumps = [{"gap_start": 5.0, "gap_end": 6.0, "gap_duration": 1.0,
              "same_scene": True, "potential_jump_cut": True, "evidence": []}]
    plan = _plan(scenes=_scenes([(0, 12)], 12.0),
                 visual=_visual([_vsum(0, motion=0.2)]),
                 transcript=_transcript([("a", 0.5, 1.0, 0.9)]),
                 intel=_intel(jumps=jumps))
    assert any(b.reason == "jump_cut_concealment" and b.recommended
               for b in plan.broll_plan)


# ---------- repetition ----------

def test_repetition_policies():
    reps = [{"text": "hello world", "spans": [{"start": 0, "end": 2}, {"start": 5, "end": 7}],
             "similarity": 1.0, "confidence": 0.6, "evidence": []}]
    base = dict(audio=_audio(), transcript=_transcript([]),
                scenes=_scenes([(0, 12)], 12.0),
                edl=_edl([("KEEP", 0, 12, "default")], 12.0),
                visual=None, refined=None, duration=12.0)
    g = build_editor_plan(intel=_intel(reps=reps), style=resolve_style("general"), **base)
    assert g.repetition_candidates[0].recommended_action == "investigate"
    t = build_editor_plan(intel=_intel(reps=reps), style=resolve_style("tutorial"), **base)
    assert t.repetition_candidates[0].recommended_action == "candidate_for_trim"
    p = build_editor_plan(intel=_intel(reps=reps), style=resolve_style("podcast"), **base)
    assert p.repetition_candidates[0].recommended_action == "keep"


def test_repetition_unrelated_none():
    plan = _plan()
    assert plan.repetition_candidates == []


# ---------- conflicts ----------

def test_conflict_speech_beats_static():
    c = resolve_conflict(
        [{"signal": "low_density", "principle": "pacing"}],
        [{"signal": "speech_continuity", "principle": "story_continuity"}])
    assert (c.winner, c.principle) == ("keep", "story_continuity")


def test_conflict_pause_vs_safety():
    c = resolve_conflict(
        [{"signal": "long_pause", "principle": "pacing"}],
        [{"signal": "safety_UNSAFE", "principle": "edit_safety"}])
    assert (c.winner, c.principle) == ("keep", "edit_safety")


def test_conflict_visual_vs_unsafe_cut():
    c = resolve_conflict(
        [{"signal": "static_visuals", "principle": "visual_quality"}],
        [{"signal": "word_overlap", "principle": "edit_safety"}])
    assert c.winner == "keep" and "never sacrificed" in c.explanation


def test_conflict_order_configurable():
    c = resolve_conflict(
        [{"signal": "a", "principle": "pacing"}],
        [{"signal": "b", "principle": "visual_quality"}],
        order=("visual_quality", "pacing"))
    assert (c.winner, c.principle) == ("keep", "visual_quality")


# ---------- priority vs confidence ----------

def test_priority_confidence_separate():
    plan = _cutplan(intel=_intel(safety=[("edl_0002", "UNSAFE")]))
    c = plan.cut_plan[0]
    assert c.priority == "high" and c.confidence == 0.85  # distinct dimensions
    assert c.priority != c.confidence


# ---------- determinism ----------

def test_deterministic_plan():
    kw = dict(audio=_audio([(5.0, 8.0)]),
              transcript=_transcript([("hi", 0.5, 1.0, 0.9), ("um", 9.0, 9.3, 0.8)],
                                     [("um", 9.0, 9.3)]),
              scenes=_scenes([(0, 6), (6, 12)], 12.0),
              edl=_edl([("KEEP", 0, 5, "default"), ("REMOVE", 5, 8, "long_silence"),
                        ("KEEP", 8, 12, "default")], 12.0),
              intel=_intel(safety=[("edl_0002", "SAFE")]), visual=None,
              refined=None, duration=12.0, style=resolve_style("talking_head"))
    from dataclasses import asdict
    a, b = asdict(build_editor_plan(**kw)), asdict(build_editor_plan(**kw))
    a.pop("processing_s"), b.pop("processing_s")  # wall-clock by design
    assert a == b


# ---------- cache ----------

def _write_brain_project(tag, audio, transcript, scenes, edl):
    p = create_project(tag)
    write_artifact(p.id, "analysis", "audio_analysis.json", audio)
    write_artifact(p.id, "analysis", "transcript.json", transcript)
    write_artifact(p.id, "analysis", "scenes.json", scenes)
    write_artifact(p.id, "edit", "edit_decision.json", edl)
    return p


def test_cache_hit_style_config_invalidation():
    import time
    from engine.editing.brain import run_editor_brain_for_project as run
    tag = f"brain_{time.time_ns()}.mp4"
    audio = dict(_audio([(5.0, 8.0)]), path=tag)
    edl = _edl([("KEEP", 0, 5, "default"), ("REMOVE", 5, 8, "long_silence"),
                ("KEEP", 8, 12, "default")], 12.0, source=tag)
    p = _write_brain_project(tag, audio, _transcript([("hi", 0.5, 1.0, 0.9)]),
                             _scenes([(0, 12)], 12.0), edl)
    first = run(p.id)
    assert first["cached"] is False
    assert (ROOT / "projects" / p.id / "editing" / "editor_plan.json").is_file()
    second = run(p.id)
    assert second["cached"] is True
    assert {k: v for k, v in second["plan"].items() if k != "cached"} == \
           {k: v for k, v in first["plan"].items() if k != "cached"}
    assert run(p.id, style_name="podcast")["cached"] is False  # style invalidates
    assert run(p.id, aggressive=True)["cached"] is False  # config invalidates


# ---------- CLI ----------

def test_cli_valid_invalid(capsys):
    import time
    from engine.cli import main
    tag = f"brain_cli_{time.time_ns()}.mp4"
    p = _write_brain_project(tag, dict(_audio(), path=tag),
                             _transcript([("hi", 0.5, 1.0, 0.9)]),
                             _scenes([(0, 12)], 12.0),
                             _edl([("KEEP", 0, 12, "default")], 12.0, source=tag))
    assert main(["editor-plan", p.id, "--style", "talking_head"]) == 0
    out = capsys.readouterr().out
    assert "style   : talking_head" in out and "artifact: editing/editor_plan.json" in out
    assert main(["editor-plan", p.id, "--style", "nope"]) == 2
    assert main(["editor-plan", "project_nope_123"]) == 2
    q = create_project(f"brain_empty_{time.time_ns()}.mp4")
    assert main(["editor-plan", q.id]) == 2  # missing analysis


# ---------- real full-chain verification ----------

@pytest.fixture(scope="module")
def real_chain():
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        pytest.skip("ffmpeg/ffprobe not on PATH")
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "make_test_media.py"), "--all"],
                       capture_output=True, text=True, timeout=600)
    assert r.returncode == 0
    from engine.analysis.scenes import detect_scenes_project
    from engine.analysis.speech import transcribe_to_project
    from engine.analysis.visual import run_visual_for_project
    from engine.core.orchestrator import run_inspect
    from engine.editing.decisions import build_edl_for_project
    from engine.editing.intelligence import run_intelligence_for_project
    out = {}
    pid = run_inspect(str(FIX / "mixed_6s.mp4"))["project"]
    transcribe_to_project(str(FIX / "mixed_6s.mp4"), project_id=pid, model="tiny")
    detect_scenes_project(str(FIX / "mixed_6s.mp4"), project_id=pid)
    build_edl_for_project(pid)
    run_intelligence_for_project(pid)
    run_visual_for_project(pid)
    out["mixed"] = pid
    sapi = run_inspect(str(FIX / "speech_sapi.wav"))["project"]
    transcribe_to_project(str(FIX / "speech_sapi.wav"), project_id=sapi, model="tiny")
    build_edl_for_project(sapi)
    run_intelligence_for_project(sapi)
    out["sapi"] = sapi
    return out


def test_real_mixed_plan_valid_conservative(real_chain):
    from engine.editing.brain import run_editor_brain_for_project as run
    res = run(real_chain["mixed"])
    plan = res["plan"]
    assert plan["schema_version"] == "editor-plan-1.0"
    assert plan["duration"] == pytest.approx(6.0, abs=0.1)
    assert all(v in ("approve", "approve_with_mitigation", "downgrade_keep",
                     "reject", "candidate_for_trim", "investigate")
               for v in [c["verdict"] for c in plan["cut_plan"]])
    # Speechless single-scene fixture: unknown segment, low confidence,
    # limitation stated, no invented semantics.
    assert plan["hook"]["recommended_opening_strategy"] in ("keep_as_is", "investigate")
    assert len(plan["story_structure"]) == 1
    assert plan["story_structure"][0]["classification"] == "unknown"
    assert plan["story_structure"][0]["confidence"] <= 0.2
    assert all("priority" in c and "confidence" in c for c in plan["cut_plan"])
    again = run(real_chain["mixed"])
    assert again["cached"] is True


def test_real_sapi_speech_signals(real_chain):
    from engine.editing.brain import run_editor_brain_for_project as run
    res = run(real_chain["sapi"], style_name="podcast")
    plan = res["plan"]
    assert plan["editing_style"]["name"] == "podcast"
    assert plan["editing_style"]["broll_intensity"] == "off"
    assert plan["broll_plan"] == []  # style off + audio-only: honest empty
    assert any(s["classification"] in ("hook", "conclusion") for s in plan["story_structure"])
    assert plan["hook"]["hook_strength_signals"]  # real measured signals
    assert sum(w["words_per_sec"] for w in plan["density_windows"]) > 0


def test_brain_consumes_phase_artifacts_from_real_locations():
    """Regression: the brain must read edit_/visual_ artifacts where their
    phases wrote them (a loader once looked only under analysis/, silently
    running without safety/visual inputs)."""
    import time
    from engine.core.project_store import create_project, write_artifact
    from engine.editing.brain import run_editor_brain_for_project as run
    tag = f"brain_locs_{time.time_ns()}.mp4"
    p = create_project(tag)
    dur, src = 12.0, str(FIX / "tone_5s.mp4")
    proj_in = {"input_path": src}
    from engine.core.project_store import load_project, save_project
    proj = load_project(p.id)
    proj.input_path = src
    save_project(proj)
    write_artifact(p.id, "analysis", "audio_analysis.json",
                   {"path": src, "audio_present": True, "audio_duration": dur,
                    "silence": [{"start": 5.0, "end": 8.0, "duration": 3.0}]})
    write_artifact(p.id, "analysis", "transcript.json",
                   {"language": "en", "duration": dur,
                    "segments": [{"id": 0, "text": "hi",
                                  "start": 0.0, "end": dur,
                                  "words": [{"word": "hi", "start": 0.5,
                                             "end": 1.0, "probability": 0.9}]}],
                    "fillers": [], "skipped_reason": ""})
    write_artifact(p.id, "analysis", "scenes.json",
                   {"duration": dur, "scenes": [{"scene_id": 0, "start": 0.0,
                                                 "end": dur, "duration": dur,
                                                 "start_frame": 0, "end_frame": 0}]})
    write_artifact(p.id, "edit", "edit_decision.json",
                   {"source": src, "duration": dur,
                    "decisions": [
                        {"decision_id": "edl_0001", "start": 0.0, "end": 5.0,
                         "action": "KEEP", "reason": "default", "confidence": 1.0,
                         "scene_id": 0, "word_refs": [], "metadata": {}},
                        {"decision_id": "edl_0002", "start": 5.0, "end": 8.0,
                         "action": "REMOVE", "reason": "long_silence", "confidence": 0.9,
                         "scene_id": 0, "word_refs": [], "metadata": {}},
                        {"decision_id": "edl_0003", "start": 8.0, "end": dur,
                         "action": "KEEP", "reason": "default", "confidence": 1.0,
                         "scene_id": 0, "word_refs": [], "metadata": {}}],
                    "policy": {}, "analysis_refs": {}, "warnings": []})
    # Phase 10 + Phase 11 artifacts in THEIR real locations (not analysis/).
    write_artifact(p.id, "edit", "edit_intelligence.json",
                   {"cut_safety": [{"decision_id": "edl_0002", "status": "UNSAFE",
                                    "evidence": []}],
                    "repetitions": [], "jump_cuts": []})
    write_artifact(p.id, "visual", "visual_analysis.json",
                   {"scene_summaries": [{"scene_id": 0, "start": 0.0, "end": dur,
                                         "duration": dur, "motion_mean": 0.0,
                                         "brightness_mean": 10.0}],
                    "continuity": [], "static_spans": []})
    plan = run(p.id)["plan"]
    verdicts = {c["decision_id"]: c["verdict"] for c in plan["cut_plan"]}
    assert verdicts["edl_0002"] == "reject"  # intel UNSAFE consumed, not ignored
    assert any(b["reason"] == "visual_stagnation" for b in plan["broll_plan"]) \
        # visual static scene consumed, not ignored
