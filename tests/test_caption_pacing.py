"""Phase 16 caption-pacing tests — deterministic units + project cache/approval + real E2E.

Pure-logic tests use hand-built dicts (no ffmpeg). Project tests hand-write
minimal artifacts. The real-E2E test runs the full local chain on fixtures.

Fixture-scenario mapping (§21): static+speech, multi-scene, pause, dense,
sparse, placement-conflict, safe/unsafe boundary, and missing-visual cases
are covered with hand-built dicts (deterministic); speech_video.mp4 and
static_12s.mp4 cover the real-media paths. No new media files needed.
"""
import copy
import json
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests" / "fixtures"

from engine.core.models import (
    CaptionPacingContext,
    CaptionPacingPlan,
    PacingRecommendation,
    PacingSignal,
)
from engine.core.project_store import (
    create_project,
    project_dir,
    write_artifact,
)
from engine.editing import caption_pacing as cp


@pytest.fixture(scope="module", autouse=True)
def fixtures():
    for name in ("tone_5s.mp4", "speech_video.mp4", "static_12s.mp4"):
        assert (FIX / name).is_file(), f"missing fixture {name}"


@pytest.fixture()
def need_ffmpeg():
    import shutil
    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg not on PATH")
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "make_test_media.py"), "--all"],
                       capture_output=True, text=True, timeout=600)
    assert r.returncode == 0


# ---------- builders ----------

def _tr(*triples):
    words = [{"word": t, "start": s, "end": e, "probability": 0.9}
             for t, s, e in triples]
    seg = {"id": 0, "start": triples[0][1], "end": triples[-1][2],
           "text": " ".join(t for t, _, _ in triples), "words": words}
    return {"language": "en", "segments": [seg]}


def _run(n, s, e, terminal_last=True):
    step = (e - s) / n
    out = []
    for i in range(n):
        w = f"w{i}"
        if i == n - 1 and terminal_last:
            w = "end."
        out.append((w, round(s + i * step, 3), round(s + (i + 1) * step, 3)))
    return out


def _cue(cid, s, e, text, scene_id=0):
    toks = text.split(" ")
    step = (e - s) / max(len(toks), 1)
    refs = [{"word": t, "start": round(s + i * step, 3),
             "end": round(s + (i + 1) * step, 3)} for i, t in enumerate(toks)]
    return {"cue_id": cid, "start": s, "end": e, "text": text,
            "word_refs": refs, "scene_id": scene_id, "language": "en",
            "confidence": 0.9}


def _scenes(*ivs):
    return {"scenes": [{"scene_id": i, "start": s, "end": e}
                       for i, (s, e) in enumerate(ivs)],
            "scene_count": len(ivs)}


def _edl(*decisions, duration=10.0):
    ds = [{"decision_id": did, "action": a, "start": s, "end": e,
           "reason": "t"} for did, a, s, e in decisions]
    return {"decisions": ds, "duration": duration}


def _intel(*spans):
    return {"cut_safety": [{"decision_id": did, "start": s, "end": e,
                            "status": st} for s, e, st, did in spans]}


def _vis(*motions):
    return {"scene_summaries": [{"scene_id": i, "motion_mean": m,
                                 "framing": {"classification": "medium"}}
                                for i, m in enumerate(motions)]}


def _cfg(**over):
    return cp.resolve_pacing_config(over or None)


def _build(cues, scenes, edl, transcript=None, audio=None, intel=None,
           visual=None, visual_plan=None, brain=None, duration=10.0,
           style="general", config=None):
    return cp.build_pacing_plan(
        audio, transcript, scenes, edl, cues, intel, visual, visual_plan,
        brain, duration, style, config or _cfg())


def _acts(plan):
    return [r.action for r in plan.recommendations]


# ---------- 1. models ----------

def test_model_serialization():
    p = CaptionPacingPlan(
        context_summary=[CaptionPacingContext(scene_id=0, scene_start=0.0,
                                              scene_end=5.0,
                                              scene_duration=5.0)],
        signals=[PacingSignal(signal_id="s1",
                              signal_type="HIGH_CAPTION_DENSITY")],
        recommendations=[PacingRecommendation(action="KEEP")])
    d = asdict(p)
    assert d["schema_version"] == "caption-pacing-plan-1.0"
    assert d["recommendations"][0]["action"] == "KEEP"
    json.loads(json.dumps(d))


