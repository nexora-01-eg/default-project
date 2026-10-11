"""Registry + router tests: discovery, determinism, no-silent-fallback."""
import sys
from pathlib import Path

sys.path.insert(0, ".")
import pytest

from engine.tools import registry
from engine.tools import router
from engine.tools.registry import (ST_AVAILABLE, ST_LICENSE_BLOCKED,
                                   ST_MISSING)


def test_discover_keys_and_core_available():
    d = registry.discover()
    for pid in ("ffmpeg", "ffprobe", "faster-whisper", "opencv", "pillow",
                "scenedetect", "onnxruntime", "pyav"):
        assert d[pid]["status"] == ST_AVAILABLE, pid
    assert d["pedalboard"]["status"] == ST_LICENSE_BLOCKED
    assert d["aubio"]["status"] == ST_LICENSE_BLOCKED
    assert d["remotion"]["status"] == ST_LICENSE_BLOCKED


def test_providers_for_deterministic():
    a = [p["id"] for p in registry.providers_for("CUT")]
    b = [p["id"] for p in registry.providers_for("CUT")]
    assert a == b and "ffmpeg" in a


def test_router_selects_available():
    r = router.resolve("CUT", {"duration": 4.0})
    assert r["decision"] in ("SELECTED", "SELECTED_PREFERRED")
    assert r["selected"]["provider"] == "ffmpeg"
    assert r["selected"]["score"] > 0
    assert any(c["provider"] == "ffmpeg" for c in r["considered"])


def test_router_preferred_unavailable_no_fallback():
    r = router.resolve("AUDIO_DSP", preferred="pedalboard",
                       allow_fallback=False)
    assert r["selected"] is None
    assert r["decision"] in ("LICENSE_BLOCKED", "TOOL_UNAVAILABLE",
                             "MISSING", "HARDWARE_BLOCKED")


def test_router_fallback_is_recorded():
    r = router.resolve("AUDIO_DSP", preferred="pedalboard",
                       allow_fallback=True)
    if r["selected"] is not None:
        assert r["decision"] == "SELECTED_FALLBACK"
        assert "preferred=pedalboard" in r["reason"]
    else:
        assert r["decision"] in ("LICENSE_BLOCKED", "TOOL_UNAVAILABLE",
                                 "MISSING", "HARDWARE_BLOCKED",
                                 "CAPABILITY_MISSING")


def test_router_unknown_capability():
    r = router.resolve("TELEPORTATION")
    assert r["selected"] is None
    assert r["decision"] == "CAPABILITY_MISSING"


def test_gate_unknown_provider():
    g = registry.gate("nope-not-real")
    assert g["status"] == "UNKNOWN_PROVIDER"


def test_hardware_profile_shape():
    h = registry.hardware_profile()
    assert h["cpu_count"] >= 1 and h["cuda_likely"] is False
