"""Phase 15 visual-caption tests — deterministic units + real renders.

Pure-logic tests use hand-built plans (no ffmpeg). Adapter/face paths use
injected fakes (labeled, never claimed as real detection). Render tests use
real fixtures through the full chain.
"""
import json
import subprocess
import sys
import time
from dataclasses import asdict
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests" / "fixtures"

from engine.core.models import (
    CaptionEmphasis,
    CaptionPlacement,
    CaptionVisualContext,
    VisualCaptionPlan,
)
from engine.subtitles import visual_captions as vc
from engine.subtitles.formats import resolve_style, write_ass_visual


@pytest.fixture(scope="module", autouse=True)
def fixtures():
    import shutil
    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg not on PATH")
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "make_test_media.py"), "--all"],
                       capture_output=True, text=True, timeout=600)
    assert r.returncode == 0
    assert (FIX / "speech_video.mp4").is_file()


def _cfg(**over):
    base = vc.resolve_visual_caption_config(None)
    base.update(over)
    return base


def _cue(cid="cue_0001", s=0.0, e=2.0, text="hello world", lang="en"):
    toks = text.split(" ")
    step = (e - s) / max(len(toks), 1)
    words = [{"word_id": f"s0w{i}", "text": t, "start": round(s + i * step, 3),
              "end": round(s + (i + 1) * step, 3), "probability": 0.9,
              "segment_id": 0} for i, t in enumerate(toks)]
    return {"cue_id": cid, "start": s, "end": e, "text": text,
            "lines": [text], "word_refs": words, "language": lang,
            "confidence": 0.9, "style": "default", "scene_id": 0}


def _plan(cues, style="default", lang="en"):
    return {"schema_version": "caption-plan-1.0", "source": "t",
            "transcript_hash": "h", "cues": cues, "cue_count": len(cues),
            "style": style, "language": lang, "warnings": [],
            "expected_duration": 10.0,
            "config": {"caption_font_family": "Arial"}}


# ---------- 1. model serialization ----------

def test_model_serialization():
    p = VisualCaptionPlan(
        placements=[CaptionPlacement(cue_id="c1", position="top")],
        emphasis=[CaptionEmphasis(cue_id="c1", emphasis_type="keyword")],
        contexts=[CaptionVisualContext(cue_id="c1", brightness=10.0)])
    d = asdict(p)
    assert d["placements"][0]["anchor"] == "top-center"
    assert d["emphasis"][0]["emphasis_type"] == "keyword"
    assert json.loads(json.dumps(d))["schema_version"] == "visual-caption-plan-1.0"


def test_config_defaults_and_validation():
    cfg = vc.resolve_visual_caption_config(None)
    assert cfg["visual_caption_good_thr"] == 150.0
    assert cfg["caption_position"] == "bottom"
    with pytest.raises(vc.VisualCaptionError):
        vc.resolve_visual_caption_config({"caption_position": "sideways"})
    with pytest.raises(vc.VisualCaptionError):
        vc.resolve_visual_caption_config({"visual_caption_good_thr": "xx"})


# ---------- 2-3. deterministic placement + safe area ----------

def test_placement_deterministic_dark_frame():
    style = dict(resolve_style("default"), _name="default")
    plan, _ = vc.build_visual_plan(
        _plan([_cue()]), None, str(FIX / "static_3s.mp4"), 3.0, 640, 360,
        style, _cfg())
    plan2, _ = vc.build_visual_plan(
        _plan([_cue()]), None, str(FIX / "static_3s.mp4"), 3.0, 640, 360,
        style, _cfg())
    assert asdict(plan) == asdict(plan2)  # deterministic
    assert plan.placements[0].position == "bottom"  # style default kept
    assert plan.placements[0].reason == "style_default"
    assert plan.contexts[0].brightness < 30.0  # black frame measured


