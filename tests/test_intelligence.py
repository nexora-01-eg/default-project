"""Phase 10 tests — editing intelligence (measurements + refinement, NO rendering).

Hand-built analysis dicts for determinism; real-fixture chain at the end.
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
from engine.editing.intelligence import (
    IntelError,
    analyze_intelligence,
    assess_removal,
    jump_cut_candidates,
    preferred_points,
    refine_edl,
    repetition_candidates,
    resolve_intel_policy,
    run_intelligence_for_project,
    scene_metrics,
)
from engine.rendering.execution import validate_edl

POLICY = resolve_intel_policy(None)
EV_KEYS = {"evidence_type", "source", "start", "end", "metric",
           "value", "threshold", "explanation"}


def _audio(silences, duration=12.0):
    return {"path": "t", "audio_present": True, "audio_duration": duration,
            "silence": [{"start": s, "end": e, "duration": e - s} for s, e in silences]}


def _transcript(words, fillers=(), language="en", duration=12.0):
    return {"language": language, "duration": duration,
            "segments": [{"id": 0, "text": " ".join(w[0] for w in words),
                          "start": 0.0, "end": duration,
                          "words": [{"word": w, "start": s, "end": e, "probability": p}
                                    for w, s, e, p in words]}],
            "fillers": [{"word": w, "start": s, "end": e, "segment_id": 0}
                        for w, s, e in fillers]}


def _scenes(spans, duration=None):
    dur = duration if duration is not None else (spans[-1][1] if spans else 0.0)
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


def _ctx(words, scenes, neighbors=(), language="en"):
    from engine.analysis.fillers import filler_set
    tr = _transcript(words, language=language)
    flat, _ = __import__("engine.editing.intelligence",
                         fromlist=["_norm_words"])._norm_words(tr)
    return {"words": flat, "referenced_fillers": set(),
            "filler_set": set(filler_set(language)),
            "scenes": _scenes(scenes)["scenes"] if isinstance(scenes, list) else [],
            "neighbors": list(neighbors), "min_keep": 0.5, "min_remove": 0.2,
            "punctuated": any(w["terminal"] for w in flat)}


# ---------- 1-3: scene metrics / continuity ----------

def test_scene_speech_density():
    words = [("a", 0.5, 1.5, 0.9), ("b", 2.0, 3.0, 0.9), ("c", 5.0, 8.0, 0.9)]
    tr = _transcript(words, duration=10.0)
    from engine.editing.intelligence import _norm_words
    flat, _ = _norm_words(tr)
    metrics, median = scene_metrics(_scenes([(0, 4), (4, 10)], 10.0), flat)
    assert [(m.scene_id, m.speech_density, m.word_count) for m in metrics] == \
           [(0, 0.5, 2), (1, 0.5, 1)]
    assert median == 5.0


def test_scene_duration_outliers_flagged_not_deleted():
    metrics, median = scene_metrics(_scenes([(0, 1), (1, 5), (5, 15)], 15.0), [])
    assert median == 4.0
    assert [m.duration_outlier for m in metrics] == ["short", "", "long"]
    # Flags are metadata: scene list itself is unchanged.
    assert len(metrics) == 3


def test_speech_crossing_boundary():
    from engine.editing.intelligence import _norm_words, continuity
    tr = _transcript([("hello", 3.5, 3.8, 0.9), ("world", 4.1, 4.4, 0.9)])
    flat, _ = _norm_words(tr)
    cont = continuity(_scenes([(0, 4), (4, 10)], 10.0), flat)
    assert cont[0]["continues_likely"] is True
    assert [w["word"] for w in cont[0]["words_before"]] == ["hello"]
    tr2 = _transcript([("end.", 3.5, 3.8, 0.9), ("next", 4.1, 4.4, 0.9)])
    flat2, _ = _norm_words(tr2)
    cont2 = continuity(_scenes([(0, 4), (4, 10)], 10.0), flat2)
    assert cont2[0]["continues_likely"] is False
    assert cont2[0]["sentence_terminated"] is True


# ---------- 4-8: cut safety ----------

def _safe_ctx():
    return _ctx([("hi", 0.5, 1.0, 0.9), ("yo", 10.5, 11.0, 0.9)],
                [(0.0, 12.0)],
                [{"action": "KEEP", "start": 0.0, "end": 5.15},
                 {"action": "KEEP", "start": 7.85, "end": 12.0}])


def test_cut_safety_safe():
    s = assess_removal(5.15, 7.85, "edl_0002", _safe_ctx())
    assert s.status == "SAFE"


def test_silence_safety_via_report():
    audio = _audio([(5.0, 8.0)])
    tr = _transcript([("hi", 0.5, 1.0, 0.9)])
    edl = _edl([("KEEP", 0.0, 5.15, "default"), ("REMOVE", 5.15, 7.85, "long_silence"),
                ("KEEP", 7.85, 12.0, "default")], 12.0)
    rep = analyze_intelligence(audio, tr, _scenes([(0, 12)], 12.0), edl, 12.0, POLICY)
    assert [s.status for s in rep.cut_safety] == ["SAFE"]


def test_filler_safety():
    ctx = _ctx([("um", 10.2, 10.48, 0.9), ("hello", 11.0, 11.5, 0.9)], [(0.0, 12.0)])
    ctx["referenced_fillers"] = {(0, "um", 10.2)}
    s = assess_removal(10.12, 10.56, "edl_0002", ctx)
    assert s.status == "SAFE"  # only its own referenced filler touched


def test_min_keep_and_min_remove():
    # Word sits OUTSIDE the removal: only the short neighboring keep flags.
    ctx = _ctx([("hi", 3.0, 3.5, 0.9)], [(0.0, 12.0)],
               [{"action": "KEEP", "start": 0.0, "end": 0.2},
                {"action": "KEEP", "start": 2.0, "end": 12.0}])
    s = assess_removal(0.2, 2.0, "edl_0002", ctx)
    assert s.status == "CAUTION"
    assert any(e.metric == "keep_duration_s" for e in s.evidence)
    s2 = assess_removal(5.0, 5.1, "edl_0003", _safe_ctx())
    assert s2.status == "UNSAFE"
    assert any(e.metric == "removal_duration_s" for e in s2.evidence)


def test_unsafe_speech_overlap_and_tight_padding():
    ctx = _ctx([("hi", 0.5, 1.0, 0.9), ("word", 5.0, 6.0, 0.9)], [(0.0, 12.0)])
    s = assess_removal(5.2, 5.8, "edl_0002", ctx)
    assert s.status == "UNSAFE"
    assert any(e.metric == "overlap_s" for e in s.evidence)
    ctx2 = _ctx([("hi", 0.5, 1.0, 0.9)], [(0.0, 12.0)])
    s3 = assess_removal(1.02, 2.0, "edl_0002", ctx2)  # 20 ms from word edge
    assert s3.status == "CAUTION"


# ---------- 9-10: jump cuts + pacing ----------

def test_jump_cut_candidates():
    same = _edl([("KEEP", 0.0, 5.0, "default"), ("REMOVE", 5.0, 6.0, "long_silence"),
                 ("KEEP", 6.0, 12.0, "default")], 12.0)["decisions"]
    for d in same:
        d["scene_id"] = 3
    from engine.editing.intelligence import jump_cut_candidates as jc
    out = jc(same)
    assert len(out) == 1 and out[0].potential_jump_cut is True
    assert out[0].same_scene is True and out[0].gap_duration == 1.0
    diff = [dict(d) for d in same]
    diff[2]["scene_id"] = 4
    out2 = jc(diff)
    assert out2[0].potential_jump_cut is False  # cross-scene = natural cut


def test_pacing_metrics_exact():
    from engine.editing.intelligence import pacing_metrics, _norm_words
    tr = _transcript([("a", 0.5, 1.0, 0.9), ("b", 5.0, 6.0, 0.9)], duration=12.0)
    flat, _ = _norm_words(tr)
    p = pacing_metrics(_scenes([(0, 4), (4, 12)], 12.0), flat,
                       [{"start": 2.0, "end": 4.0, "duration": 2.0}], 12.0)
    assert (p.scene_count, p.avg_shot_duration, p.median_shot_duration) == (2, 6.0, 6.0)
    assert p.scene_changes_per_min == pytest.approx(5.0)
    assert p.words_per_min == pytest.approx(80.0)
    assert (p.pauses_per_min, p.avg_pause_duration) == (5.0, 2.0)


# ---------- 11-12: repetition + sentence points ----------

def test_repetition_exact_match():
    from engine.editing.intelligence import _norm_words
    tr = _transcript([("hello", 0, 1, 1), ("world", 1, 2, 1), ("foo", 3, 4, 1),
                      ("hello", 5, 6, 1), ("world", 6, 7, 1), ("bar", 8, 9, 1)])
    flat, _ = _norm_words(tr)
    reps = repetition_candidates(flat, min_words=2)
    assert len(reps) == 1
    assert reps[0].text == "hello world" and reps[0].similarity == 1.0
    assert [ (s["start"], s["end"]) for s in reps[0].spans ] == [(0.0, 2.0), (5.0, 7.0)]
    tr2 = _transcript([("alpha", 0, 1, 1), ("beta", 1, 2, 1), ("gamma", 3, 4, 1)])
    flat2, _ = _norm_words(tr2)
    assert repetition_candidates(flat2, min_words=2) == []


def test_sentence_points_and_limitation():
    from engine.editing.intelligence import _norm_words, sentence_signals
    tr = _transcript([("hi", 0.0, 0.5, 0.9), ("there", 1.0, 1.5, 0.9)])
    flat, _ = _norm_words(tr)
    pts = preferred_points(flat, [], _scenes([(0, 12)], 12.0), gap_min=0.15)
    assert pts and pts[0]["kind"] == "word_gap"
    assert (pts[0]["start"], pts[0]["end"]) == (0.5, 1.0)
    sig = sentence_signals(flat)
    assert sig["coverage"] == 0.0 and "limitation" in sig  # recorded, not invented


# ---------- 13-14: evidence + determinism ----------

def test_evidence_fields_complete():
    audio = _audio([(5.0, 8.0)])
    tr = _transcript([("hi", 0.5, 1.0, 0.9)])
    edl = _edl([("KEEP", 0.0, 5.15, "default"), ("REMOVE", 5.15, 7.85, "long_silence"),
                ("KEEP", 7.85, 12.0, "default")], 12.0)
    rep = analyze_intelligence(audio, tr, _scenes([(0, 12)], 12.0), edl, 12.0, POLICY)
    all_ev = [e for s in rep.cut_safety for e in s.evidence]
    assert all_ev, "non-trivial decisions must carry evidence"
    from dataclasses import asdict
    for e in all_ev:
        assert EV_KEYS <= set(asdict(e))


def test_deterministic_output():
    kwargs = dict(audio=_audio([(5.0, 8.0)]),
                  transcript=_transcript([("hi", 0.5, 1.0, 0.9)]),
                  scenes=_scenes([(0, 12)], 12.0),
                  edl=_edl([("KEEP", 0.0, 5.15, "default"),
                            ("REMOVE", 5.15, 7.85, "long_silence"),
                            ("KEEP", 7.85, 12.0, "default")], 12.0),
                  duration=12.0, policy=POLICY)
    from dataclasses import asdict
    a, b = asdict(analyze_intelligence(**kwargs)), asdict(analyze_intelligence(**kwargs))
    a.pop("processing_s"), b.pop("processing_s")  # wall-clock by design
    assert a == b


# ---------- refinement ----------

def test_unsafe_reverted_with_provenance():
    # Hand-fed EDL whose removal overlaps real speech: must flip to KEEP.
    edl = _edl([("KEEP", 0.0, 5.0, "default"), ("REMOVE", 5.0, 6.0, "long_silence"),
                ("KEEP", 6.0, 12.0, "default")], 12.0)
    tr = _transcript([("word", 5.2, 5.8, 0.9)])
    rep = analyze_intelligence(_audio([]), tr, _scenes([(0, 12)], 12.0), edl, 12.0, POLICY)
    assert rep.cut_safety[0].status == "UNSAFE"
    refined, changes = refine_edl(edl, rep, POLICY)
    assert validate_edl(refined, 12.0) == []
    flipped = [d for d in refined["decisions"] if d["decision_id"] == "ref_0002"][0]
    assert flipped["action"] == "KEEP" and flipped["reason"] == "safety_revert"
    assert flipped["metadata"]["provenance"]["original_action"] == "REMOVE"
    assert changes[0]["rule"] == "safety_revert"
    # Source tiling preserved exactly.
    assert [(d["start"], d["end"]) for d in refined["decisions"]] == \
           [(d["start"], d["end"]) for d in edl["decisions"]]


def test_strict_mode_reverts_caution():
    edl = _edl([("KEEP", 0.0, 0.2, "default"), ("REMOVE", 0.2, 2.0, "long_silence"),
                ("KEEP", 2.0, 12.0, "default")], 12.0)
    tr = _transcript([("hi", 5.0, 5.5, 0.9)])  # outside the removal: CAUTION only
    rep = analyze_intelligence(_audio([]), tr, _scenes([(0, 12)], 12.0), edl, 12.0, POLICY)
    assert rep.cut_safety[0].status == "CAUTION"  # short neighboring keep
    ref_c, _ = refine_edl(edl, rep, POLICY)
    assert [d["action"] for d in ref_c["decisions"]] == ["KEEP", "REMOVE", "KEEP"]
    strict = resolve_intel_policy({"intel_safety_mode": "strict"})
    ref_s, changes = refine_edl(edl, rep, strict)
    assert all(d["action"] == "KEEP" for d in ref_s["decisions"])
    assert changes[0]["rule"] == "safety_revert"


def test_repetition_removal_opt_in():
    words = [("hello", 0.0, 1.0, 0.9), ("world", 1.0, 2.0, 0.9),
             ("foo", 2.0, 3.0, 0.9), ("bar", 3.0, 4.0, 0.9),
             ("um", 4.0, 4.3, 0.9),
             ("hello", 5.0, 6.0, 0.9), ("world", 6.0, 7.0, 0.9),
             ("foo", 7.0, 8.0, 0.9), ("bar", 8.0, 9.0, 0.9),
             ("done", 10.0, 11.0, 0.9)]
    tr = _transcript(words, [("um", 4.0, 4.3)], duration=12.0)
    edl = _edl([("KEEP", 0.0, 12.0, "default")], 12.0)
    rep = analyze_intelligence(_audio([]), tr, _scenes([(0, 12)], 12.0), edl, 12.0, POLICY)
    assert len(rep.repetitions) == 1
    assert rep.repetitions[0].text == "hello world foo bar"
    assert [(s["start"], s["end"]) for s in rep.repetitions[0].spans] == \
           [(0.0, 4.0), (5.0, 9.0)]
    ref_off, ch_off = refine_edl(edl, rep, POLICY)
    assert ch_off == [] and all(d["action"] == "KEEP" for d in ref_off["decisions"])
    on = resolve_intel_policy({"intel_repetition_removal": True})
    ref_on, ch_on = refine_edl(edl, rep, on)
    assert validate_edl(ref_on, 12.0) == []
    rem = [d for d in ref_on["decisions"] if d["action"] == "REMOVE"]
    assert len(rem) == 1 and rem[0]["reason"] == "repetition"
    assert (rem[0]["start"], rem[0]["end"]) == (5.0, 9.0)
    assert any(d["action"] == "KEEP" and d["start"] == 0.0 for d in ref_on["decisions"])


# ---------- 15-20: project / cache / CLI ----------

def _write_intel_project(path_tag, audio, transcript, scenes, edl):
    p = create_project(path_tag)
    write_artifact(p.id, "analysis", "audio_analysis.json", audio)
    write_artifact(p.id, "analysis", "transcript.json", transcript)
    write_artifact(p.id, "analysis", "scenes.json", scenes)
    write_artifact(p.id, "edit", "edit_decision.json", edl)
    return p


def test_cache_hit_and_invalidation():
    import time
    tag = f"intel_{time.time_ns()}.mp4"
    audio = dict(_audio([(5.0, 8.0)]), path=tag)
    p = _write_intel_project(tag, audio, _transcript([("hi", 0.5, 1.0, 0.9)]),
                             _scenes([(0, 12)], 12.0),
                             _edl([("KEEP", 0.0, 5.15, "default"),
                                   ("REMOVE", 5.15, 7.85, "long_silence"),
                                   ("KEEP", 7.85, 12.0, "default")], 12.0, source=tag))
    from engine.editing.intelligence import run_intelligence_for_project as run
    first = run(p.id)
    assert first["cached"] is False
    assert first["intelligence"]["refined_changes"] == []
    second = run(p.id)
    assert second["cached"] is True
    assert {k: v for k, v in second["refined_edl"].items() if k != "cached"} == \
           {k: v for k, v in first["refined_edl"].items() if k != "cached"}
    third = run(p.id, {"intel_safety_mode": "strict"})
    assert third["cached"] is False  # policy change invalidates
    for name in ("edit_intelligence.json", "refined_edit_decision.json"):
        assert (ROOT / "projects" / p.id / "edit" / name).is_file()


def test_missing_inputs_fail_clearly():
    from engine.editing.intelligence import run_intelligence_for_project as run
    p = create_project(f"intel_missing_{time.time_ns()}.mp4")
    with pytest.raises(IntelError, match="base EDL"):
        run(p.id)
    write_artifact(p.id, "edit", "edit_decision.json",
                   _edl([("KEEP", 0, 12, "default")], 12.0))
    with pytest.raises(IntelError, match="audio_analysis"):
        run(p.id)


def test_cli_success_and_error(capsys):
    import time
    from engine.cli import main
    tag = f"intel_cli_{time.time_ns()}.mp4"
    p = _write_intel_project(tag, dict(_audio([(5.0, 8.0)]), path=tag),
                             _transcript([("hi", 0.5, 1.0, 0.9)]),
                             _scenes([(0, 12)], 12.0),
                             _edl([("KEEP", 0.0, 5.15, "default"),
                                   ("REMOVE", 5.15, 7.85, "long_silence"),
                                   ("KEEP", 7.85, 12.0, "default")], 12.0, source=tag))
    assert main(["edit-analyze", p.id]) == 0
    out = capsys.readouterr().out
    assert "safety  :" in out and "refined :" in out and "nothing rendered" in out
    assert main(["edit-analyze", "project_nope_123"]) == 2
    q = create_project(f"intel_empty_{time.time_ns()}.mp4")
    assert main(["edit-analyze", q.id]) == 2


# ---------- 17: real-fixture verification (no rendering) ----------

@pytest.fixture(scope="module")
def real_chain():
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        pytest.skip("ffmpeg/ffprobe not on PATH")
    from engine.analysis.scenes import detect_scenes_project
    from engine.analysis.speech import transcribe_to_project
    from engine.core.orchestrator import run_inspect
    from engine.editing.decisions import build_edl_for_project
    out = {}
    pid = run_inspect(str(FIX / "mixed_6s.mp4"))["project"]
    transcribe_to_project(str(FIX / "mixed_6s.mp4"), project_id=pid, model="tiny")
    detect_scenes_project(str(FIX / "mixed_6s.mp4"), project_id=pid)
    edl = build_edl_for_project(pid)["edl"]
    out["mixed"] = pid
    out["mixed_removed"] = edl["removed_duration"]
    sapi = run_inspect(str(FIX / "speech_sapi.wav"))["project"]
    transcribe_to_project(str(FIX / "speech_sapi.wav"), project_id=sapi, model="tiny")
    sapi_edl = build_edl_for_project(sapi)["edl"]  # audio-only synth scenes
    out["sapi"] = sapi
    out["sapi_words"] = sapi_edl and json.loads(
        (ROOT / "projects" / sapi / "analysis" / "transcript.json").read_text()
    )["word_count"]
    return out


def test_real_mixed_chain(real_chain):
    from engine.editing.intelligence import run_intelligence_for_project as run
    res = run(real_chain["mixed"])
    intel, ref = res["intelligence"], res["refined_edl"]
    assert len(intel["scene_metrics"]) >= 1  # real static video: 1 scene
    assert intel["scene_metrics"][0]["speech_density"] == 0.0  # sine is not speech: honest
    assert intel["pacing"]["scene_count"] >= 1
    assert validate_edl(ref, intel["duration"]) == []
    assert ref["removed_duration"] == pytest.approx(real_chain["mixed_removed"])
    assert {d["action"] for d in ref["decisions"]} <= {"KEEP", "REMOVE"}


def test_real_sapi_speech_density(real_chain):
    from engine.editing.intelligence import run_intelligence_for_project as run
    assert real_chain["sapi_words"] >= 10  # real recognized words, not fixtures
    res = run(real_chain["sapi"])
    intel = res["intelligence"]
    assert intel["scene_metrics"][0]["speech_density"] > 0.0  # real speech measured
    assert intel["scene_metrics"][0]["word_count"] >= 10
    assert intel["continuity"] == []  # single (synth) scene: nothing to cross
    assert validate_edl(res["refined_edl"], intel["duration"]) == []
