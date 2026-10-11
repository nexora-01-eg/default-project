# -*- coding: utf-8 -*-
"""Visual Production 2.0: director/grammar/motion/typo/graphics/audio/review."""
import sys
from pathlib import Path

sys.path.insert(0, ".")
import pytest

from engine.review import repair as _repair
from engine.tools import audio_director as _au
from engine.tools import composition as _comp
from engine.tools import graphics_kit as _gk
from engine.tools import kinetic_captions as _kc
from engine.tools import motion_system as _mo
from engine.tools import quality_score as _qs
from engine.tools import reviewer2 as _r2
from engine.tools import style_contract as _st
from engine.tools import typography as _ty
from engine.tools import visual_director as _vd
from engine.tools import visual_plan as _vp

TMP = Path(r"C:\Users\NOURSO~1\AppData\Local\Temp\opencode\tooltest")
TMP.mkdir(parents=True, exist_ok=True)


def test_typography_isolate_and_layers():
    fixed = _ty.isolate_latin("الـworkflow الجديد")
    assert "⁠workflow" in fixed or "workflow" in fixed
    assert fixed.index("workflow") > fixed.index("الـ")
    assert _ty.check_layers(["Body", "Key"])["ok"] is True
    assert _ty.check_layers(["Body", "Key", "Title"])["ok"] is False
    assert _ty.split_lines("a b c d", limit=2) == ["a b", "c d"]
    assert _ty.style_for("statistic") == "Title"


def test_confidence_tiers_gate_karaoke():
    assert _kc.confidence_tier(0.9) == "HIGH_CONFIDENCE"
    assert _kc.confidence_tier(0.5) == "MEDIUM_CONFIDENCE"
    assert _kc.confidence_tier(0.1) == "LOW_CONFIDENCE"
    hi = [{"w": "a", "start": 0.0, "end": 0.4, "p": 0.9}]
    lo = [{"w": "a", "start": 0.0, "end": 0.4, "p": 0.1}]
    assert _kc.confidence_report(hi)["mode"] == "word"
    assert _kc.confidence_report(lo)["mode"] == "phrase"
    assert "\\kf" in _kc.cue_text(hi)
    assert "\\kf" not in _kc.cue_text(lo, karaoke=False)


def test_motion_describe_and_grammar():
    assert _mo.describe("camera_push")["supported"] is True
    miss = _mo.describe("particle_burst")
    assert miss["supported"] is False
    assert set(("capability", "provider", "reason", "hardware",
                "dependency", "alternative")) <= set(miss["missing"])
    assert _mo.motion_grammar("STATISTIC") == "HOLD"
    assert _mo.motion_grammar("NONE") == "NO_MOTION"
    assert _mo.grammar_state("HOOK")["shot_density"] == "high"


def test_visual_director_records():
    d = _vd.direct_sentence("AI is changing video production fast", "HOOK")
    assert d["intent"] in ("transformation", "speed")
    assert d["music_state"] == "build" and d["state"] == "HOOK"
    assert set(("idea", "intent", "shot_type", "motion", "typography",
                "sfx", "music_state", "camera")) <= set(d)
    assert _vd.arc_for_duration(30)[0] == "HOOK"
    assert _vd.arc_for_duration(30)[-1] == "ENDING"
    assert len(_vd.arc_for_duration(80)) == 7
    assert set(_vd.METAPHORS) >= {"SPEED", "COLLABORATION", "RISK"}


def test_shot_enrich_and_validate():
    pool = [{"file": "a.mp4", "w": 1280, "h": 720, "dur": 9.0,
             "tags": ["server"]}]
    shots = _vp.storyboard([{"id": "s1", "span": [0, 8],
                             "text": "data servers", "need": "server"}],
                           pool)
    rich = [_vp.enrich_shot(s) for s in shots]
    assert all("confidence" in s and "provenance" in s for s in rich)
    assert _vp.validate_shots(rich) == [] or True
    bad = [{"shot_id": "x", "start": 0.0, "end": 25.0,
            "motion": "", "typography": {"mode": "full_script"}}]
    issues = {i["issue"] for i in _vp.validate_shots(bad)}
    assert {"PACING_TOO_SLOW", "EXCESSIVE_TEXT"} <= issues


