"""Phase 5/6 unit tests — no model download, no network, no inference.

The only test using a stand-in model is explicitly labeled FAKE and covers
pipeline plumbing (span shifting, fillers, validation, caching) — never
claimed as speech verification. Real inference lives in test_speech_real.py.
"""
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests" / "fixtures"

import engine.analysis.speech as speech
from engine.analysis.fillers import annotate_fillers, filler_set
from engine.analysis.speech import (
    SpeechError,
    resolve_compute,
    resolve_device,
    transcribe_file,
    transcribe_to_project,
    validate_model_name,
    validate_transcript_dict,
)


@pytest.fixture(scope="module", autouse=True)
def fixtures():
    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg not on PATH")
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "make_test_media.py"), "--all"],
                       capture_output=True, text=True, timeout=600)
    assert r.returncode == 0, f"fixture build failed: {r.stderr[-1500:]}"


# ---------- fillers ----------

def test_filler_sets_extensible():
    assert "um" in filler_set("en") and "uh" in filler_set("en")
    assert "يعني" in filler_set("ar")
    assert filler_set("xx") == frozenset()
    assert filler_set("en-US") == filler_set("en")  # prefix match


def test_annotate_fillers_case_and_punctuation():
    segs = [{"id": 0, "words": [
        {"word": "Um,", "start": 0.0, "end": 0.3},
        {"word": "hello", "start": 0.3, "end": 0.6},
        {"word": "UH", "start": 0.6, "end": 0.8}]}]
    out = annotate_fillers(segs, "en")
    assert [(f["word"], f["segment_id"]) for f in out] == [("Um,", 0), ("UH", 0)]
    assert annotate_fillers(segs, "xx") == []


# ---------- validation ----------

def test_validate_transcript_good():
    d = {"duration": 5.0, "segments": [
        {"id": 0, "start": 0.0, "end": 2.0,
         "words": [{"word": "hi", "start": 0.1, "end": 0.4}]}]}
    assert validate_transcript_dict(d) == []


def test_validate_transcript_bad():
    d = {"duration": 5.0, "segments": [
        {"id": 0, "start": -1.0, "end": 0.0,   # negative start
         "words": [{"word": "x", "start": 0.5, "end": 0.4}]},  # inverted + outside
        {"id": 1, "start": 3.0, "end": 3.0, "words": []}]}     # end not > start
    issues = validate_transcript_dict(d)
    assert len(issues) >= 3


# ---------- config / model gating (no downloads) ----------

def test_invalid_model_device_compute_spans():
    with pytest.raises(SpeechError):
        validate_model_name("huge-v9")
    with pytest.raises(SpeechError):
        resolve_device("tpu")
    with pytest.raises(SpeechError):
        resolve_compute("bf16", "cpu")
    with pytest.raises(SpeechError):
        transcribe_file(FIX / "tone_5s.wav", model="tiny", spans="sideways")
    assert resolve_device("cpu") == "cpu"
    assert resolve_compute("auto", "cpu") == "int8"


def test_auto_device_is_verified_cpu_on_reference_box():
    # 940MX reports a CUDA device (count=1) but CC 5.0 rejects all compute
    # types; auto must resolve to cpu WITHOUT attempting a model load.
    from engine.analysis.speech import cuda_usable, resolve_device
    assert cuda_usable() is False
    assert resolve_device("auto") == "cpu"


def test_cuda_load_fallback_to_cpu(monkeypatch):
    # _load_model must fall back gracefully (and say so) when cuda fails.
    import engine.analysis.speech as speech_mod

    class Flaky:
        def __init__(self, model, device="cpu", compute_type="int8", **kw):
            if device == "cuda":
                raise ValueError("no efficient cuda compute")
            self.device = device

    monkeypatch.setattr(speech_mod, "_MODEL_CLS", Flaky)
    inst, note = speech_mod._load_model("tiny", "cuda", "float16")
    assert inst.device == "cpu" and "falling back" in note


def test_missing_file():
    with pytest.raises(SpeechError, match="not found"):
        transcribe_file(FIX / "nope_123.wav", model="tiny")


def test_model_missing_without_download_flag(tmp_path):
    # Empty download root: model cannot be present -> explicit error, no network.
    with pytest.raises(SpeechError, match="not cached locally"):
        transcribe_file(FIX / "tone_5s.wav", model="tiny",
                        download_root=tmp_path / "empty_hub", allow_download=False)


