"""Production-stack unit tests: contract, visual plan, motion, kinetic, review."""
import sys
from pathlib import Path

sys.path.insert(0, ".")
import pytest

from engine.tools import contract_schema, visual_plan, motion_system
from engine.tools import kinetic_captions as KC
from engine.tools import visual_review as VR

TMP = Path(r"C:\Users\NOURSO~1\AppData\Local\Temp\opencode\tooltest")
TMP.mkdir(parents=True, exist_ok=True)


def test_contract_valid_and_invalid():
    good = {"project": "p", "canvas": {"w": 1080, "h": 1920, "fps": 30},
            "narration": {"segments": [{"id": "n1", "text": "hi",
                                        "start": 0.0}]},
            "shots": [{"shot_id": "sh_001", "start": 0.0, "end": 2.0}]}
    assert contract_schema.validate_contract(good)["valid"] is True
    bad = {"project": "p"}
    r = contract_schema.validate_contract(bad)
    assert r["valid"] is False and r["errors"]


def test_visual_plan_concepts():
    assert visual_plan.concept_of("cut the repetitive workload")[0] == \
        "repetitive_task"
    assert visual_plan.concept_of("the human decides")[0] == "humanSubmit"
    beats = visual_plan.plan_visual_beats(
        [{"id": "n1", "span": [0, 3], "text": "hook question؟"},
         {"id": "n2", "span": [3, 9], "text": "analysis of data"}])
    assert beats[0]["intent"] == "hook" and beats[0]["transition"] == \
        "fade in"
    assert beats[1]["transition"] == "hard cut"


def test_storyboard_pure():
    pool = [{"file": "a.mp4", "w": 1280, "h": 720, "dur": 9.0,
             "tags": ["server", "data"]}]
    shots = visual_plan.storyboard(
        [{"id": "s1", "span": [0, 8], "text": "data servers",
          "need": "server data"}], pool)
    assert len(shots) >= 2 and shots[0]["shot_id"] == "sh_001"


def test_motion_system_maps():
    assert "fad" in motion_system.ass_tags("FADE_IN").lower() or \
        "\\fad" in motion_system.ass_tags("FADE_IN")
    cam = motion_system.camera_contract("PUSH_IN", "a.mp4", "b.mp4")
    assert cam["zoom_to"] == 1.12
    assert motion_system.camera_contract("HOLD", "a.mp4", "b.mp4") is None
    assert motion_system.grammar_state("hook")["shot_density"] == "high"


def test_kinetic_pure_helpers():
    words = [{"w": f"w{i}", "start": float(i), "end": float(i) + 0.4}
             for i in range(10)]
    cues = KC.chunk_words(words, limit=8)
    assert [len(c) for c in cues] == [8, 2]
    assert "\\kf" in KC.cue_text([{"w": "AI", "start": 0.0, "end": 0.5}])


def test_kinetic_from_real_words():
    from engine.tools.adapters.providers import get
    fix = (Path(".").resolve() / "tests" / "fixtures" / "speech_sapi.wav")
    if not fix.is_file():
        pytest.skip("SAPI fixture absent")
    get("faster-whisper").run({"src": str(fix),
                               "out": str(TMP / "kw.json"),
                               "model": "tiny", "language": "en"})
    rep = KC.build_ass(TMP / "kw.json", TMP / "kin.ass",
                       keywords=[(1.0, 3.0, "fox")],
                       title=("T1", "T2", 0.0, 1.0),
                       endcard=("E1", "E2", 30.0, 32.0))
    text = Path(TMP / "kin.ass").read_text(encoding="utf-8")
    assert rep["words"] >= 10 and "\\kf" in text and "WEBVTT" not in text


def test_visual_review_flags():
    tl = {"total": 10.0, "segments": [
        {"kind": "clip", "label": "long-static", "span": [0, 8]}]}
    r = VR.review_all(tl, 99, ["a.mp4"] * 5, mean_db=-30.0, peak_db=-0.5)
    issues = {i["issue"] for i in r["issues"]}
    assert {"MOTION_TOO_STATIC", "TEXT_OVERLOAD", "ASSET_REPETITION",
            "AUDIO_TOO_QUIET", "AUDIO_CLIPPING_RISK"} <= issues
    assert r["verdict"] == "FAIL"
    ok = VR.review_all({"total": 10.0, "segments": [
        {"kind": "clip", "label": "s", "span": [0, 2],
         "motion": "push"}]}, 5, ["a.mp4"], mean_db=-18.0, peak_db=-3.0)
    assert ok["verdict"] == "PASS"