def test_build_never_mutates_inputs():
    """Regression: build_visual_plan once stamped cue['_visual'] onto the
    caller's dicts, poisoning the caption-plan hash stored next to the
    pristine file (approval drift on identical content)."""
    import copy
    from engine.subtitles.visual_captions import build_visual_plan
    style = dict(resolve_style("default"), _name="default")
    cues = [_cue_dict("cue_0001", 0.5, 2.0, "hello World")]
    plan_in = {"schema_version": "caption-plan-1.0", "source": "t",
               "transcript_hash": "h", "cues": cues, "cue_count": 1,
               "style": "default", "language": "en", "warnings": [],
               "expected_duration": 5.0, "config": {}}
    snapshot = copy.deepcopy(plan_in)
    build_visual_plan(plan_in, None, str(FIX / "tone_5s.mp4"), 5.0, 640, 360,
                      style, _cfg())
    assert plan_in == snapshot  # inputs untouched


def test_safe_area_math():
    sa = vc.safe_area(640, 360, _cfg())
    # margins scale with height (1080p basis): 40*1/3/640, 24*1/3/360
    assert sa == {"x_min": 0.0208, "x_max": 0.9792, "y_min": 0.0222, "y_max": 0.9778}
    assert sa["x_min"] >= 0 and sa["y_min"] >= 0  # inside frame, off edges


# ---------- 4-5. brightness/contrast + classification ----------

def test_band_brightness_black_vs_white():
    dark = vc.sample_bands(str(FIX / "static_3s.mp4"), 1.0, 3.0, 640, 360)
    bright = vc.sample_bands(str(FIX / "tone_5s.mp4"), 1.0, 5.0, 640, 360)
    assert dark["bottom"]["mean"] < 30.0
    assert bright["bottom"]["mean"] > 30.0
    assert set(dark) == {"top", "center", "bottom"}
    assert vc.classify_contrast(10.0, _cfg()) == "GOOD_CONTRAST"
    assert vc.classify_contrast(170.0, _cfg()) == "CAUTION"
    assert vc.classify_contrast(230.0, _cfg()) == "POOR_CONTRAST"


# ---------- 6. style adaptation ----------

def test_style_adaptation_escalation():
    style = resolve_style("clean")  # outline 1, no box
    adapted, record = vc.adapt_style(style, "POOR_CONTRAST", _cfg())
    assert adapted == {"outline": 2} and record["adapted"] is True
    assert record["confidence"] == 0.55 and "reason" in record
    maxed = dict(style, outline=3, box=True, shadow=1)
    adapted2, record2 = vc.adapt_style(maxed, "POOR_CONTRAST", _cfg())
    assert adapted2 == {} and record2["adapted"] is False  # ceiling honored
    adapted3, _ = vc.adapt_style(style, "GOOD_CONTRAST", _cfg())
    assert adapted3 == {}  # good contrast: no change, ever


# ---------- 7-8. no-face fallback + fake adapter ----------

def test_no_face_fallback():
    style = dict(resolve_style("default"), _name="default")
    plan, _ = vc.build_visual_plan(
        _plan([_cue()]), None, str(FIX / "static_3s.mp4"), 3.0, 640, 360,
        style, _cfg())
    assert plan.contexts[0].face_available is False
    assert plan.contexts[0].face_regions == []


def test_fake_face_adapter_moves_placement():
    style = dict(resolve_style("default"), _name="default")

    def fake_faces(t):
        return [{"x": 100, "y": 250, "w": 200, "h": 100}]  # bottom band

    plan, _ = vc.build_visual_plan(
        _plan([_cue()]), None, str(FIX / "static_3s.mp4"), 3.0, 640, 360,
        style, _cfg(), face_regions_fn=fake_faces)
    assert plan.contexts[0].face_available is True
    assert plan.placements[0].position in ("top", "center")  # moved off faces
    assert plan.placements[0].reason == "face_avoidance"


# ---------- 9-12. word emphasis ----------

def _words_cue():
    return _cue(text="hello World 123 um")