def test_config_defaults_and_validation():
    cfg = cp.resolve_pacing_config(None)
    assert cfg["pacing_caption_cps_fast"] == 17.0
    assert cfg["pacing_pause_s"] == 0.6
    assert cfg["pacing_long_scene_ratio"] == 2.0
    with pytest.raises(cp.PacingError):
        cp.resolve_pacing_config({"pacing_pause_s": -1.0})
    with pytest.raises(cp.PacingError):
        cp.resolve_pacing_config({"pacing_caption_cps_fast": "fast"})
    with pytest.raises(cp.PacingError):
        cp.resolve_pacing_config({"nope": 1})


def test_unknown_style_rejected():
    with pytest.raises(cp.PacingError):
        _build([], _scenes((0, 10)),
               _edl(("k", "KEEP", 0, 10)), style="nope")


# ---------- 2. density / gaps / rapid ----------

def test_cps_fast_and_extreme():
    cues = [_cue("c1", 0, 1.0, "x" * 20), _cue("c2", 2, 4.0, "y" * 46)]
    plan = _build(cues, _scenes((0, 10)), _edl(("k", "KEEP", 0, 10)))
    fast = [s for s in plan.signals
            if s.signal_type == "HIGH_CAPTION_DENSITY" and "c1" in s.source_refs]
    extreme = [s for s in plan.signals
               if s.signal_type == "HIGH_CAPTION_DENSITY" and "c2" in s.source_refs]
    assert fast and fast[0].severity == "medium"
    assert extreme and extreme[0].severity == "high"
    assert fast[0].metrics["cps"] == pytest.approx(20.0)


def test_words_per_cue_and_long_gap():
    cues = [_cue("c1", 0, 1.0, "one two three four five six seven eight nine ten"),
            _cue("c2", 3.5, 4.5, "tail here")]
    plan = _build(cues, _scenes((0, 10)), _edl(("k", "KEEP", 0, 10)))
    assert any(s.signal_type == "HIGH_CAPTION_DENSITY" and s.severity == "low"
               for s in plan.signals)
    gaps = [s for s in plan.signals if s.signal_type == "LONG_SILENCE"]
    assert gaps and gaps[0].metrics["gap_s"] == pytest.approx(2.5)


def test_rapid_caption_sequence():
    cues = [_cue("c1", 0, 1.0, "aa"), _cue("c2", 1.1, 2.0, "bb"),
            _cue("c3", 2.1, 3.0, "cc")]
    plan = _build(cues, _scenes((0, 10)), _edl(("k", "KEEP", 0, 10)))
    assert any(s.signal_type == "RAPID_CAPTION_SEQUENCE" for s in plan.signals)


# ---------- 3. speech signals ----------

def test_natural_pause_and_sentence_boundary():
    tr = _tr(("hello", 0.0, 0.5), ("world.", 0.6, 1.0), ("next", 1.8, 2.2))
    plan = _build([_cue("c1", 0, 1.0, "hello world."),
                   _cue("c2", 1.8, 2.2, "next")],
                  _scenes((0, 10)), _edl(("k", "KEEP", 0, 10)),
                  transcript=tr)
    assert any(s.signal_type == "NATURAL_PAUSE" for s in plan.signals)
    assert any(s.signal_type == "SENTENCE_BOUNDARY" for s in plan.signals)


def test_long_speech_block():
    tr = _tr(*_run(40, 0.0, 10.0, terminal_last=False))
    plan = _build([_cue("c1", 0, 10.0, "w" * 30)],
                  _scenes((0, 10)), _edl(("k", "KEEP", 0, 10)),
                  transcript=tr)
    assert any(s.signal_type == "LONG_SPEECH_BLOCK" for s in plan.signals)


# ---------- 4. visual signals ----------

