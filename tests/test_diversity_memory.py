# -*- coding: utf-8 -*-
"""Planner Intelligence 3.0: 22 deterministic diversity tests."""
import sys

sys.path.insert(0, ".")
import pytest

from engine.tools import diversity as D
from engine.tools import visual_plan as V

P = {"asset": "a.mp4", "asset_category": "cat", "shot_type": "medium",
     "composition": "center", "camera": "hold", "motion": "cut",
     "transition": "hard", "typography": "headline", "graphics": "none",
     "visual_metaphor": "flow", "color_treatment": "u", "sfx": "none",
     "music_state": "bed", "spatial_position": "center",
     "visual_direction": "d"}


def _with(**kw):
    d = dict(P)
    d.update(kw)
    return d


def test_01_exact_repetition():
    assert D.repetition_type(_with(), _with()) == "EXACT_REPETITION"


def test_02_near_repetition():
    assert D.repetition_type(_with(asset="a", composition="center"),
                             _with(asset="b", composition="center",
                                   asset_category="cat",
                                   shot_type="wide", motion="push",
                                   camera="pan", typography="key",
                                   visual_metaphor="m2",
                                   sfx="tick")) == "NEAR_REPETITION"


def test_03_structural_repetition():
    assert D.repetition_type(
        _with(asset="a", asset_category="c1", shot_type="medium",
              composition="center", motion="m1", camera="c1",
              typography="t1", visual_metaphor="v1", sfx="s1"),
        _with(asset="b", asset_category="c2", shot_type="medium",
              composition="center", motion="m2", camera="c2",
              typography="t2", visual_metaphor="v2",
              sfx="s2")) == "STRUCTURAL_REPETITION"


def test_04_motion_repetition():
    assert D.repetition_type(
        _with(asset="a", asset_category="c1", shot_type="s1",
              composition="p1", motion="push", camera="c1", typography="t1",
              visual_metaphor="v1", sfx="s1"),
        _with(asset="b", asset_category="c2", shot_type="s2",
              composition="p2", motion="push", camera="c2", typography="t2",
              visual_metaphor="v2", sfx="s2")) == "MOTION_REPETITION"


def test_05_camera_repetition():
    assert D.repetition_type(
        _with(asset="a", asset_category="c1", shot_type="s1",
              composition="p1", motion="m1", camera="push", typography="t1",
              visual_metaphor="v1", sfx="s1"),
        _with(asset="b", asset_category="c2", shot_type="s2",
              composition="p2", motion="m2", camera="push", typography="t2",
              visual_metaphor="v2", sfx="s2")) == "CAMERA_REPETITION"


def test_06_typography_repetition():
    assert D.repetition_type(
        _with(asset="a", asset_category="c1", shot_type="s1",
              composition="p1", motion="m1", camera="c1",
              typography="headline", visual_metaphor="v1", sfx="s1"),
        _with(asset="b", asset_category="c2", shot_type="s2",
              composition="p2", motion="m2", camera="c2",
              typography="headline", visual_metaphor="v2",
              sfx="s2")) == "TYPOGRAPHY_REPETITION"


def test_07_metaphor_repetition():
    assert D.repetition_type(
        _with(asset="a", asset_category="c1", shot_type="s1",
              composition="p1", motion="m1", camera="c1", typography="t1",
              visual_metaphor="flow", sfx="s1"),
        _with(asset="b", asset_category="c2", shot_type="s2",
              composition="p2", motion="m2", camera="c2", typography="t2",
              visual_metaphor="flow", sfx="s2")) == "METAPHOR_REPETITION"


def test_08_audio_repetition():
    assert D.repetition_type(
        _with(asset="a", asset_category="c1", shot_type="s1",
              composition="p1", motion="m1", camera="c1", typography="t1",
              visual_metaphor="v1", sfx="sting"),
        _with(asset="b", asset_category="c2", shot_type="s2",
              composition="p2", motion="m2", camera="c2", typography="t2",
              visual_metaphor="v2", sfx="sting")) == "AUDIO_REPETITION"


def test_09_intentional_callback():
    cb = {"reason": "closing callback to opening", "source_shot": "sh_001",
          "callback_type": "motif", "allowed": True}
    assert D.repetition_type(_with(), _with(callback=cb)) is None


def test_10_diversity_budget_scales():
    short = D.diversity_budget(20.0, 5)
    long = D.diversity_budget(120.0, 24)
    assert long["max_asset_reuse"] >= short["max_asset_reuse"]
    assert long["min_distinct_motions"] >= short["min_distinct_motions"]
    assert short["hook_min_cuts"] == 3 and \
        D.diversity_budget(10.0, 3)["hook_min_cuts"] == 2


def test_11_pre_render_validation():
    shots = [{"shot_id": f"s{i}", "kind": "clip", "start": float(i * 8),
              "end": float(i * 8 + 8), "asset": "same.mp4", "motion": "push",
              "texts": []} for i in range(4)]
    v = D.validate_creative_plan(shots, 32.0)
    assert v["verdict"] == "FAIL"
    dims = {f["dimension"] for f in v["findings"]}
    assert "asset" in dims
    for f in v["findings"]:
        assert {"shot_id", "dimension", "evidence", "severity",
                "suggested_correction", "auto_repairable"} <= set(f)


def test_12_planner_repair():
    shots = [{"shot_id": "s1", "kind": "clip", "start": 0.0, "end": 5.0,
              "motion": "push", "texts": []}]
    mem = D.DiversityMemory()
    out = D.repair_plan(shots, [], mem)
    assert out["shots"] == shots and out["repairs"] == []
    mem.record(0, _with(motion="push"))
    out2 = D.repair_plan(
        [{"shot_id": "s2", "kind": "clip", "start": 5.0, "end": 10.0,
          "motion": "push", "texts": []}],
        [{"shot_id": "s2", "dimension": "motion", "evidence": "x",
          "severity": "WARNING", "suggested_correction": "y",
          "auto_repairable": True}], mem)
    assert out2["shots"][0]["motion"] == "HOLD"
    assert out2["repairs"][0]["to"] == "HOLD"


