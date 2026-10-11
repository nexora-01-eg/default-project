"""Phase 5/6 integration tests — REAL faster-whisper inference (tiny model).

Honest end-to-end verification: real model load, real transcription of
Windows-SAPI-synthesized speech (offline, built-in voices, no new deps),
real cache behavior. Slow/heavy by design; failures here are real failures.
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests" / "fixtures"
SAPI_WAV = FIX / "speech_sapi.wav"
SAPI_MIXED = FIX / "speech_mixed.wav"
SAPI_TEXT = ("Hello world. This is a test of the local speech engine. "
             "The quick brown fox jumps over the lazy dog.")

from engine.analysis.speech import (
    download_model_explicit,
    ensure_model_local,
    transcribe_file,
    transcribe_to_project,
)


def _sapi_speak(dest: Path, text: str) -> bool:
    ps = ("Add-Type -AssemblyName System.Speech; "
          "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
          "$s.SelectVoice('Microsoft Zira Desktop'); $s.Rate = -1; "
          f"$s.SetOutputToWaveFile('{dest}'); $s.Speak('{text}'); $s.Dispose()")
    r = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                       capture_output=True, text=True, timeout=300)
    return r.returncode == 0 and dest.is_file() and dest.stat().st_size > 100_000


@pytest.fixture(scope="module", autouse=True)
def speech_media():
    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg not on PATH")
    if not SAPI_WAV.is_file():
        if not _sapi_speak(SAPI_WAV, SAPI_TEXT):
            pytest.skip("SAPI TTS unavailable - cannot synthesize speech fixture")
    from engine.core.media import probe
    if not SAPI_MIXED.is_file():
        d1 = probe(SAPI_WAV).duration
        r = subprocess.run(
            [shutil.which("ffmpeg"), "-y", "-i", str(SAPI_WAV),
             "-f", "lavfi", "-i", "anullsrc=cl=mono:r=44100:d=2",
             "-i", str(SAPI_WAV), "-filter_complex",
             "[0:a][1:a][2:a]concat=n=3:v=0:a=1",
             "-c:a", "pcm_s16le", str(SAPI_MIXED)],
            capture_output=True, text=True, timeout=300)
        assert r.returncode == 0, f"mixed build failed: {r.stderr[-800:]}"
    # Explicit model provisioning (the documented setup action, not a side effect).
    try:
        ensure_model_local("tiny")
    except Exception:
        download_model_explicit("tiny")
    return {"speech_dur": probe(SAPI_WAV).duration}


def _full_text(t) -> str:
    return " ".join(s.text for s in t.segments)


def test_real_transcribe_tiny(speech_media):
    t = transcribe_file(SAPI_WAV, model="tiny")
    assert t.skipped_reason == ""
    assert t.language == "en" and t.language_probability > 0.5
    assert t.segment_count >= 1 and t.word_count >= 10
    assert t.timestamp_issues == []
    assert t.duration == pytest.approx(speech_media["speech_dur"], abs=1.0)
    assert t.engine["device"] == "cpu" and t.engine["compute_type"] == "int8"
    assert t.performance["realtime_factor"] > 1.0
    text = _full_text(t).lower()
    assert "hello" in text and "fox" in text  # real recognition, not plumbing
    json.dumps(t.__dict__, default=str)  # JSON-serializable


def test_real_word_timestamps_valid(speech_media):
    t = transcribe_file(SAPI_WAV, model="tiny")
    for s in t.segments:
        for w in s.words:
            assert w.end > w.start
            assert w.start >= s.start - 0.5 and w.end <= s.end + 0.5


def test_real_cache_flags(tmp_path):
    target = tmp_path / "speech_cache.wav"
    target.write_bytes(SAPI_WAV.read_bytes())
    first = transcribe_to_project(str(target), model="tiny")
    assert first["cached"] is False
    second = transcribe_to_project(str(target), model="tiny")
    assert second["cached"] is True
    assert second["transcript"] == first["transcript"]
    assert second["transcript"]["segment_count"] >= 1


def test_real_spans_alignment(speech_media):
    from engine.core.media import probe
    d1 = speech_media["speech_dur"]
    t = transcribe_file(SAPI_MIXED, model="tiny", spans="non_silent")
    assert t.segment_count >= 2
    assert t.segments[0].start == pytest.approx(0.0, abs=0.6)
    late = [s for s in t.segments if s.start >= d1 + 1.0]
    assert late, "second speech block must appear after the silence gap, shifted back"
    assert late[0].start == pytest.approx(d1 + 2.0, abs=0.8)
    assert t.timestamp_issues == []
    assert probe(SAPI_MIXED).duration == pytest.approx(t.duration, abs=0.5)


def test_real_no_word_timestamps_flag():
    t = transcribe_file(SAPI_WAV, model="tiny", word_timestamps=False)
    assert t.segment_count >= 1 and t.word_count == 0


def test_real_forced_language():
    t = transcribe_file(SAPI_WAV, model="tiny", language="en")
    assert t.language == "en" and t.language_mode == "forced"


def test_real_cli_transcribe(capsys):
    from engine.cli import main
    rc = main(["transcribe", str(SAPI_WAV), "--model", "tiny"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "language: en" in out and "segments:" in out
    pid = [l.split(":")[1].strip() for l in out.splitlines()
           if l.startswith("project :")][0].split()[0]
    artifact = ROOT / "projects" / pid / "analysis" / "transcript.json"
    assert artifact.is_file()
    assert json.loads(artifact.read_text(encoding="utf-8"))["word_count"] >= 10