def test_word_emphasis_selection():
    from engine.subtitles.visual_captions import plan_emphasis
    # 7 words -> 30% cap allows 2 emphases.
    cue = {"cue_id": "c1",
           "word_refs": [
               {"word_id": "s0w0", "text": "hello", "start": 0.0, "end": 0.4,
                "probability": 0.9},
               {"word_id": "s0w1", "text": "World", "start": 0.5, "end": 0.9,
                "probability": 0.9},
               {"word_id": "s0w2", "text": "and", "start": 1.0, "end": 1.4,
                "probability": 0.9},
               {"word_id": "s0w3", "text": "123", "start": 1.5, "end": 1.9,
                "probability": 0.9},
               {"word_id": "s0w4", "text": "today", "start": 2.0, "end": 2.4,
                "probability": 0.9},
               {"word_id": "s0w5", "text": "um", "start": 2.5, "end": 2.9,
                "probability": 0.9},
               {"word_id": "s0w6", "text": "ok", "start": 3.0, "end": 3.4,
                "probability": 0.9}]}
    e = plan_emphasis(cue, "en", _cfg())
    got = {r["word"] for r in e.word_refs}
    assert got == {"World", "123"}  # number + capitalized; filler rejected
    assert e.emphasis_type in ("keyword", "important_words")


def test_low_confidence_and_punct_rejected():
    from engine.subtitles.visual_captions import plan_emphasis
    cue = {"cue_id": "c1",
           "word_refs": [{"word_id": "s0w0", "text": "Maybe", "start": 0.0,
                          "end": 0.5, "probability": 0.2},
                         {"word_id": "s0w1", "text": "...", "start": 0.5,
                          "end": 1.0, "probability": 0.99}]}
    e = plan_emphasis(cue, "en", _cfg())
    assert e.emphasis_type == "none"  # low-conf + punct-only rejected


def test_emphasis_timing_from_transcript():
    from engine.subtitles.visual_captions import plan_emphasis
    cue = {"cue_id": "c1",
           "word_refs": [{"word_id": "s0w0", "text": "call", "start": 1.0,
                          "end": 1.4, "probability": 0.9},
                         {"word_id": "s0w1", "text": "5551234", "start": 1.4,
                          "end": 2.2, "probability": 0.9}]}
    e = plan_emphasis(cue, "en", _cfg())
    assert e.word_refs[0]["start"] == 1.4 and e.word_refs[0]["end"] == 2.2


# ---------- 13-14. Arabic + mixed emphasis ----------

AR_CUE = _cue(cid="c-ar", s=0.0, e=2.5, text="اتصل على 123 الآن", lang="ar")


def test_arabic_emphasis_numbers_only():
    from engine.subtitles.visual_captions import plan_emphasis
    cue = {"cue_id": "c-ar",
           "word_refs": [{"word_id": "s0w0", "text": "اتصل", "start": 0.0,
                          "end": 0.6, "probability": 0.9},
                         {"word_id": "s0w1", "text": "123", "start": 0.6,
                          "end": 1.2, "probability": 0.9},
                         {"word_id": "s0w2", "text": "الآن", "start": 1.2,
                          "end": 2.0, "probability": 0.9}]}
    e = plan_emphasis(cue, "ar", _cfg())
    assert [r["word"] for r in e.word_refs] == ["123"]
    assert e.emphasis_type == "keyword"


def test_mixed_script_integrity():
    style = dict(resolve_style("default"), _name="default")
    cue = _cue(cid="c-mx", s=0.0, e=3.0, text="أهلا Windows الجديد", lang="ar")
    plan, _ = vc.build_visual_plan(
        _plan([cue], lang="ar"), None, str(FIX / "static_3s.mp4"), 3.0,
        640, 360, style, _cfg())
    assert plan.placements[0].position == "bottom"
    assert "Windows" in cue["text"]  # source text untouched


# ---------- 15-16. scene-aware + conflicts ----------

def test_scene_crossing_conflict():
    style = dict(resolve_style("default"), _name="default")
    scenes = {"duration": 6.0, "scenes": [
        {"scene_id": 0, "start": 0.0, "end": 3.0},
        {"scene_id": 1, "start": 3.0, "end": 6.0}]}
    # Build via project-less direct call using scenes payload shape.
    plan, _ = vc.build_visual_plan(
        _plan([_cue(cid="c-x", s=1.0, e=5.0, text="spanning cue here now")]),
        {"scene_summaries": scenes["scenes"]}, str(FIX / "static_3s.mp4"),
        3.0, 640, 360, style, _cfg())
    kinds = [c["kind"] for c in plan.conflicts]
    assert "scene_crossing" in kinds
    assert plan.placements[0].position == "bottom"  # single placement kept


