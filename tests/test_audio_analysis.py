"""Phase 3 tests — audio/silence analysis (real ffmpeg, synthetic fixtures).

Covers the 6 required cases: audio file, silence, non-silent audio,
no-audio stream, invalid/missing media, cached analysis — plus deterministic
parser unit tests that need no binaries.
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests" / "fixtures"

from engine.analysis.audio import (
    AudioAnalysisError,
    analyze_audio,
    complement,
    parse_loudnorm_json,
    parse_silencedetect,
    parse_volumedetect,
)

NEEDS_FFMPEG = shutil.which("ffmpeg") is None


@pytest.fixture(scope="module", autouse=True)
def fixtures():
    if NEEDS_FFMPEG:
        pytest.skip("ffmpeg not on PATH")
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "make_test_media.py"), "--all"],
                       capture_output=True, text=True, timeout=600)
    assert r.returncode == 0, f"fixture build failed: {r.stderr[-1500:]}"
    for name in ("tone_5s.wav", "silence_5s.wav", "mixed_6s.wav",
                 "tone_5s.mp4", "silent_video.mp4", "mixed_6s.mp4"):
        assert (FIX / name).is_file(), f"missing fixture {name}"


# ---------- parser unit tests (deterministic, no ffmpeg) ----------

def test_parse_silencedetect_pairs_and_trailing():
    stderr = (
        "[silencedetect @ 0x1] silence_start: 2.01\n"
        "[silencedetect @ 0x1] silence_end: 4.005 | silence_duration: 1.995\n"
        "[silencedetect @ 0x1] silence_start: 8.0\n"
    )
    spans = parse_silencedetect(stderr, audio_duration=10.0)
    assert len(spans) == 2
    assert spans[0].start == pytest.approx(2.01)
    assert spans[0].end == pytest.approx(4.005)
    assert spans[0].duration == pytest.approx(1.995)
    assert spans[1].start == pytest.approx(8.0)  # dangling start closed at EOF
    assert spans[1].end == pytest.approx(10.0)


def test_parse_volumedetect_na():
    stderr = "mean_volume: n/a dB\nmax_volume: n/a dB\n"
    vols = parse_volumedetect(stderr)
    assert vols == {"mean_volume_db": None, "max_volume_db": None}
    vols2 = parse_volumedetect("mean_volume: -20.1 dB\nmax_volume: -5.2 dB\n")
    assert vols2 == {"mean_volume_db": -20.1, "max_volume_db": -5.2}


def test_parse_loudnorm_json_garbage():
    assert parse_loudnorm_json("no json here") == {}
    assert parse_loudnorm_json('{"foo": 1}') == {}
    good = '{\n"input_i" : "-16.0",\n"input_tp" : "-1.0",\n"input_lra" : "5.0",\n"input_thresh" : "-34.0"\n}\n'
    assert parse_loudnorm_json("blah\n" + good)["input_i"] == "-16.0"


def test_complement_basic():
    from engine.core.models import SilenceInterval
    inv = complement([SilenceInterval(2.0, 4.0, 2.0)], 6.0)
    assert [(s.start, s.end) for s in inv] == [(0.0, 2.0), (4.0, 6.0)]
    assert complement([], 3.0)[0].duration == pytest.approx(3.0)


# ---------- integration tests (real ffmpeg) ----------

def test_tone_has_audio_and_no_silence():
    a = analyze_audio(FIX / "tone_5s.wav")
    assert a.audio_present is True
    assert a.num_audio_streams == 1
    assert a.channels == 1
    assert a.sample_rate == 44100
    assert a.codec == "pcm_s16le"
    assert a.audio_duration == pytest.approx(5.0, abs=0.05)
    assert a.mean_volume_db is not None and a.max_volume_db is not None
    assert a.silence == []
    assert len(a.non_silent) == 1
    assert a.non_silent[0].start == pytest.approx(0.0, abs=0.05)
    assert a.non_silent[0].end == pytest.approx(5.0, abs=0.05)
    assert set(a.loudness) >= {"input_i", "input_tp", "input_lra"}


def test_mixed_silence_boundaries():
    a = analyze_audio(FIX / "mixed_6s.wav")
    assert a.audio_present is True
    assert len(a.silence) == 1
    s = a.silence[0]
    assert s.start == pytest.approx(2.0, abs=0.15)
    assert s.end == pytest.approx(4.0, abs=0.15)
    assert s.duration == pytest.approx(2.0, abs=0.25)
    assert a.silence_total_s == pytest.approx(2.0, abs=0.25)
    assert len(a.non_silent) == 2  # tone head + tone tail


def test_all_silence_file():
    a = analyze_audio(FIX / "silence_5s.wav")
    assert a.audio_present is True
    assert a.silence_total_s >= 4.5
    assert sum(s.duration for s in a.non_silent) <= 0.2
    assert a.mean_volume_db is None or a.mean_volume_db <= -90.0  # n/a or 16-bit floor


def test_no_audio_stream():
    a = analyze_audio(FIX / "silent_video.mp4")
    assert a.audio_present is False
    assert a.num_audio_streams == 0
    assert a.silence == [] and a.non_silent == []
    assert a.mean_volume_db is None and a.max_volume_db is None
    assert a.loudness == {}


def test_missing_file():
    with pytest.raises(AudioAnalysisError):
        analyze_audio(FIX / "does_not_exist_123.wav")


def test_min_silence_override_filters_short_gaps():
    a = analyze_audio(FIX / "mixed_6s.wav", min_silence_s=3.0)
    assert a.silence == []  # the 2 s gap is below the 3 s minimum
    assert a.config_used == {"silence_db": -35.0, "min_silence_s": 3.0}


def test_cached_analysis_via_orchestrator(tmp_path):
    from engine.core.orchestrator import run_inspect
    # Unique temp copy -> guaranteed-cold cache key (mtime/size hashed).
    target = tmp_path / "tone_cache_test.mp4"
    target.write_bytes((FIX / "tone_5s.mp4").read_bytes())
    first = run_inspect(str(target))
    assert first["cached"] is False
    assert first["audio"]["audio_present"] is True
    second = run_inspect(str(target))
    assert second["cached"] is True
    assert second["audio"] == first["audio"]
    assert second["media"] == first["media"]
    artifact = ROOT / "projects" / second["project"] / "analysis" / "audio_analysis.json"
    assert artifact.is_file()
    assert json.loads(artifact.read_text(encoding="utf-8"))["audio_present"] is True


def test_analyze_cli_writes_both_artifacts(capsys):
    from engine.cli import main
    rc = main(["analyze", str(FIX / "mixed_6s.mp4")])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert "media" in out and "audio" in out
    assert len(out["audio"]["silence"]) == 1