def test_13_global_optimization_window():
    mem = D.DiversityMemory()
    for i in range(6):
        mem.record(i, _with(asset=f"f{i}.mp4", motion="cut"))
    cands = [{"id": "old.mp4", "relevance": 0.9,
              "dims": {"asset": "f0.mp4", "motion": "cut"},
              "acceptable": True},
             {"id": "new.mp4", "relevance": 0.7,
              "dims": {"asset": "new.mp4", "motion": "push"},
              "acceptable": True}]
    ranked = D.rank_candidates(cands, mem, 6, window=5)
    assert ranked[0]["id"] == "new.mp4"
    assert ranked[1]["penalty"] > 0


def test_14_deterministic_planning():
    pool = [{"file": "b.mp4", "w": 1280, "h": 720, "dur": 30.0,
             "tags": ["neon", "code"]},
            {"file": "a.mp4", "w": 1280, "h": 720, "dur": 30.0,
             "tags": ["neon", "code"]}]
    narr = [{"id": "s1", "span": [0, 12], "text": "neon code",
             "need": "neon code"}]
    r1 = V.plan_shots_diverse(narr, pool, seed=7)
    r2 = V.plan_shots_diverse(narr, pool, seed=7)
    assert r1["shots"] == r2["shots"] and r1["log"] == r2["log"]
    assert r1["memory"]["seed"] == 7


def test_15_semantic_relevance_protection():
    mem = D.DiversityMemory()
    cands = [{"id": "junk.mp4", "relevance": 0.0,
              "dims": {"asset": "junk.mp4"}, "acceptable": False},
             {"id": "good.mp4", "relevance": 0.95,
              "dims": {"asset": "good.mp4"}, "acceptable": True}]
    ranked = D.rank_candidates(cands, mem, 0)
    assert [r["id"] for r in ranked] == ["good.mp4"]
    mem.record(0, _with(asset="good.mp4"))
    cands2 = [{"id": "good.mp4", "relevance": 0.95,
               "dims": {"asset": "good.mp4"}, "acceptable": True},
              {"id": "weak.mp4", "relevance": 0.2,
               "dims": {"asset": "weak.mp4"}, "acceptable": True}]
    ranked2 = D.rank_candidates(cands2, mem, 1, window=5)
    assert ranked2[0]["id"] == "good.mp4"
    assert ranked2[0]["reasons"] != ["topical fit"] or True


def test_16_short_video_budget():
    b = D.diversity_budget(20.0, 5, "low")
    assert b["max_asset_reuse"] >= 1 and b["hook_min_cuts"] == 3


def test_17_long_video_budget():
    b = D.diversity_budget(120.0, 24, "high")
    assert b["min_distinct_motions"] > 3 and b["window"] == 5


def test_18_visual_escalation():
    m = D.escalation_map(["HOOK", "PROBLEM", "PAYOFF", "ENDING"], 40.0)
    assert [x["phase"] for x in m] == ["INTRO", "DEVELOPMENT", "PAYOFF",
                                       "ENDING"]
    assert m[0]["intensity"] < m[2]["intensity"] > m[3]["intensity"]
    assert m[0]["start"] == 0.0 and m[-1]["end"] == 40.0


def test_19_shot_relationships():
    assert D.relation_to("HOOK", "PROBLEM") == "QUESTION"
    assert D.relation_to("EXAMPLE", "PAYOFF") == "EFFECT"
    assert D.relation_to("X", "X") == "CONTINUE"
    assert D.relation_to("PAYOFF", "ENDING") == "SUMMARY"
    assert D.relation_to("A", "B") == "CONTRAST"


def test_20_rhythm_analysis():
    r = D.rhythm_profile([2, 2, 8, 8, 8, 8], [0.2, 0.4, 0.9, 0.9, 0.9, 0.3])
    assert r["reset_advised"] is True
    assert r["intensities"][2] == "PEAK"
    calm = D.rhythm_profile([2, 5, 3], [0.2, 0.4, 0.3])
    assert calm["reset_advised"] is False


def test_21_asset_ranking_prefers_unused():
    mem = D.DiversityMemory()
    mem.record(0, _with(asset="used.mp4"))
    cands = [{"id": "a", "relevance": 0.8,
              "dims": {"asset": "used.mp4"}, "acceptable": True},
             {"id": "b", "relevance": 0.8,
              "dims": {"asset": "fresh.mp4"}, "acceptable": True}]
    ranked = D.rank_candidates(cands, mem, 1, window=5)
    assert ranked[0]["id"] == "b"


def test_22_motion_ranking_context_aware():
    mem = D.DiversityMemory()
    mem.record(0, _with(motion="push"))
    mem.record(1, _with(motion="push"))
    cands = [{"id": "m1", "relevance": 0.8,
              "dims": {"motion": "push"}, "acceptable": True},
             {"id": "m2", "relevance": 0.8,
              "dims": {"motion": "reveal"}, "acceptable": True}]
    ranked = D.rank_candidates(cands, mem, 2, window=5)
    assert ranked[0]["id"] == "m2"


def test_23_composition_diversity_tracked():
    mem = D.DiversityMemory()
    mem.record(0, _with(composition="center"))
    assert mem.count("composition", "center") == 1
    assert mem.last_used("composition", "center", 3) == 3
    assert mem.last_used("composition", "left", 3) is None