def test_busy_and_long_conflicts():
    style = dict(resolve_style("default"), _name="default")
    cue = _cue(cid="c-b", s=0.0, e=7.0, text="a long lingering caption line here")
    plan, _ = vc.build_visual_plan(
        _plan([cue]), None, str(FIX / "tone_5s.mp4"), 5.0, 640, 360,
        style, _cfg())
    kinds = [c["kind"] for c in plan.conflicts]
    assert "long_cue" in kinds  # > 6 s recorded, never split


# ---------- 17-19. project approval + dry-run ----------

def _project_with_caption_plan(tag, cues, style="default", lang="en",
                               source=None, visual=None):
    import time
    from engine.core.media import probe
    from engine.core.project_store import create_project, write_artifact
    src = source or str(FIX / "tone_5s.mp4")
    p = create_project(f"{tag}_{time.time_ns()}.mp4")
    info = probe(src)
    from dataclasses import asdict as _asdict
    write_artifact(p.id, "analysis", "media_info.json",
                   {"path": src, "video_codec": info.video_codec or "h264",
                    "duration": info.duration, "width": info.width or 640,
                    "height": info.height or 360, "fps": info.fps or 30.0})
    write_artifact(p.id, "captions", "caption_plan.json",
                   {"schema_version": "caption-plan-1.0", "source": src,
                    "transcript_hash": "h", "cues": cues,
                    "cue_count": len(cues), "style": style, "language": lang,
                    "warnings": [], "expected_duration": info.duration,
                    "config": {"caption_font_family": "Arial"}})
    if visual is not None:
        write_artifact(p.id, "visual", "visual_analysis.json", visual)
    from engine.core.project_store import load_project, save_project
    proj = load_project(p.id)
    proj.input_path = src
    save_project(proj)
    return p


def _cue_dict(cid="cue_0001", s=0.5, e=2.0, text="hello World"):
    toks = text.split(" ")
    step = (e - s) / max(len(toks), 1)
    words = [{"word_id": f"s0w{i}", "text": t,
              "start": round(s + i * step, 3), "end": round(s + (i + 1) * step, 3),
              "probability": 0.9, "segment_id": 0} for i, t in enumerate(toks)]
    return {"cue_id": cid, "start": s, "end": e, "text": text, "lines": [text],
            "word_refs": words, "language": "en", "confidence": 0.9,
            "style": "default", "scene_id": 0}


def test_approval_and_invalidation(tmp_path):
    from engine.subtitles.visual_captions import (
        approve_caption_visual,
        caption_visual_for_project,
        validate_visual_approval,
    )
    unique = tmp_path / "vis_appr_src.mp4"
    unique.write_bytes((FIX / "tone_5s.mp4").read_bytes())
    p = _project_with_caption_plan("t", [_cue_dict()], source=str(unique))
    res = caption_visual_for_project(p.id)
    assert res["cached"] is False
    assert (ROOT / "projects" / p.id / "captions" / "visual_caption_plan.json").is_file()
    appr = approve_caption_visual(p.id)
    assert appr["approval"]["schema_version"] == "visual-caption-approval-1.0"
    assert validate_visual_approval(p.id)["approval"] == appr["approval"]
    # Drift the visual plan -> approval invalid.
    import json
    vp = ROOT / "projects" / p.id / "captions" / "visual_caption_plan.json"
    payload = json.loads(vp.read_text(encoding="utf-8"))
    payload["placements"].append({"cue_id": "zz", "position": "top"})
    vp.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(Exception, match="re-approve"):
        validate_visual_approval(p.id)