def test_static_and_outlier_and_change():
    plan = _build([_cue("c1", 0, 1.0, "hi")],
                  _scenes((0, 4), (4, 8), (8, 20)),
                  _edl(("k", "KEEP", 0, 20)), duration=20.0,
                  visual=_vis(0.9, 0.8, 0.01))
    types = {s.signal_type for s in plan.signals}
    assert "STATIC_VISUAL" in types
    assert "LONG_VISUAL_SECTION" in types
    vis = dict(_vis(0.9, 0.8, 0.01))
    vis["continuity"] = [{"label": "large_change", "boundary": 8.0}]
    plan2 = _build([_cue("c1", 0, 1.0, "hi")],
                   _scenes((0, 4), (4, 8), (8, 20)),
                   _edl(("k", "KEEP", 0, 20)), duration=20.0, visual=vis)
    assert any(s.signal_type == "HIGH_VISUAL_CHANGE" for s in plan2.signals)


def test_missing_visual_degrades_with_warning():
    plan = _build([_cue("c1", 0, 1.0, "hi")],
                  _scenes((0, 10)), _edl(("k", "KEEP", 0, 10)), visual=None)
    assert any("no visual analysis" in w for w in plan.warnings)
    assert not any(s.signal_type in ("STATIC_VISUAL", "LONG_VISUAL_SECTION")
                   for s in plan.signals)


# ---------- 5-6. correlation cases A/B/C ----------

def test_case_a_dense_static_long():
    tr = _tr(*(_run(6, 0.0, 4.0) + _run(6, 4.0, 8.0)
               + _run(20, 8.0, 20.0)))
    cues = [_cue("c1", 0, 4.0, "intro words here"),
            _cue("c2", 8.0, 20.0, "dense " * 12)]
    plan = _build(cues, _scenes((0, 4), (4, 8), (8, 20)),
                  _edl(("k", "KEEP", 0, 20)), transcript=tr, duration=20.0,
                  visual=_vis(0.9, 0.8, 0.01))
    recs = [r for r in plan.recommendations if r.scene_id == 2]
    acts = {r.action for r in recs}
    assert "CHANGE_VISUAL" in acts and "ADD_CUTAWAY_OPPORTUNITY" in acts
    ch = next(r for r in recs if r.action == "CHANGE_VISUAL")
    assert "LONG_VISUAL_SECTION" in ch.supporting_signals


def test_case_b_sparse_static_hold_vs_keep():
    tr = _tr(("slow", 9.0, 10.0), ("words.", 11.0, 12.0))
    kw = dict(cues=[_cue("c1", 9.0, 12.0, "slow words.")],
              scenes=_scenes((0, 4), (4, 8), (8, 20)),
              edl=_edl(("k", "KEEP", 0, 20)), transcript=tr, duration=20.0,
              visual=_vis(0.9, 0.8, 0.01))
    pod = _build(style="podcast", **kw)
    gen = _build(style="general", **kw)
    assert any(r.action == "HOLD_LONGER" and r.scene_id == 2
               for r in pod.recommendations)
    assert any(r.action == "KEEP" and r.scene_id == 2
               for r in gen.recommendations)


def test_case_c_fast_captions_stable_shot():
    tr = _tr(*_run(18, 0.0, 6.0))
    plan = _build([_cue("c1", 0, 2.0, "fast " * 6),
                   _cue("c2", 2.0, 4.0, "fast " * 6),
                   _cue("c3", 4.0, 6.0, "fast " * 6)],
                  _scenes((0, 6)), _edl(("k", "KEEP", 0, 6)),
                  transcript=tr, duration=6.0, visual=_vis(0.02))
    ch = [r for r in plan.recommendations if r.action == "CHANGE_VISUAL"]
    assert ch and "RAPID_CAPTION_SEQUENCE" in ch[0].supporting_signals


# ---------- 7-8. boundary / sentence / split-safe ----------

def _split_fixture(status):
    tr = _tr(("until", 4.0, 4.5), ("done.", 4.5, 4.9), ("after", 5.6, 6.0))
    cues = [_cue("c1", 4.0, 4.9, "until done."),
            _cue("c2", 5.6, 6.0, "after")]
    intel = _intel((4.0, 6.0, status, "s1"))
    return dict(cues=cues, scenes=_scenes((0, 5), (5, 10)),
                edl=_edl(("k", "KEEP", 0, 10)), transcript=tr, intel=intel)