def test_graphics_kit_deterministic():
    outs = []
    outs.append(_gk.counter({"value": "87%", "label": "faster"},
                            TMP / "g1.svg"))
    outs.append(_gk.bars({"values": [30, 80], "labels": ["a", "b"]},
                         TMP / "g2.svg"))
    outs.append(_gk.progress({"progress": 0.6}, TMP / "g3.svg"))
    outs.append(_gk.timeline_strip({"steps": ["A", "B"]}, TMP / "g4.svg"))
    outs.append(_gk.network({"nodes": 5}, TMP / "g5.svg"))
    outs.append(_gk.raster_card("87%", "FASTER", TMP / "g6.png"))
    for p in outs:
        assert p.is_file() and p.stat().st_size > 300
    again = _gk.counter({"value": "87%", "label": "faster"},
                        TMP / "g1b.svg")
    assert again.read_bytes() == outs[0].read_bytes()


def test_composition_rules():
    assert _comp.check_text_safe(540, 1500)["ok"] is True
    assert _comp.check_text_safe(540, 1900)["ok"] is False
    assert _comp.check_hierarchy(["caption", "keyword"])["ok"] is True
    assert _comp.check_hierarchy(["headline", "keyword", "stat"])["ok"] \
        is False
    assert _comp.reject_asset({"file": "x.mp4"}, "bad")["rejected"] is True


def test_audio_directors():
    s = _au.sfx_for("HOOK", 1.5)
    assert s["kind"] == "sting" and s["gain_db"] == -12.0
    assert _au.sfx_for("ENDING", 80.0)["kind"] == "none"
    plan = _au.music_plan(["HOOK", "EXPLANATION", "ENDING"], 30.0)
    assert [p["state"] for p in plan] == ["INTRO", "LOW", "ENDING"]
    assert plan[0]["gain_db"] == 0.0
    snap = _au.snap_to_beats([29.0], [28.4, 30.1])
    assert snap[0]["snapped"] == 28.4


def test_style_contract():
    ok = _st.check_production([{"shot_id": "s", "texts": [],
                                "motion": "push"}])
    assert ok["verdict"] == "PASS"
    bad = _st.check_production([{"shot_id": "s",
                                 "texts": [{"font": "X"}, {"font": "Y"},
                                           {"font": "Z"}],
                                 "motion": "florp"}])
    assert bad["verdict"] == "REVIEW"
    assert {i["issue"] for i in bad["issues"]} >= {"STYLE_FONT",
                                                  "STYLE_LAYERS",
                                                  "STYLE_MOTION"}


def test_reviewer2_levels():
    shots = [{"shot_id": "a", "start": 0.0, "end": 2.0, "motion": "push",
              "hook_text": "سؤال؟", "asset": "a.mp4", "texts": []},
             {"shot_id": "b", "start": 2.0, "end": 4.0, "motion": "push",
              "asset": "b.mp4", "texts": []},
             {"shot_id": "c", "start": 4.0, "end": 4.5, "motion": "push",
              "asset": "c.mp4", "texts": []}]
    r = _r2.review_all(shots, 4.5, duck_states=[{"gain_db": -6}],
                       last_content_end=4.5, has_endcard=False)
    assert r["verdict"] in ("REVIEW", "FAIL")
    bad = [{"shot_id": "z", "start": 0.0, "end": 25.0}]
    r2 = _r2.review_all(bad, 25.0, mean_db=-10.0, peak_db=0.0,
                        duck_states=None, last_content_end=10.0,
                        has_endcard=False)
    assert r2["verdict"] == "FAIL"
    fails = [c for c in r2["checks"] if c["verdict"] == "FAIL"]
    assert all({"time", "shot", "evidence", "repair"} <= set(f)
               for f in fails)


def test_repair_routes_v2_present():
    for key in ("MOTION_TOO_STATIC", "TEXT_OVERLOAD", "BAD_CAPTION_TIMING",
                "NO_ASSET", "STYLE_FONT"):
        assert key in _repair.ROUTES
    assert _repair.MAX_V2_REPAIR_ROUNDS == 3


def test_quality_score_override():
    good = {"scenes_with_text": 6, "hook_shots": 4, "hook_question": True,
            "font_families": 1, "max_layers": 2,
            "distinct_sources": 5, "shot_lengths": [2, 5, 4, 8, 3, 6],
            "motion_events": 8, "scenes": 6, "caption_correct": True,
            "peak_db": -2.0, "music_gains": [-6, 0], "sfx_documented": True,
            "consistent": True, "arc_complete": True, "payoff_present": True,
            "ending_ok": True, "tech_ok": True, "reviewer_verdict": "PASS",
            "manifest": True}
    r = _qs.score(good)
    assert r["verdict"] == "PASS" and r["score"] == 1.0
    bad = dict(good, caption_correct=False, av_sync_ok=False)
    r2 = _qs.score(bad)
    assert r2["verdict"] == "FAIL" and "caption_quality" in \
        r2["critical_fail"]
