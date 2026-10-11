"""Phase 13 B-roll tests — real renders with a local asset (no downloads)."""
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests" / "fixtures"
SRC = str(FIX / "tone_5s.mp4")
BROLL = str(FIX / "broll_test.mp4")

from engine.core.media import probe
from engine.core.project_store import create_project, write_artifact
from engine.rendering.execution import RenderError
from engine.rendering.plan_execute import compose_timeline, render_plan_for_project


@pytest.fixture(scope="module", autouse=True)
def fixtures():
    import shutil
    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg not on PATH")
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "make_test_media.py"), "--all"],
                       capture_output=True, text=True, timeout=600)
    assert r.returncode == 0
    assert (FIX / "broll_test.mp4").is_file()


def _edl(keeps, duration):
    seq, out = 0, []
    for s, e in keeps:
        seq += 1
        out.append({"decision_id": f"edl_{seq:04d}", "start": s, "end": e,
                    "action": "KEEP", "reason": "default", "confidence": 1.0,
                    "scene_id": 0, "word_refs": [], "metadata": {}})
    return {"source": SRC, "duration": duration, "decisions": out,
            "policy": {}, "analysis_refs": {}, "warnings": []}


def _approval(assignments, cuts=()):
    return {"schema_version": "approval-1.0", "plan_hash": "x",
            "source_fingerprint": {}, "analysis_hashes": {},
            "approved_cuts": [{"decision_id": d, "verdict": "approve"} for d in cuts],
            "broll_assignments": list(assignments),
            "jump_approvals": [], "status": "approved", "warnings": [],
            "approved_at": "t", "approver": "test"}


def _assign(s, e, path=None, audio="mute", fit="cover", placement="overlay"):
    from engine.editing.approval import file_pin
    apath = path or BROLL
    return {"opportunity": {"start": s, "end": e, "kind": "opportunity"},
            "start": s, "end": e,
            "asset_id": "broll_test", "asset_path": apath,
            "asset_hash": file_pin(apath)["media_hash"],
            "asset_start": 0.0, "asset_end": e - s, "audio_mode": audio,
            "fit": fit, "placement": placement}


def _proj(tag, edl, approval):
    from engine.editing.approval import approve_plan as _unused  # noqa (surface)
    p = create_project(SRC)
    for name, payload in ({"audio_analysis.json": {"silence": []},
                           "transcript.json": {"segments": []},
                           "scenes.json": {"scenes": [{"scene_id": 0, "start": 0.0,
                                                        "end": edl["duration"]}]},
                           "media_info.json": {"video_codec": "h264",
                                               "duration": edl["duration"]}}).items():
        write_artifact(p.id, "analysis", name, payload)
    write_artifact(p.id, "edit", "edit_decision.json", edl)
    write_artifact(p.id, "editing", "editor_plan.json",
                   {"schema_version": "editor-plan-1.0", "project": p.id,
                    "source": SRC, "duration": edl["duration"],
                    "editing_style": {"name": "general"}})
    # Bypass approve_plan (already covered): write the approval snapshot directly.
    import json
    from engine.editing.approval import plan_hash, source_fingerprint
    from engine.core.project_store import project_dir
    full = dict(approval, plan_hash=plan_hash(
        json.loads((project_dir(p.id) / "editing" / "editor_plan.json").read_text())),
        source_fingerprint=source_fingerprint(SRC))
    write_artifact(p.id, "editing", "approved_edit_plan.json", full)
    return p


def test_broll_overlay_render_muted(tmp_path):
    p = _proj("t", _edl([(0, 5)], 5.0),
              _approval([_assign(1, 3)]))
    res = render_plan_for_project(p.id, out_name="broll_ov.mp4")
    m = res["manifest"]
    assert m["status"] == "completed" and m["qc"]["verdict"] == "pass"
    info = probe(res["output"])
    assert info.duration == pytest.approx(5.0, abs=0.4)
    assert (info.width, info.height) == (640, 360)  # aspect preserved
    assert info.audio_codec == "aac"  # base dialogue intact (muted overlay)
    assert any(c["name"].startswith("broll_placed_") and c["passed"]
               for c in m["qc"]["checks"])


def test_broll_replace_muted_leaves_silence(tmp_path):
    p = _proj("t", _edl([(0, 5)], 5.0),
              _approval([_assign(1, 3, placement="replace")]))
    res = render_plan_for_project(p.id, out_name="broll_rp.mp4")
    assert res["manifest"]["qc"]["verdict"] == "pass"
    assert probe(res["output"]).duration == pytest.approx(5.0, abs=0.4)


def test_broll_original_audio(tmp_path):
    p = _proj("t", _edl([(0, 5)], 5.0),
              _approval([_assign(1, 3, audio="original", placement="replace")]))
    res = render_plan_for_project(p.id, out_name="broll_orig.mp4")
    assert probe(res["output"]).audio_codec == "aac"
    assert res["manifest"]["qc"]["verdict"] == "pass"


def test_broll_fit_contain_and_crop(tmp_path):
    for fit in ("contain", "crop"):
        p = _proj("t", _edl([(0, 5)], 5.0),
                  _approval([dict(_assign(1, 3), fit=fit)]))
        res = render_plan_for_project(p.id, out_name=f"broll_{fit}.mp4")
        info = probe(res["output"])
        assert (info.width, info.height) == (640, 360)  # never distorted
        assert res["manifest"]["qc"]["verdict"] == "pass"


def test_broll_long_asset_trimmed(tmp_path):
    p = _proj("t", _edl([(0, 5)], 5.0),
              _approval([_assign(0, 2)]))  # 4 s asset, 2 s need
    res = render_plan_for_project(p.id, out_name="broll_long.mp4")
    assert probe(res["output"]).duration == pytest.approx(5.0, abs=0.4)


def test_broll_placement_midpoint_matches_asset():
    from engine.analysis.visual import dhash, hist_corr
    import cv2
    import tempfile
    from engine.rendering.ffmpeg import extract_frame
    p = _proj("t", _edl([(0, 5)], 5.0),
              _approval([_assign(1, 3)]))
    out = render_plan_for_project(p.id, out_name="broll_place.mp4")["output"]
    with tempfile.TemporaryDirectory() as tmp:
        fo, fa = str(Path(tmp) / "o.jpg"), str(Path(tmp) / "a.jpg")
        extract_frame(out, 2.0, fo)
        extract_frame(BROLL, 1.0, fa)
        go = cv2.cvtColor(cv2.imread(fo), cv2.COLOR_BGR2GRAY)
        ga = cv2.cvtColor(cv2.imread(fa), cv2.COLOR_BGR2GRAY)
        import engine.analysis.visual as _v
        assert _v.hamming(_v.dhash(go), _v.dhash(ga)) <= 10
        assert _v.hist_corr(go, ga) >= 0.7  # same testsrc family
