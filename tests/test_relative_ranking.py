# -*- coding: utf-8 -*-
"""Planner 3.1: relative-floor ranking, keep/swap log, motion/camera."""
import sys

sys.path.insert(0, ".")
import pytest

from engine.tools import diversity as D


def _mem():
    return D.DiversityMemory(seed=7)


def _c(cid, rel, dims=None, ok=True):
    return {"id": cid, "relevance": rel, "dims": dims or {},
            "acceptable": ok}


def test_semantic_leader():
    mem = _mem()
    r = D.rank_relative([_c("b", 0.7, {"asset": "b"}),
                         _c("a", 0.9, {"asset": "a"})], mem, 0)
    assert r["leader"] == "a"
    assert r["ranked"][0]["id"] == "a"


def test_relative_floor_value():
    mem = _mem()
    r = D.rank_relative([_c("a", 1.0, {}), _c("b", 0.5, {})], mem, 0)
    assert r["floor"] == round(max(0.85 * 1.0, 1.0 - 0.15), 4) == 0.85


def test_case_a_leader_keeps():
    mem = _mem()
    r = D.rank_relative([_c("a", 0.95, {"asset": "x"}),
                         _c("b", 0.90, {"asset": "y"})], mem, 0)
    assert r["decision"]["decision"] == "KEEP_BEST_SEMANTIC"
    assert r["decision"]["replacement"] == "a"


def test_case_b_diversity_swap():
    mem = _mem()
    mem.record(0, {"asset": "x", "motion": "push", "camera": "hold"})
    r = D.rank_relative([_c("a", 0.90, {"asset": "x", "motion": "push"}),
                         _c("b", 0.85, {"asset": "y", "motion": "hold"})],
                        mem, 1, window=5)
    assert r["decision"]["decision"].startswith("SWAP")
    assert r["decision"]["replacement"] == "b"
    assert r["decision"]["semantic_delta"] == -0.05
    assert r["decision"]["diversity_gain"] >= 0.05


def test_case_c_semantic_rejection():
    mem = _mem()
    mem.record(0, {"asset": "x"})
    r = D.rank_relative([_c("a", 0.95, {"asset": "x"}),
                         _c("b", 0.50, {"asset": "y"})], mem, 1)
    ids = [x["id"] for x in r["ranked"]]
    assert "b" not in ids
    assert r["decision"]["replacement"] == "a"


def test_case_d_negligible_gain():
    mem = _mem()
    r = D.rank_relative([_c("a", 0.90, {"asset": "x"}),
                         _c("b", 0.895, {"asset": "y"})], mem, 0,
                        config={"minimum_diversity_gain": 5.0})
    assert r["decision"]["decision"] == "KEEP_BEST_SEMANTIC"


def test_case_e_callback_overrides():
    mem = _mem()
    mem.record(0, {"asset": "x"})
    r = D.rank_relative([_c("a", 0.9, {"asset": "x"}),
                         _c("b", 0.9, {"asset": "x"})], mem, 1,
                        context={"callback": True})
    assert r["decision"]["decision"] == "CALLBACK_ALLOWED"


def test_case_f_no_alternative():
    mem = _mem()
    r = D.rank_relative([_c("only", 0.6, {"asset": "z"})], mem, 0)
    assert r["decision"]["decision"] == "KEEP_BECAUSE_ALTERNATIVES_TOO_WEAK"


def test_case_g_motion_swap():
    mem = _mem()
    mem.record(0, {"motion": "push"})
    mem.record(1, {"motion": "push"})
    out = D.select_motion(["push", "reveal"], mem, 2, story_state="EXAMPLE")
    assert out["motion"] == "reveal"
    assert "push" in out["reason"]


def test_case_h_camera_swap():
    mem = _mem()
    mem.record(0, {"camera": "push", "composition": "center"})
    mem.record(1, {"camera": "push", "composition": "center"})
    out = D.select_camera(["push", "static"], "center", mem, 2)
    assert out["camera"] == "static"


def test_motion_none_when_empty():
    out = D.select_motion([], _mem(), 0)
    assert out["motion"] == "NONE"


def test_motion_no_mechanical_rotation():
    mem = _mem()
    out = D.select_motion(["push"], mem, 0, story_state="PAYOFF")
    assert out["motion"] == "push"


def test_combo_repetition_warn():
    mem = _mem()
    mem.record(0, {"camera": "push", "composition": "center"})
    mem.record(1, {"camera": "push", "composition": "center"})
    r = D.combo_repeat(mem, "push", "center", 2)
    assert r["warn"] is True and r["consecutive"] == 2
    assert D.combo_repeat(mem, "static", "center", 2)["warn"] is False


def test_keep_reason_logged():
    mem = _mem()
    r = D.rank_relative([_c("a", 0.9, {}), _c("b", 0.8, {})], mem, 0)
    d = r["decision"]
    assert set(("decision", "original", "replacement", "semantic_delta",
                "diversity_gain", "reason")) <= set(d)


def test_swap_reason_logged():
    mem = _mem()
    mem.record(0, {"asset": "x"})
    r = D.rank_relative([_c("a", 0.9, {"asset": "x"}),
                         _c("b", 0.88, {"asset": "y"})], mem, 1)
    d = r["decision"]
    assert d["decision"].startswith("SWAP") and d["replacement"] == "b"
    assert "reason" in d and d["semantic_delta"] < 0


def test_deterministic_ranking():
    mem = D.DiversityMemory(seed=7)
    cands = [_c("m", 0.8, {"motion": "push"}),
             _c("n", 0.8, {"motion": "reveal"})]
    r1 = D.rank_relative(cands, mem, 3)
    r2 = D.rank_relative(cands, D.DiversityMemory(seed=7), 3)
    del r1, r2
    mem2 = D.DiversityMemory(seed=7)
    a = D.rank_relative(cands, mem, 3)
    b = D.rank_relative(cands, mem2, 3)
    assert a == b


def test_contribution_score():
    mem = _mem()
    mem.record(0, {"asset": "x", "motion": "push"})
    c = D.diversity_contribution({"asset": "x", "motion": "hold",
                                  "camera": "pan"}, mem, 1, window=5)
    assert c["parts"]["asset"] < c["parts"]["camera"] == 1.0
    assert 0.0 <= c["total"] <= 1.0


def test_plan_report():
    rep = D.plan_report([{"decision": "KEEP_BEST_SEMANTIC"},
                         {"decision": "SWAP_FOR_ASSET_VARIETY"}])
    assert rep["swaps"] == 1 and rep["keeps"] == 1
    assert rep["candidate_decisions"] == 2


def test_benchmark_planner_output_logged():
    from engine.tools import visual_plan as V
    pool = [{"file": "b.mp4", "w": 1280, "h": 720, "dur": 30.0,
             "tags": ["neon", "code"]},
            {"file": "a.mp4", "w": 1280, "h": 720, "dur": 30.0,
             "tags": ["neon", "code"]}]
    narr = [{"id": "s1", "span": [0, 12], "text": "neon code",
             "need": "neon code"}]
    r = V.plan_shots_diverse(narr, pool, seed=7)
    assert r["log"] and all(
        {"decision", "shot", "reason"} <= set(d) for d in r["log"])
    assert r["planner_version"] == "visual_plan/3.0"
    assert r["seed"] == 7
