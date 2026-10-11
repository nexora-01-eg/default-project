"""FFmpeg/ffprobe resolution tests (PATH lookup + explicit env override)."""
import os
import shutil
from pathlib import Path

import pytest

from engine.core.media import MediaProbeError, ffprobe_path
from engine.rendering import ffmpeg as F
from engine.rendering.ffmpeg import FfmpegError


def _real_bins():
    """Locate genuine installed binaries (never faked)."""
    ff = shutil.which("ffmpeg")
    fp = shutil.which("ffprobe")
    if not ff or not fp:
        base = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / \
            "WinGet" / "Packages"
        if base.is_dir():
            ffs = sorted(base.glob("Gyan.FFmpeg*/ffmpeg-*/bin/ffmpeg.exe"))
            fps = sorted(base.glob("Gyan.FFmpeg*/ffmpeg-*/bin/ffprobe.exe"))
            ff = str(ffs[-1]) if ffs and not ff else ff
            fp = str(fps[-1]) if fps and not fp else fp
    return ff, fp


def test_env_override_wins_and_version_runs():
    ff, _ = _real_bins()
    if not ff:
        pytest.skip("no real ffmpeg on machine")
    old = os.environ.get("FFMPEG_PATH")
    try:
        os.environ["FFMPEG_PATH"] = f'"{ff}"'  # quoted, spaces inside
        assert F.which_ffmpeg() == ff
        ver = F.ffmpeg_version()
        assert ver.startswith("ffmpeg version"), ver
        st = F.ffmpeg_config_state()
        assert st == {"source": "FFMPEG_PATH", "explicit": ff,
                      "explicit_valid": True, "path": ff}
    finally:
        if old is None:
            os.environ.pop("FFMPEG_PATH", None)
        else:
            os.environ["FFMPEG_PATH"] = old


def test_invalid_explicit_path_fails_clearly():
    old = os.environ.get("FFMPEG_PATH")
    try:
        os.environ["FFMPEG_PATH"] = "C:\\definitely\\not\\ffmpeg.exe"
        assert F.which_ffmpeg() is None
        with pytest.raises(FfmpegError) as ei:
            F._need_exe()
        assert "FFMPEG_PATH points nowhere" in str(ei.value)
    finally:
        if old is None:
            os.environ.pop("FFMPEG_PATH", None)
        else:
            os.environ["FFMPEG_PATH"] = old


def test_missing_everything_reports_not_found(monkeypatch, tmp_path):
    monkeypatch.delenv("FFMPEG_PATH", raising=False)
    monkeypatch.setenv("PATH", str(tmp_path))
    assert F.which_ffmpeg() is None
    assert F.ffmpeg_version() == "NOT FOUND"
    with pytest.raises(FfmpegError) as ei:
        F._need_exe()
    assert "setup.ps1" in str(ei.value)


def test_ffprobe_env_override_and_invalid(monkeypatch):
    _, fp = _real_bins()
    if fp:
        monkeypatch.setenv("FFPROBE_PATH", fp)
        assert ffprobe_path() == fp
    monkeypatch.setenv("FFPROBE_PATH", "C:\\definitely\\not\\ffprobe.exe")
    assert ffprobe_path() is None
    with pytest.raises(MediaProbeError) as ei:
        from engine.core.media import probe
        probe(__file__)
    assert "FFPROBE_PATH points nowhere" in str(ei.value)
