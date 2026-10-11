"""Punch-in reframing tests (planner pure + gateway execution on fixture)."""
import json
from pathlib import Path

import pytest

from engine.core.project_store import create_project, project_dir, write_artifact
from engine.editing import punch as P
from engine.editing.punch import PunchError

FIX = Path(__file__).resolve().parents[1] / "tests" / "fixtures"


def _tr(*triples):
    # engine transcript schema uses "word" (caption refs use "text")
    words = [{"word": t, "start": s, "end": e, "probability": 0.9}
             for t, s, e in triples]
    return {"language": "ar",
            "segments": [{"id": 0, "start": triples[0][1],
                          "end": triples[-1][2], "text": "x", "words": words}]}


def test_plan_spacing_and_scales():
    tr = _tr(("one two three four.", 0.0, 4.0),
             ("next phrase here now.", 5.0, 9.5),
             ("short.", 20.0, 21.0),
             ("another long phrase for emphasis here.", 30.0, 44.0))
    plan = P.plan_punch_ins(tr, 60.0)
    starts = [r.start for r in plan.ranges]
    assert starts == sorted(starts)
    assert all(b - a >= 8.0 for a, b in zip(starts, starts[1:]))
    by_start = {r.start: r.scale for r in plan.ranges}
    assert by_start[30.0] == 1.12  # 14 s phrase -> emphasis
    assert by_start[5.0] == 1.08
    assert 0.0 not in by_start  # too close to the 5 s phrase (spacing)
    assert 20.0 not in by_start  # 1 s phrase ineligible
    assert all(r.end - r.start <= 20.0 for r in plan.ranges)  # capped


def test_plan_deterministic_and_validated():
    tr = _tr(("hello world.", 1.0, 3.0), ("bye now.", 10.0, 14.0))
    a = P.plan_punch_ins(tr, 60.0, focus=(0.47, 0.40))
    b = P.plan_punch_ins(tr, 60.0, focus=(0.47, 0.40))
    assert a == b
    assert (a.focus_x, a.focus_y) == (0.47, 0.40)
    with pytest.raises(PunchError):
        P.plan_punch_ins(tr, 60.0, focus=(1.5, 0.5))
    with pytest.raises(PunchError):
        P.plan_punch_ins(tr, 0)


def test_map_punches_to_output():
    punches = [{"start": 10.0, "end": 20.0, "scale": 1.08},
               {"start": 48.0, "end": 52.0, "scale": 1.08},
               {"start": 90.0, "end": 95.0, "scale": 1.08}]
    keeps = [(0.0, 50.0, 0.0, 50.0), (55.0, 100.0, 50.0, 95.0)]
    mapped, dropped = P.map_punches_to_output(punches, keeps)
    assert [(m["start"], m["end"]) for m in mapped] == \
        [(10.0, 20.0), (48.0, 50.0), (85.0, 90.0)]
    assert dropped == []
    # straddling punch shrinks to largest surviving span ([55,58] -> [50,53])
    m2, d2 = P.map_punches_to_output(
        [{"start": 48.0, "end": 58.0, "scale": 1.08}], keeps)
    assert (m2[0]["start"], m2[0]["end"]) == (50.0, 53.0)
    assert not d2
    m3, d3 = P.map_punches_to_output(
        [{"start": 54.9, "end": 55.05, "scale": 1.08}], keeps)
    assert not m3 and d3  # fully removed


def test_filter_math():
    vf = P.punch_filter(720, 1280, 1.08, 0.5, 0.5)
    assert vf.startswith("crop=")
    nums = [int(x) for x in
            vf.split(",")[0].split("=")[1].split(":")[:2]]
    assert all(n % 2 == 0 for n in nums)  # even for h264
    assert f"scale=720:1280" in vf
    vf2 = P.punch_filter(720, 1280, 1.12, 0.0, 0.0)  # clamped, no crash
    assert "crop=" in vf2
    with pytest.raises(PunchError):
        P.punch_filter(720, 1280, 0.9, 0.5, 0.5)


def test_apply_preserves_dims_and_duration():
    from engine.core.media import probe
    src = str(FIX / "tone_5s.mp4")
    src_dur = probe(src).duration
    dst = Path("C:/Users/NOURSO~1/AppData/Local/Temp/opencode/punch_t.mp4")
    if dst.is_file():
        dst.unlink()
    punches = [{"start": 0.5, "end": 2.0, "scale": 1.1, "cx": 0.5, "cy": 0.5}]
    P.apply_punch_ins(src, punches, dst, width=640, height=360,
                      duration=src_dur, encoder="libx264")
    info = probe(dst)
    assert (info.width, info.height) == (640, 360)
    assert abs(info.duration - src_dur) < 0.3
    dst.unlink()


def _count_frames(path):
    import json as _json
    import subprocess
    from engine.rendering.ffmpeg import which_ffmpeg
    exe = which_ffmpeg() or "ffmpeg"
    raw = subprocess.run(
        [exe.replace("ffmpeg.exe", "ffprobe.exe"), "-v", "quiet",
         "-select_streams", "v:0", "-count_frames",
         "-show_entries", "stream=nb_read_frames", "-of", "json", str(path)],
        capture_output=True, text=True, timeout=120)
    return int(_json.loads(raw.stdout)["streams"][0]["nb_read_frames"])


def test_assembly_preserves_every_frame():
    """Regression: 21-part assembly must not drop frames (QSV concat
    re-encode dropped ~2%; copy-concat is exact)."""
    from engine.core.media import probe
    src = str(FIX / "tone_5s.mp4")
    src_dur = probe(src).duration
    punches = [{"start": 0.5, "end": 2.0, "scale": 1.1, "cx": 0.5, "cy": 0.5},
               {"start": 3.0, "end": 4.0, "scale": 1.12, "cx": 0.5, "cy": 0.5}]
    for enc in ("libx264", "h264_qsv"):
        dst = Path("C:/Users/NOURSO~1/AppData/Local/Temp/opencode/"
                   f"punch_asm_{enc}.mp4")
        if dst.is_file():
            dst.unlink()
        try:
            P.apply_punch_ins(src, punches, dst, width=640, height=360,
                              duration=src_dur, encoder=enc)
        except Exception as exc:
            if enc == "h264_qsv":
                pytest.skip(f"qsv unavailable: {exc}")
            raise
        assert _count_frames(dst) == _count_frames(src)
        dst.unlink()


def test_approval_roundtrip_and_drift():
    p = create_project(str(FIX / "tone_5s.mp4"))
    write_artifact(p.id, "analysis", "transcript.json",
                   _tr(("hello world.", 0.5, 2.0)))
    write_artifact(p.id, "edit", "edit_decision.json",
                   {"decisions": [{"decision_id": "k", "action": "KEEP",
                                    "start": 0, "end": 5, "reason": "t"}],
                    "duration": 5.0})
    res = P.approve_punch_plan(p.id, focus=(0.5, 0.42))
    assert res["approval"]["focus_x"] == 0.5
    assert P.validate_punch_approval(p.id)["approval"]
    plan_path = project_dir(p.id) / "editing" / "punch_plan.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    plan["ranges"].append({"start": 1, "end": 2, "scale": 1.1,
                           "reason": "x", "confidence": 0.5})
    plan_path.write_text(json.dumps(plan), encoding="utf-8")
    with pytest.raises(PunchError):
        P.validate_punch_approval(p.id)