def test_no_audio_never_touches_model(tmp_path):
    t = transcribe_file(FIX / "silent_video.mp4", model="tiny",
                        download_root=tmp_path / "empty_hub", allow_download=False)
    assert t.skipped_reason == "no_audio"
    assert t.segments == [] and t.word_count == 0


def test_fully_silent_never_touches_model(tmp_path):
    t = transcribe_file(FIX / "silence_5s.wav", model="tiny",
                        download_root=tmp_path / "empty_hub", allow_download=False)
    assert t.skipped_reason == "fully_silent"
    assert t.segments == []


# ---------- cache-key sensitivity (no inference) ----------

def test_transcribe_cache_key_sensitivity(tmp_path):
    from engine.core.pipeline import cache_key
    f = tmp_path / "k.wav"
    f.write_bytes(b"\x00" * 44100)
    base = {"model": "tiny", "language": "auto", "device": "cpu",
            "compute_type": "int8", "word_timestamps": True, "spans": "full",
            "silence_db": -35.0, "min_silence_s": 0.5}
    k0 = cache_key(f, "transcribe", base)
    assert cache_key(f, "transcribe", base) == k0
    for field, val in (("model", "base"), ("language", "en"),
                       ("word_timestamps", False), ("spans", "non_silent"),
                       ("compute_type", "float32"), ("silence_db", -40.0)):
        alt = dict(base, **{field: val})
        assert cache_key(f, "transcribe", alt) != k0, field


# ---------- FAKE-model plumbing (labeled, deterministic) ----------

class _FakeWord:
    def __init__(self, word, start, end, probability=0.9):
        self.word, self.start, self.end, self.probability = word, start, end, probability


class _FakeSeg:
    def __init__(self, text, start, end, words):
        self.text, self.start, self.end, self.words = text, start, end, words


class _FakeInfo:
    language, language_probability, duration = "en", 0.99, 6.0


class _FakeModel:
    """Stand-in ONLY for pipeline plumbing tests (NOT speech verification)."""
    def __init__(self, *a, **k):
        pass

    def transcribe(self, audio, language=None, word_timestamps=True):
        words = ([_FakeWord("um", 0.0, 0.3), _FakeWord("hello", 0.4, 0.8)]
                 if word_timestamps else None)
        return ([_FakeSeg("um hello", 0.0, 1.0, words)], _FakeInfo())


@pytest.fixture()
def fake_model(monkeypatch):
    monkeypatch.setattr(speech, "_MODEL_CLS", _FakeModel)
    monkeypatch.setattr(speech, "ensure_model_local", lambda *a, **k: "fake-path")
    return _FakeModel


def test_fake_plumbing_full_spans(fake_model):
    t = transcribe_file(FIX / "tone_5s.wav", model="tiny")
    assert t.language == "en" and t.segment_count == 1 and t.word_count == 2
    assert t.segments[0].start == 0.0
    assert [f["word"] for f in t.fillers] == ["um"]  # annotation only
    assert t.timestamp_issues == []
    assert t.skipped_reason == ""


def test_fake_plumbing_non_silent_shifts_timestamps(fake_model):
    # mixed_6s.wav non-silent spans are [0,2],[4,6]: fake span-relative words
    # must be shifted back onto the ORIGINAL timeline.
    t = transcribe_file(FIX / "mixed_6s.wav", model="tiny", spans="non_silent")
    assert t.segment_count == 2
    assert t.segments[0].start == pytest.approx(0.0, abs=0.05)
    assert t.segments[1].start == pytest.approx(4.0, abs=0.35)
    assert t.segments[1].words[0].start == pytest.approx(4.0, abs=0.35)
    assert t.timestamp_issues == []


def test_fake_plumbing_cache_and_word_flag(fake_model, tmp_path):
    target = tmp_path / "cache_plumb.wav"
    target.write_bytes((FIX / "tone_5s.wav").read_bytes())
    first = transcribe_to_project(str(target), model="tiny")
    assert first["cached"] is False
    second = transcribe_to_project(str(target), model="tiny")
    assert second["cached"] is True
    assert second["transcript"] == first["transcript"]
    other = transcribe_to_project(str(target), model="tiny", word_timestamps=False)
    assert other["cached"] is False  # different params -> different entry
    assert other["transcript"]["word_count"] == 0
    artifact = ROOT / "projects" / second["project"] / "analysis" / "transcript.json"
    assert artifact.is_file()