def test_dry_run_writes_nothing():
    from engine.subtitles.visual_captions import caption_visual_for_project
    p = _project_with_caption_plan("t", [_cue_dict()])
    res = caption_visual_for_project(p.id, dry_run=True)
    assert res.get("dry_run") is True
    assert not (ROOT / "projects" / p.id / "captions" / "visual_caption_plan.json").exists()
    assert res["plan"]["placements"]


def test_cache_hit_and_invalidation(tmp_path):
    from engine.subtitles.visual_captions import caption_visual_for_project
    unique = tmp_path / "vis_cache_src.mp4"
    unique.write_bytes((FIX / "tone_5s.mp4").read_bytes())  # unique key material
    p = _project_with_caption_plan("t", [_cue_dict()], source=str(unique))
    first = caption_visual_for_project(p.id)
    assert first["cached"] is False
    second = caption_visual_for_project(p.id)
    assert second["cached"] is True
    third = caption_visual_for_project(p.id, style_name="social")
    assert third["cached"] is False  # style change invalidates


def test_cli_visual_and_approve(capsys):
    from engine.cli import main
    p = _project_with_caption_plan("t", [_cue_dict()])
    assert main(["caption-visual", p.id]) == 0
    assert "placed" in capsys.readouterr().out
    assert main(["caption-visual", p.id, "--dry-run"]) == 0
    assert "DRY RUN" in capsys.readouterr().out
    assert main(["approve-caption-visual", p.id]) == 0
    assert "approved_visual_caption_plan" in capsys.readouterr().out
    assert main(["caption-visual", "project_nope_123"]) == 2
    assert main(["approve-caption-visual", "project_nope_123"]) == 2


# ---------- 22. QC unit checks ----------

def test_visual_qc_invalid_geometry_fails():
    from engine.subtitles.render import _visual_qc_checks
    state = {"active": True, "placements": {"c1": "sideways"},
             "emphasis": {}}
    cues = [{"cue_id": "c1", "start": 0.0, "end": 1.0, "text": "hi",
             "word_refs": [{"text": "hi", "start": 0.0, "end": 0.5}]}]
    checks = _visual_qc_checks(cues, state)
    assert any(c["name"] == "visual_placement_c1" and not c["passed"]
               for c in checks)
    state_ok = {"active": True, "placements": {"c1": "top"}, "emphasis": {}}
    assert all(c["passed"] for c in _visual_qc_checks(cues, state_ok))
    assert _visual_qc_checks(cues, {"active": False}) == []


# ---------- real fixtures + end-to-end ----------

def _sapi_wav():
    import shutil
    wav = FIX / "speech_sapi.wav"
    if wav.is_file():
        return wav
    ps = ("Add-Type -AssemblyName System.Speech; "
          "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
          "$s.SelectVoice('Microsoft Zira Desktop'); $s.Rate = -1; "
          f"$s.SetOutputToWaveFile('{wav}'); $s.Speak('Hello World 123. "
          "This is a visual caption test.'); $s.Dispose()")
    import subprocess as _sp
    import sys as _sys
    r = _sp.run(["powershell", "-NoProfile", "-Command", ps],
                capture_output=True, text=True, timeout=300)
    if r.returncode != 0 or not wav.is_file():
        pytest.skip("SAPI TTS unavailable")
    return wav