def test_safe_split():
    plan = _build(**_split_fixture("SAFE"))
    sp = [r for r in plan.recommendations if r.action == "SPLIT"]
    assert sp and sp[0].safety_status == "SAFE"
    assert {"SCENE_BOUNDARY_OPPORTUNITY", "NATURAL_PAUSE",
            "SENTENCE_BOUNDARY"} <= set(sp[0].supporting_signals)


def test_unsafe_split_becomes_review():
    plan = _build(**_split_fixture("UNSAFE"))
    assert not any(r.action == "SPLIT" for r in plan.recommendations)
    rev = [r for r in plan.recommendations if r.action == "REVIEW"]
    assert rev
    assert any(c["winner"] == "keep" and c["principle"] == "edit_safety"
               for c in plan.conflicts)


def test_caution_split_becomes_review():
    plan = _build(**_split_fixture("CAUTION"))
    assert not any(r.action == "SPLIT" for r in plan.recommendations)
    assert any(r.action == "REVIEW" for r in plan.recommendations)


# ---------- 9. case D: placement conflict never moves ----------

def test_visual_conflict_review_never_moves():
    cues = [_cue("c1", 1.0, 2.0, "hello world")]
    before = copy.deepcopy(cues)
    vp = {"conflicts": [{"cue_id": "c1", "kind": "overlap_face",
                         "start": 1.0, "end": 2.0}]}
    plan = _build(cues, _scenes((0, 10)), _edl(("k", "KEEP", 0, 10)),
                  visual_plan=vp)
    assert cues == before  # inputs untouched
    rev = [r for r in plan.recommendations if r.action == "REVIEW"]
    assert rev and "never move" in rev[0].reason
    assert any(s.signal_type == "CAPTION_PLACEMENT_CONFLICT"
               for s in plan.signals)


# ---------- 10-11. TRIM eligibility ----------

def _trim_fixture(rs=2.0, re_=3.0, did=None, status="SAFE",
                  cue_span=(2.1, 2.9), terminal_before=True):
    did = did or f"{round(rs, 3)}"
    words = []
    if terminal_before:
        words += [("steady", 1.5, 1.8), ("end.", 1.8, 2.0)]
    else:
        words += [("steady", 1.5, 2.0)]
    words += [("flow", 3.1, 3.5)]
    tr = _tr(*words)
    cs, ce = cue_span
    cues = [_cue("c1", cs, ce, "inside removal")]
    edl = _edl(("k1", "KEEP", 0.0, rs), (did, "REMOVE", rs, re_),
               ("k2", "KEEP", re_, 10.0))
    intel = _intel((rs, re_, status, did))
    return dict(cues=cues, scenes=_scenes((0, 10)), edl=edl, transcript=tr,
                intel=intel)


def test_trim_eligible():
    plan = _build(**_trim_fixture())
    trims = [r for r in plan.recommendations if r.action == "TRIM"]
    assert len(trims) == 1
    assert (trims[0].start, trims[0].end) == (2.0, 3.0)
    assert trims[0].safety_status == "SAFE"
    assert trims[0].affected_caption_ids == ["c1"]


def test_trim_unsafe_becomes_review():
    plan = _build(**_trim_fixture(rs=5.0, re_=6.0, cue_span=(5.1, 5.9),
                                  status="UNSAFE"))
    assert not any(r.action == "TRIM" for r in plan.recommendations)
    rev = [r for r in plan.recommendations if r.action == "REVIEW"]
    assert rev and rev[0].safety_status == "UNSAFE"


