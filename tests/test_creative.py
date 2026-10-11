"""Creative layer tests (quality model, director shots, motion, review)."""
import pytest

from engine.autonomy.director import classify_voice_mode, plan_shots
from engine.creative import motion, quality
from engine.creative.review import review_production
from engine.review.repair import route_creative


def _pool():
    return [
        {"file": "a.mp4", "w": 3840, "h": 2160, "dur": 20.0,
         "tags": ["code", "software"]},
        {"file": "b.mp4", "w": 1280, "h": 720, "dur": 10.0,
         "tags": ["laptop", "russian ui"], "foreign_ui": True},
        {"file": "c.mp4", "w": 1920, "h": 1080, "dur": 30.0,
         "tags": ["server", "data"]},
    ]


def test_voice_mode_explicit():
    assert classify_voice_mode(False)["voice_mode"] == "TEXT_DRIVEN"
    assert classify_voice_mode(True, ("ar",))["voice_mode"] == "NARRATED"
    assert classify_voice_mode(True, ())["voice_mode"] == "TEXT_DRIVEN"


def test_shot_planning():
    scenes = [{"id": "S1", "span": [0, 9.5], "text": "hook here?",
               "visual": "montage", "need": "code server"}]
    shots = plan_shots(scenes, _pool())
    assert len(shots) >= 2
    assert shots[0]["asset"] == "a.mp4"  # tag relevance wins
    assert all(s["caption_behavior"] == "headline" for s in shots)
    # foreign UI vetoed despite resolution
    bad = plan_shots([{"id": "S9", "span": [0, 12], "text": "x",
                       "visual": "v", "need": "laptop russian ui"}],
                     _pool())
    assert all(s["asset"] != "b.mp4" for s in bad)
    assert plan_shots(scenes, _pool()) == plan_shots(scenes, _pool())


def test_motion_builders():
    assert "\\fad" in motion.fade()
    assert "\\move" in motion.rise(540, 900)
    assert "\\move" in motion.slide_in(540, 900, "right")
    assert motion.check_headline("one two three")["ok"] is True
    assert motion.check_headline("one " * 10)["ok"] is False
    assert motion.dialogue(1.0, 2.0, "Body", "hi").startswith("Dialogue:")


def test_quality_model():
    tl = {"total": 76.0,
          "segments": [{"kind": "card", "label": "title-card", "len": 2.5},
                       {"kind": "clip", "span": [2.5, 4.0]},
                       {"kind": "clip", "span": [4.0, 5.5]},
                       {"kind": "clip", "span": [5.5, 7.5]}],
          "motion_events": 8, "music_gains": [0.0, -1.5, 0.0]}
    script = {"scenes": [{"id": "S1", "span": [0, 9.5],
                          "text": "hook here?"},
                         {"id": "S2", "span": [9.5, 22.5], "text": "body"}],
              "body_cues": ["short line", "another short one"],
              "hierarchy_ok": True}
    assets = {"used": [{"file": "a.mp4", "w": 3840, "h": 2160}],
              "music": {"file": "m.mp3"}}
    q = quality.evaluate(tl, script, assets)
    assert set(q) == set(quality.CRITERIA)
    assert q["hook_strength"]["verdict"] == "PASS"
    assert q["caption_design"]["verdict"] == "PASS"
    assert q["audio_structure"]["verdict"] == "PASS"
    # overload case
    script2 = dict(script, body_cues=[" ".join(["w"] * 40)])
    assert quality.evaluate(tl, script2, assets)["caption_design"]["verdict"] \
        in ("REVIEW", "FAIL")


def test_creative_review_and_routing(tmp_path):
    tl = {"segments": [{"kind": "card", "label": "title-card", "len": 2.5},
                       {"kind": "clip", "span": [2.5, 5]}],
          "scenes": [{"id": "S1", "span": [0, 20], "text": "x"}],
          "motion_events": 0, "music_gains": [0.0],
          "script_words": 100, "hook_text": "plain statement"}
    ass = ("[Script Info]\n[Events]\n"
           "Dialogue: 0,0:00:01.00,0:00:19.00,Body," + "w " * 70 + "\n")
    rep = review_production(str(tmp_path / "none.mp4"), tl, ass,
                            {"used": [], "music": None})
    assert rep["verdict"] == "FAIL"  # single long clip + overload + weak hook
    routed = route_creative(rep)
    routes = {r["route"] for r in routed}
    assert "WEAK_SHOT_SEQUENCE" in routes
    assert "CAPTION_OVERLOAD" in routes
    assert all(r["subsystem"] for r in routed)


def test_gain_audio(tmp_path):
    import shutil
    from engine.core.media import probe
    from engine.rendering.ffmpeg import gain_audio
    src = tmp_path / "t.wav"
    shutil.copy("tests/fixtures/tone_5s.wav", src)
    out = tmp_path / "g.wav"
    gain_audio(src, out, gain_db=-6.0)
    assert abs(probe(out).duration - probe(src).duration) < 0.15
    import pytest as _p
    with _p.raises(ValueError):
        gain_audio(src, tmp_path / "x.wav", gain_db=99)