@pytest.fixture(scope="module")
def av_chain():
    """Full real chain on speech+video (module-scoped, built once)."""
    import shutil
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        pytest.skip("ffmpeg/ffprobe not on PATH")
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "make_test_media.py"),
                        "--all"], capture_output=True, text=True, timeout=600)
    assert r.returncode == 0
    wav = _sapi_wav()
    static_mp4 = FIX / "speech_static.mp4"
    if not static_mp4.is_file():
        from engine.core.media import probe
        dur = probe(wav).duration
        r = subprocess.run(
            [shutil.which("ffmpeg"), "-y",
             "-f", "lavfi", "-i", f"color=c=black:size=640x360:rate=30:duration={dur:.2f}",
             "-i", str(wav), "-c:v", "libx264", "-pix_fmt", "yuv420p",
             "-c:a", "aac", "-shortest", str(static_mp4)],
            capture_output=True, text=True, timeout=300)
        assert r.returncode == 0, f"static fixture failed: {r.stderr[-500:]}"
    from engine.analysis.scenes import detect_scenes_project
    from engine.analysis.speech import transcribe_to_project
    from engine.analysis.visual import run_visual_for_project
    from engine.core.media import probe as _probe
    from engine.core.orchestrator import run_inspect
    from engine.editing.decisions import build_edl_for_project
    from engine.editing.brain import run_editor_brain_for_project
    from engine.editing.approval import approve_plan
    from engine.subtitles.captions import approve_captions, caption_plan_for_project
    pid = run_inspect(str(static_mp4))["project"]
    transcribe_to_project(str(static_mp4), project_id=pid, model="tiny")
    detect_scenes_project(str(static_mp4), project_id=pid)
    build_edl_for_project(pid)
    run_editor_brain_for_project(pid)
    approve_plan(pid)
    run_visual_for_project(pid)
    caption_plan_for_project(pid)
    approve_captions(pid, mode="burned_in")
    info = _probe(static_mp4)
    return {"project": pid, "duration": info.duration,
            "width": info.width, "height": info.height}


def test_real_full_chain_visual_render(av_chain):
    from engine.cli import main
    pid = av_chain["project"]
    assert main(["caption-visual", pid]) == 0
    assert main(["approve-caption-visual", pid]) == 0
    assert main(["render-plan", pid, "--out", "capvis_e2e.mp4", "--captions"]) == 0
    renders = ROOT / "projects" / pid / "renders"
    out = renders / "capvis_e2e_captioned.mp4"
    assert out.is_file()
    from engine.core.media import probe
    info = probe(out)
    assert abs(info.duration - av_chain["duration"]) <= 0.5
    assert (info.width, info.height) == (640, 360)
    assert info.audio_codec == "aac"  # burn never touches audio
    m = json.loads((renders / "capvis_e2e_captioned_plan_manifest.json").read_text())
    assert m["caption_qc"]["verdict"] == "pass"
    assert m["visual_approval"] == "valid"
    assert m["visual_placements"] >= 1
    assert any(c["name"].startswith("caption_visible_") and c["passed"]
               for c in m["caption_qc"]["checks"])
    assert any(c["name"].startswith("visual_placement_") and c["passed"]
               for c in m["caption_qc"]["checks"])


def test_comparison_render_isolates_polish(av_chain):
    """Same cues, same timings, different ASS: polish isolated to visuals."""
    import json as _json
    from engine.cli import main
    from engine.subtitles.render import apply_captions
    from engine.core.project_store import project_dir
    from engine.rendering.execution import resolve_render_config
    pid = av_chain["project"]
    assert main(["caption-visual", pid]) == 0
    assert main(["approve-caption-visual", pid]) == 0
    assert main(["render-plan", pid, "--out", "capvis_e2e.mp4", "--captions"]) == 0
    renders = project_dir(pid) / "renders"
    base = sorted(renders.glob("capvis_e2e.mp4"))
    assert base, "base render required"
    # Capture the visual ASS BEFORE re-running (the plain run rewrites it).
    visual_ass = (renders / "capvis_e2e_captioned.ass").read_text(encoding="utf-8")
    # Re-run caption layer with visual approval removed -> standard ASS.
    vp = project_dir(pid) / "captions" / "visual_caption_plan.json"
    ap = project_dir(pid) / "captions" / "approved_visual_caption_plan.json"
    vp_bak, ap_bak = vp.read_bytes(), ap.read_bytes()
    vp.unlink()
    ap.unlink()
    try:
        res = apply_captions(pid, str(base[0]), [(0.0, av_chain["duration"])],
                             resolve_render_config(None), None)
    finally:
        vp.write_bytes(vp_bak)
        ap.write_bytes(ap_bak)
    assert res["visual_approval"] == "absent"  # recorded state, not a warning
    plain_ass = Path(res["files"]["ass"]).read_text(encoding="utf-8")
    assert plain_ass != visual_ass  # polish changed the ASS tracks
    # ...but cue timings identical (same Dialogue start/end stamps).
    def _stamps(text):
        return sorted(l.split(",", 3)[1:3] for l in text.splitlines()
                      if l.startswith("Dialogue:"))
    assert _stamps(plain_ass) == _stamps(visual_ass)