def test_trim_sentence_split_downgraded():
    tr = _tr(("steady", 1.9, 2.0), ("flow", 2.8, 3.0))
    cues = [_cue("c1", 2.0, 2.8, "steady flow")]
    edl = _edl(("k1", "KEEP", 0.0, 2.0), ("2.0", "REMOVE", 2.0, 2.8),
               ("k2", "KEEP", 2.8, 10.0))
    plan = _build(cues, _scenes((0, 10)), edl, transcript=tr,
                  intel=_intel((2.0, 2.8, "SAFE", "2.0")))
    assert not any(r.action == "TRIM" for r in plan.recommendations)
    assert any(r.action == "REVIEW" and "sentence" in r.reason
               for r in plan.recommendations)


def test_trim_partial_cue_rejected():
    plan = _build(**_trim_fixture(cue_span=(2.5, 4.0)))
    assert not any(r.action == "TRIM" for r in plan.recommendations)
    assert any(r.action == "REVIEW" and "cue" in r.reason
               for r in plan.recommendations)


def test_no_unsafe_trim_executable():
    plan = _build(**_trim_fixture(rs=5.0, re_=6.0, cue_span=(5.1, 5.9),
                                  status="UNSAFE"))
    for r in plan.recommendations:
        if r.action == "TRIM":
            assert r.safety_status != "UNSAFE"


# ---------- 12. style adaptation ----------

def test_style_threshold_adaptation():
    base = cp.resolve_pacing_config(None)
    adapted, notes = cp._adapt_thresholds(base, "social_short")
    assert adapted["pacing_pause_s"] == 0.4
    assert adapted["pacing_caption_cps_fast"] == 14.0
    assert adapted["pacing_long_scene_ratio"] == 1.5
    assert notes


# ---------- 13. conflict resolution examples ----------

def _rec(action, s, e, priority="medium", conf=0.6, reason="r",
         safety="SAFE"):
    return PacingRecommendation(recommendation_id="x", action=action,
                                start=s, end=e, scene_id=0, priority=priority,
                                confidence=conf, reason=reason,
                                safety_status=safety)


def test_conflict_trim_vs_keep_safest_wins():
    kept, rejected = cp.rank_recommendations(
        [_rec("TRIM", 2.0, 3.0, "high", 0.7, "edl"),
         _rec("KEEP", 0.0, 10.0, "high", 0.6, "default")])
    assert [r.action for r in kept] == ["KEEP"]
    assert rejected and rejected[0]["action"] == "TRIM"


def test_conflict_unsafe_vs_safe_trim():
    kept, rejected = cp.rank_recommendations(
        [_rec("TRIM", 5.0, 6.0, "high", 0.7, "edl", safety="UNSAFE"),
         _rec("TRIM", 5.0, 6.0, "high", 0.7, "edl", safety="SAFE")])
    assert len(kept) == 1 and kept[0].safety_status == "SAFE"
    assert len(rejected) == 1 and rejected[0]["action"] == "TRIM"


def test_conflict_split_vs_keep():
    kept, _ = cp.rank_recommendations(
        [_rec("SPLIT", 4.5, 5.5, "medium", 0.6, "split"),
         _rec("KEEP", 0.0, 10.0, "informational", 0.65, "default")])
    assert any(r.action == "SPLIT" for r in kept)
    assert not any(r.action == "KEEP" for r in kept)


def test_ranking_order_merge_reject():
    recs = [_rec("KEEP", 20, 30, "informational", 0.6, "dflt"),
            _rec("TRIM", 2, 3, "high", 0.7, "edl"),
            _rec("KEEP", 25, 35, "informational", 0.6, "dflt")]
    kept, rejected = cp.rank_recommendations(recs)
    assert kept[0].action == "TRIM"  # priority first
    merged = [r for r in kept if r.action == "KEEP"]
    assert len(merged) == 1  # identical defaults merged
    assert (merged[0].start, merged[0].end) == (20, 35)
    assert [r.recommendation_id for r in kept] == ["rec_0001", "rec_0002"]
    assert not rejected


def test_case_a_pair_coexists():
    kept, rejected = cp.rank_recommendations(
        [_rec("CHANGE_VISUAL", 8, 20, "medium", 0.6, "dense"),
         _rec("ADD_CUTAWAY_OPPORTUNITY", 8, 20, "low", 0.5, "cut")])
    assert {r.action for r in kept} == {"CHANGE_VISUAL",
                                        "ADD_CUTAWAY_OPPORTUNITY"}
    assert not rejected


