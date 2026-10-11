import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from decision_engine.primitives import choice_answer, confidence, noul_answer, score_answer, softmax


def test_confidence_peaked_is_one():
    assert confidence([1.0, 0.0, 0.0]) == 1.0


def test_confidence_uniform_is_zero():
    assert abs(confidence([0.5, 0.5]) - 0.0) < 1e-9
    assert abs(confidence([1 / 3] * 3) - 0.0) < 1e-9


def test_softmax_sums_to_one():
    p = softmax([2.0, 1.0, 0.5])
    assert abs(sum(p) - 1.0) < 1e-9


def test_choice_shape_and_probs():
    a = choice_answer(["A", "B", "C"], [0.7, 0.2, 0.1])
    assert a["type"] == "choice" and a["choice"] == "A"
    assert abs(sum(a["probabilities"].values()) - 1.0) < 0.01


def test_score_between_levels():
    a = score_answer(["low", "mid", "high"], [0.1, 0.6, 0.3])
    assert a["type"] == "score" and 0 <= a["score"] <= 2
    assert a["legend"] == {"0": "low", "1": "mid", "2": "high"}


def test_noul_shape():
    a = noul_answer(0.94)
    assert a == {"type": "noul", "noul": 0.94}


def test_restaurant_example():
    import decision_engine.engine as E
    eng = E.LocalDecisionEngine()
    ans = eng.decide("Someone is asking for a website for their restaurant.",
                     {"opp": {"type": "choice", "instructions": "real service opportunity?",
                              "criteria": {"A": "real service opportunity", "B": "maybe",
                                           "C": "irrelevant"}}})
    assert set(ans["opp"]) == {"type", "choice", "confidence", "probabilities"}