def test_real_arabic_burn():
    """Arabic glyphs through libass with emphasis: burn passes, text intact.

    Self-contained (burns the tone fixture directly): proves real Arabic
    shaping through the verified toolchain, independent of other tests.
    """
    from engine.subtitles.formats import write_ass_visual, resolve_style
    from engine.rendering.ffmpeg import burn_subtitles, extract_frame
    cues = [{"cue_id": "c-ar", "start": 0.5, "end": 2.5,
             "text": "اتصل 123 الآن", "lines": ["اتصل 123 الآن"],
             "word_refs": [{"word_id": "s0w0", "text": "اتصل", "start": 0.5,
                            "end": 1.0, "probability": 0.95},
                           {"word_id": "s0w1", "text": "123", "start": 1.0,
                            "end": 1.7, "probability": 0.95},
                           {"word_id": "s0w2", "text": "الآن", "start": 1.7,
                            "end": 2.5, "probability": 0.95}],
             "language": "ar", "confidence": 0.95, "style": "default",
             "scene_id": 0}]
    ass = write_ass_visual(
        cues, dict(resolve_style("default"), _name="default"), "Arial",
        640, 360, placements={"c-ar": "bottom"},
        emphasis={"c-ar": [{"text": "123", "occurrence": 0, "kind": "keyword"}]},
        adaptations={})
    assert "اتصل" in ass and "الآن" in ass  # source words survive tagging
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        ass_path = Path(tmp) / "ar_probe.ass"
        ass_path.write_text(ass, encoding="utf-8")
        out = Path(tmp) / "ar_probe.mp4"
        burn_subtitles(FIX / "tone_5s.mp4", ass_path, out,
                       fontsdir="C:/Windows/Fonts")
        fo, fb = Path(tmp) / "o.jpg", Path(tmp) / "b.jpg"
        extract_frame(out, 1.5, fo)
        extract_frame(FIX / "tone_5s.mp4", 1.5, fb)
        import cv2
        io = cv2.imread(str(fo)).astype(float)
        ib = cv2.imread(str(fb)).astype(float)
        band = slice(int(io.shape[0] * 0.75), None)
        import numpy as np
        diff = float(np.abs(io[band] - ib[band]).mean())
    assert diff > 2.0  # Arabic caption pixels visibly rendered, not tofu-identical


# ---------- 20-21. ASS rendering with visual features ----------

def test_ass_visual_tags_and_overrides():
    from engine.subtitles.formats import write_ass_visual
    style = dict(resolve_style("default"), _name="default")
    cues = [_cue_dict("cue_0001", 0.5, 2.0, "hello World")]
    out = write_ass_visual(
        cues, style, "Arial", 640, 360,
        placements={"cue_0001": "top"},
        emphasis={"cue_0001": [{"text": "World", "occurrence": 0,
                                "kind": "keyword"}]},
        adaptations={"cue_0001": {"outline": 3}})
    assert "{\\an8}" in out  # top alignment override
    assert "{\\bord3}" in out  # adapted outline rendered
    assert "{\\1c&H0000FFFF&}World{\\1c}" in out  # emphasis tags
    assert "hello" in out  # surrounding text intact


def test_ass_visual_arabic_emphasis_intact():
    from engine.subtitles.formats import write_ass_visual
    style = dict(resolve_style("default"), _name="default")
    cues = [_cue_dict("c-ar", 0.0, 2.0, "اتصل 123 الآن")]
    cues[0]["language"] = "ar"
    out = write_ass_visual(
        cues, style, "Arial", 640, 360,
        placements={}, emphasis={"c-ar": [{"text": "123", "occurrence": 0,
                                           "kind": "keyword"}]},
        adaptations={})
    for token in ("اتصل", "123", "الآن"):
        assert token in out  # all source words survive tagging
    assert "{\\1c&H0000FFFF&}123{\\1c}" in out