# ---------- 14. determinism ----------

def test_deterministic_build():
    kw = dict(cues=[_cue("c1", 0, 2.0, "hello world here"),
                    _cue("c2", 2.8, 4.0, "next line")],
              scenes=_scenes((0, 5), (5, 10)),
              edl=_edl(("k", "KEEP", 0, 10)),
              transcript=_tr(("hello", 0, 0.5), ("world.", 0.6, 1.0),
                             ("next", 2.8, 3.2)))
    a, b = asdict(_build(**kw)), asdict(_build(**kw))
    assert a == b
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def test_recommendations_grounded():
    plan = _build(**_split_fixture("SAFE"))
    emitted = {s.signal_type for s in plan.signals}
    assert plan.signals and all(s.evidence for s in plan.signals)
    for r in plan.recommendations:
        assert r.action in cp.ACTIONS
        assert r.evidence
        assert set(r.supporting_signals) <= emitted


def test_captions_immutable():
    cues = [_cue("c1", 1.0, 2.0, "hello world")]
    before = copy.deepcopy(cues)
    _build(cues, _scenes((0, 10)), _edl(("k", "KEEP", 0, 10)),
           transcript=_tr(("hello", 1.0, 1.4), ("world.", 1.5, 1.9)))
    assert cues == before


# ---------- 15. missing/invalid inputs ----------

def test_missing_required_inputs_error():
    cues = [_cue("c1", 0, 1.0, "hi")]
    with pytest.raises(cp.PacingError):
        _build(cues, {}, _edl(("k", "KEEP", 0, 10)))
    with pytest.raises(cp.PacingError):
        _build(cues, _scenes((0, 10)), {})
    with pytest.raises(cp.PacingError):
        _build(cues, _scenes((0, 10)), _edl(("k", "KEEP", 0, 10)),
               duration=0)


def test_degraded_inputs_warn_only():
    plan = _build([_cue("c1", 0, 1.0, "hi")], _scenes((0, 10)),
                  _edl(("k", "KEEP", 0, 10)))
    assert len(plan.warnings) == 5  # transcript/audio/visual/intel/brain
    assert plan.recommendations  # scene defaults still emitted


def test_invalid_coordinates_rejected():
    with pytest.raises(cp.PacingError):
        _build([], _scenes((5, 2)), _edl(("k", "KEEP", 0, 10)))
    with pytest.raises(cp.PacingError):
        _build([], _scenes((0, 10)), _edl(("x", "CUT", 0, 5)))


# ---------- 16-17. project cache / approval / CLI ----------

import itertools
import uuid
_SALT = itertools.count()


def _project_with_artifacts(salt=""):
    p = create_project(str(FIX / "tone_5s.mp4"))
    write_artifact(p.id, "analysis", "scenes.json", _scenes((0, 2.5), (2.5, 5)))
    write_artifact(p.id, "edit", "edit_decision.json",
                   _edl(("k", "KEEP", 0, 5), duration=5.0))
    write_artifact(p.id, "captions", "caption_plan.json",
                   {"schema_version": "caption-plan-1.0", "source": "t",
                    "transcript_hash": "h",
                    "cues": [_cue("c1", 0.5, 2.0, f"hello world{salt}")]})
    write_artifact(p.id, "analysis", "transcript.json",
                   _tr(("hello", 0.5, 1.0), (f"world{salt}.", 1.2, 1.8)))
    return p


def test_project_cache_hit_and_invalidation():
    from engine.editing.caption_pacing import run_caption_pacing_for_project
    p = _project_with_artifacts(salt=f"s{uuid.uuid4().hex[:8]}")  # unique content: fresh cache keys
    first = run_caption_pacing_for_project(p.id)
    assert first["cached"] is False
    second = run_caption_pacing_for_project(p.id)
    assert second["cached"] is True
    assert second["plan"] == first["plan"]
    assert run_caption_pacing_for_project(p.id, style_name="podcast")["cached"] is False
    assert run_caption_pacing_for_project(
        p.id, config_overrides={"pacing_pause_s": 0.9})["cached"] is False


