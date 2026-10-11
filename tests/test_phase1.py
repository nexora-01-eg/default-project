"""Unit tests — Phase 1 (run with `pytest` after Phase 2 installs Python deps)."""
import json


def test_models_roundtrip():
    from engine.core.models import Project
    p = Project(id="project_test", input_path="input/x.mp4")
    d = p.to_dict()
    assert Project.from_dict(d).id == "project_test"


def test_config_layering(tmp_path):
    from engine.core import config as cfg
    resolved = cfg.resolve("youtube", "youtube_1080p", {"silence_db": -40})
    assert resolved["silence_db"] == -40
    assert resolved["width"] == 1920


def test_cache_key_stable(tmp_path):
    from engine.core.pipeline import cache_key
    f = tmp_path / "a.bin"
    f.write_bytes(b"hello world, this is a test payload" * 100)
    k1 = cache_key(f, "inspect", {"a": 1})
    k2 = cache_key(f, "inspect", {"a": 1})
    assert k1 == k2
    assert cache_key(f, "inspect", {"a": 2}) != k1


def test_probe_missing_file():
    import pytest
    from engine.core.media import MediaProbeError, probe
    with pytest.raises(MediaProbeError):
        probe("definitely_not_here_12345.mp4")


def test_cli_doctor_runs(capsys):
    from engine.cli import main
    rc = main(["doctor"])
    assert rc in (0, 3)  # 0 = ffmpeg present, 3 = not yet installed


def test_run_edit_not_implemented():
    import pytest
    from engine.core.orchestrator import run_edit
    with pytest.raises(NotImplementedError):
        run_edit()


def test_probe_non_ascii_path(tmp_path):
    """Regression: probe must survive Arabic/space paths (UTF-8 pipes)."""
    import shutil
    from engine.core.media import probe
    src = shutil.which("ffmpeg")  # only proves resolver below; real check:
    import pathlib
    fix = pathlib.Path("tests/fixtures/tone_5s.mp4")
    if not fix.is_file():
        import pytest as _p
        _p.skip("fixture absent")
    dst = tmp_path / "مجلد test" / "tone_5s.mp4"
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(fix, dst)
    info = probe(dst)
    assert info.duration > 0 and info.audio_codec != ""