def test_approval_and_drift():
    from engine.editing.caption_pacing import (
        approve_caption_pacing,
        run_caption_pacing_for_project,
        validate_caption_pacing_approval,
    )
    p = _project_with_artifacts()
    run_caption_pacing_for_project(p.id)
    approve_caption_pacing(p.id)
    assert validate_caption_pacing_approval(p.id)["plan"]
    cap = project_dir(p.id) / "captions" / "caption_plan.json"
    doc = json.loads(cap.read_text(encoding="utf-8"))
    doc["cues"].append(_cue("c9", 3.0, 4.0, "tampered"))
    cap.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(cp.PacingError):
        validate_caption_pacing_approval(p.id)


def test_dry_run_writes_nothing():
    from engine.editing.caption_pacing import run_caption_pacing_for_project
    p = _project_with_artifacts()
    res = run_caption_pacing_for_project(p.id, dry_run=True)
    assert res["dry_run"] is True
    assert not (project_dir(p.id) / "editing" / "caption_pacing_plan.json").is_file()


def test_cli_success_and_errors(capsys):
    from engine.cli import main
    p = _project_with_artifacts()
    assert main(["caption-pacing", p.id]) == 0
    assert main(["approve-caption-pacing", p.id]) == 0
    assert main(["caption-pacing", "project_19000101_000000"]) == 2
    q = create_project(str(FIX / "tone_5s.mp4"))  # no artifacts
    assert main(["caption-pacing", q.id]) == 2


# ---------- 18. real E2E ----------

def test_real_chain_e2e(need_ffmpeg):
    from engine.analysis.scenes import detect_scenes_project
    from engine.analysis.speech import transcribe_to_project
    from engine.analysis.visual import run_visual_for_project
    from engine.core.orchestrator import run_inspect
    from engine.editing.brain import run_editor_brain_for_project
    from engine.editing.caption_pacing import (
        approve_caption_pacing,
        run_caption_pacing_for_project,
        validate_caption_pacing_approval,
    )
    from engine.editing.decisions import build_edl_for_project
    from engine.editing.intelligence import run_intelligence_for_project
    from engine.subtitles.captions import (
        approve_captions,
        caption_plan_for_project,
    )
    from engine.subtitles.visual_captions import (
        approve_caption_visual,
        caption_visual_for_project,
    )
    src = str(FIX / "speech_video.mp4")
    pid = run_inspect(src)["project"]
    transcribe_to_project(src, project_id=pid, model="tiny")
    detect_scenes_project(src, project_id=pid)
    build_edl_for_project(pid)
    run_intelligence_for_project(pid)
    run_visual_for_project(pid)
    run_editor_brain_for_project(pid)
    caption_plan_for_project(pid)
    approve_captions(pid, mode="sidecar")
    caption_visual_for_project(pid)
    approve_caption_visual(pid)

    first = run_caption_pacing_for_project(pid)
    plan = first["plan"]
    assert plan["signals"] and plan["recommendations"]
    assert all(s["evidence"] for s in plan["signals"])
    cue_ids = {c["cue_id"] for c in
               json.loads((project_dir(pid) / "captions" / "caption_plan.json")
                          .read_text(encoding="utf-8"))["cues"]}
    for r in plan["recommendations"]:
        assert r["action"] in cp.ACTIONS
        assert set(r["affected_caption_ids"]) <= cue_ids
    second = run_caption_pacing_for_project(pid)
    assert second["cached"] is True
    assert second["plan"] == first["plan"]

    approve_caption_pacing(pid)
    assert validate_caption_pacing_approval(pid)["plan"]
    assert (project_dir(pid) / "editing" / "caption_pacing_plan.json").is_file()
    assert (project_dir(pid) / "editing" / "approved_caption_pacing_plan.json").is_file()
    renders = project_dir(pid) / "renders"
    media = list(renders.glob("*.mp4")) + list(renders.glob("*.srt")) \
        + list(renders.glob("*.vtt")) + list(renders.glob("*.ass")) \
        if renders.is_dir() else []
    assert media == []  # analysis only: pacing writes no media
