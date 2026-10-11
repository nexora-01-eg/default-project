"""Provider registry: capability -> providers, environment discovery, gating.

Every provider is a plain dict (machine-readable descriptor). ``discover``
probes the live environment (imports, binaries) and annotates each
provider with a status + reason. Nothing here installs or downloads.
"""
from __future__ import annotations

import importlib.util
import shutil

GPU_NONE = "NONE"
GPU_OPTIONAL = "OPTIONAL"
GPU_REQUIRED = "REQUIRED"

ST_AVAILABLE = "AVAILABLE"
ST_MISSING = "MISSING"            # not installed / binary absent
ST_HW_BLOCKED = "HARDWARE_BLOCKED"
ST_LICENSE_BLOCKED = "LICENSE_BLOCKED"

# Static provider descriptors. ``probe`` is evaluated by discover():
# ("module", "<dotted path>") or ("bin", "<executable>") or ("always", None).
PROVIDERS: list[dict] = [
    # --- already present (REG) ---
    {"id": "ffmpeg", "capabilities": ["CUT", "TRIM", "CONCAT", "SPEED_CHANGE",
                                      "AUDIO_DUCKING", "LOUDNESS_NORMALIZATION",
                                      "SFX_SYNC", "COLOR_MATCH", "DENOISE",
                                      "STABILIZATION", "SCENE_DETECTION",
                                      "BEAT_SYNC", "MIX", "MUX", "BURN_CAPTIONS",
                                      "CAMERA_PUSH", "SCOPES"],
     "runtime": "native", "code_controlled": True, "headless": True,
     "windows": True, "cpu": True, "gpu_required": GPU_OPTIONAL,
     "cpu_fallback": True, "license_code": "LGPL-2.1+/GPL (local build: GPL full)",
     "license_model": "n/a", "needs_credentials": False,
     "needs_download": False, "probe": ("bin", "ffmpeg"),
     "gui_only": False, "evidence": "engine/rendering/ffmpeg.py"},
    {"id": "ffprobe", "capabilities": ["PROBE", "QUALITY_REVIEW", "SCOPES"],
     "runtime": "native", "code_controlled": True, "headless": True,
     "windows": True, "cpu": True, "gpu_required": GPU_NONE,
     "cpu_fallback": True, "license_code": "LGPL-2.1+/GPL (local build: GPL full)",
     "license_model": "n/a", "needs_credentials": False,
     "needs_download": False, "probe": ("bin", "ffprobe"),
     "gui_only": False, "evidence": "engine/core/media.py"},
    {"id": "faster-whisper", "capabilities": ["SPEECH_TO_TEXT", "WORD_TIMING",
                                              "CAPTION_ALIGNMENT"],
     "runtime": "python", "code_controlled": True, "headless": True,
     "windows": True, "cpu": True, "gpu_required": GPU_OPTIONAL,
     "cpu_fallback": True, "license_code": "MIT",
     "license_model": "MIT (OpenAI whisper weights)",
     "needs_credentials": False, "needs_download": True,
     "probe": ("module", "faster_whisper"),
     "gui_only": False, "evidence": "engine/analysis/speech.py"},
    {"id": "piper", "capabilities": ["TEXT_TO_SPEECH_AR"],
     "runtime": "native", "code_controlled": True, "headless": True,
     "windows": True, "cpu": True, "gpu_required": GPU_NONE,
     "cpu_fallback": True, "license_code": "MIT",
     "license_model": "voice-dependent (ar_JO kareem: NEEDS VERIFICATION)",
     "needs_credentials": False, "needs_download": True,
     "probe": ("always", None),
     "gui_only": False, "evidence": "tools/tts/piper (validated 2026-09-21)"},
    {"id": "onnxruntime", "capabilities": ["MODEL_INFERENCE_CPU"],
     "runtime": "python", "code_controlled": True, "headless": True,
     "windows": True, "cpu": True, "gpu_required": GPU_NONE,
     "cpu_fallback": True, "license_code": "MIT", "license_model": "n/a",
     "needs_credentials": False, "needs_download": False,
     "probe": ("module", "onnxruntime"),
     "gui_only": False, "evidence": "phase: rembg/whisper-adjacent"},
    {"id": "opencv", "capabilities": ["FRAME_IO", "OPTICAL_FLOW_CLASSIC",
                                      "OBJECT_TRACKING_CLASSIC",
                                      "FACE_DETECT_CLASSIC", "IMAGE_FILTERS"],
     "runtime": "python", "code_controlled": True, "headless": True,
     "windows": True, "cpu": True, "gpu_required": GPU_OPTIONAL,
     "cpu_fallback": True, "license_code": "Apache-2.0",
     "license_model": "n/a", "needs_credentials": False,
     "needs_download": False, "probe": ("module", "cv2"),
     "gui_only": False, "evidence": "engine/analysis/visual.py"},
    {"id": "pyav", "capabilities": ["FRAME_EXACT_IO"],
     "runtime": "python", "code_controlled": True, "headless": True,
     "windows": True, "cpu": True, "gpu_required": GPU_NONE,
     "cpu_fallback": True, "license_code": "MIT", "license_model": "n/a",
     "needs_credentials": False, "needs_download": False,
     "probe": ("module", "av"),
     "gui_only": False, "evidence": "phase: PyAV E2E chain"},
    {"id": "pillow", "capabilities": ["IMAGE_GEN", "IMAGE_COMPOSITE", "THUMBNAILS"],
     "runtime": "python", "code_controlled": True, "headless": True,
     "windows": True, "cpu": True, "gpu_required": GPU_NONE,
     "cpu_fallback": True, "license_code": "HPND", "license_model": "n/a",
     "needs_credentials": False, "needs_download": False,
     "probe": ("module", "PIL"),
     "gui_only": False, "evidence": "procedural cards/thumbs"},
    {"id": "scenedetect", "capabilities": ["SCENE_DETECTION", "SHOT_DETECTION"],
     "runtime": "python", "code_controlled": True, "headless": True,
     "windows": True, "cpu": True, "gpu_required": GPU_NONE,
     "cpu_fallback": True, "license_code": "BSD-3", "license_model": "n/a",
     "needs_credentials": False, "needs_download": False,
     "probe": ("module", "scenedetect"),
     "gui_only": False, "evidence": "installed 0.7.1"},
    {"id": "ass-libass", "capabilities": ["CAPTIONS", "KINETIC_CAPTIONS_BASIC",
                                          "WORD_HIGHLIGHT_BASIC"],
     "runtime": "native", "code_controlled": True, "headless": True,
     "windows": True, "cpu": True, "gpu_required": GPU_NONE,
     "cpu_fallback": True, "license_code": "ISC (libass); engine side MIT-shape",
     "license_model": "n/a", "needs_credentials": False,
     "needs_download": False, "probe": ("always", None),
     "gui_only": False, "evidence": "engine/subtitles + creative/motion.py"},
    # --- TIER 0 targets (installed by stack task, else MISSING) ---
    {"id": "librosa", "capabilities": ["BEAT_DETECTION", "ONSET_DETECTION",
                                       "AUDIO_ANALYSIS", "CHROMA"],
     "runtime": "python", "code_controlled": True, "headless": True,
     "windows": True, "cpu": True, "gpu_required": GPU_NONE,
     "cpu_fallback": True, "license_code": "ISC", "license_model": "n/a",
     "needs_credentials": False, "needs_download": False,
     "probe": ("module", "librosa"),
     "gui_only": False, "evidence": "docs/PRODUCTION_TOOL_ARSENAL_200PLUS.md"},
    {"id": "soundfile", "capabilities": ["AUDIO_IO"],
     "runtime": "python", "code_controlled": True, "headless": True,
     "windows": True, "cpu": True, "gpu_required": GPU_NONE,
     "cpu_fallback": True, "license_code": "BSD-3", "license_model": "n/a",
     "needs_credentials": False, "needs_download": False,
     "probe": ("module", "soundfile"),
     "gui_only": False, "evidence": "with librosa"},
    {"id": "pydub", "capabilities": ["AUDIO_SEGMENTS", "FADE", "SLICE"],
     "runtime": "python", "code_controlled": True, "headless": True,
     "windows": True, "cpu": True, "gpu_required": GPU_NONE,
     "cpu_fallback": True, "license_code": "MIT", "license_model": "n/a",
     "needs_credentials": False, "needs_download": False,
     "probe": ("module", "pydub"),
     "gui_only": False, "evidence": "needs system ffmpeg (present)"},
    {"id": "pyloudnorm", "capabilities": ["LOUDNESS_NORMALIZATION"],
     "runtime": "python", "code_controlled": True, "headless": True,
     "windows": True, "cpu": True, "gpu_required": GPU_NONE,
     "cpu_fallback": True, "license_code": "MIT", "license_model": "n/a",
     "needs_credentials": False, "needs_download": False,
     "probe": ("module", "pyloudnorm"),
     "gui_only": False, "evidence": "BS.1770 meter"},
    {"id": "opentimelineio", "capabilities": ["TIMELINE_IO", "EDL", "OTIO"],
     "runtime": "python", "code_controlled": True, "headless": True,
     "windows": True, "cpu": True, "gpu_required": GPU_NONE,
     "cpu_fallback": True, "license_code": "Apache-2.0",
     "license_model": "n/a", "needs_credentials": False,
     "needs_download": False, "probe": ("module", "opentimelineio"),
     "gui_only": False, "evidence": "interchange layer"},
    {"id": "svgwrite", "capabilities": ["SVG_AUTHORING", "CALLOUTS", "ARROWS",
                                        "STAT_CARD", "LOWER_THIRDS"],
     "runtime": "python", "code_controlled": True, "headless": True,
     "windows": True, "cpu": True, "gpu_required": GPU_NONE,
     "cpu_fallback": True, "license_code": "Apache-2.0",
     "license_model": "n/a", "needs_credentials": False,
     "needs_download": False, "probe": ("module", "svgwrite"),
     "gui_only": False, "evidence": "procedural graphics"},
    {"id": "webrtcvad", "capabilities": ["VOICE_ACTIVITY"],
     "runtime": "python", "code_controlled": True, "headless": True,
     "windows": True, "cpu": True, "gpu_required": GPU_NONE,
     "cpu_fallback": True, "license_code": "BSD-3",
     "license_model": "n/a", "needs_credentials": False,
     "needs_download": False, "probe": ("module", "webrtcvad"),
     "gui_only": False, "evidence": "stale upstream (2017), works"},
    {"id": "moviepy", "capabilities": ["PROGRAMMATIC_EDIT", "COMPOSITE"],
     "runtime": "python", "code_controlled": True, "headless": True,
     "windows": True, "cpu": True, "gpu_required": GPU_NONE,
     "cpu_fallback": True, "license_code": "MIT (v2.x)",
     "license_model": "n/a", "needs_credentials": False,
     "needs_download": False, "probe": ("module", "moviepy"),
     "gui_only": False,
     "evidence": "DROPPED 2026-09-24: pillow<12 pin breaks rembg>=12.1; "
                 "FFmpeg gateway already covers its use cases"},
    {"id": "jsonschema", "capabilities": ["CONTRACT_VALIDATION"],
     "runtime": "python", "code_controlled": True, "headless": True,
     "windows": True, "cpu": True, "gpu_required": GPU_NONE,
     "cpu_fallback": True, "license_code": "MIT", "license_model": "n/a",
     "needs_credentials": False, "needs_download": False,
     "probe": ("module", "jsonschema"),
     "gui_only": False, "evidence": "production contract gate"},
    {"id": "rembg", "capabilities": ["BACKGROUND_REMOVE"],
     "runtime": "python", "code_controlled": True, "headless": True,
     "windows": True, "cpu": True, "gpu_required": GPU_NONE,
     "cpu_fallback": True, "license_code": "MIT",
     "license_model": "u2net/isnet weights in Arsenal (verify per-model)",
     "needs_credentials": False, "needs_download": True,
     "probe": ("module", "rembg"),
     "gui_only": False, "evidence": "F:/Arsenal/07_AI_Models/rembg"},
    {"id": "colour-science", "capabilities": ["COLOR_MATCH", "COLOR_ANALYSIS"],
     "runtime": "python", "code_controlled": True, "headless": True,
     "windows": True, "cpu": True, "gpu_required": GPU_NONE,
     "cpu_fallback": True, "license_code": "BSD-3", "license_model": "n/a",
     "needs_credentials": False, "needs_download": False,
     "probe": ("module", "colour"),
     "gui_only": False, "evidence": "exposure/temp matching"},
    {"id": "mediapipe", "capabilities": ["FACE_LANDMARKS", "HAND_POSE"],
     "runtime": "python", "code_controlled": True, "headless": True,
     "windows": True, "cpu": True, "gpu_required": GPU_OPTIONAL,
     "cpu_fallback": True, "license_code": "Apache-2.0",
     "license_model": "bundled task models (verify per-model)",
     "needs_credentials": False, "needs_download": True,
     "probe": ("module", "mediapipe"),
     "gui_only": False, "evidence": "TIER 1 attempt"},
    {"id": "scikit-image", "capabilities": ["IMAGE_FILTERS", "IMAGE_METRICS"],
     "runtime": "python", "code_controlled": True, "headless": True,
     "windows": True, "cpu": True, "gpu_required": GPU_NONE,
     "cpu_fallback": True, "license_code": "BSD-3", "license_model": "n/a",
     "needs_credentials": False, "needs_download": False,
     "probe": ("module", "skimage"),
     "gui_only": False, "evidence": "TIER 1 attempt (~30 MB wheels)"},
    # --- documented but NOT integrated (license/hardware gates) ---
    {"id": "pedalboard", "capabilities": ["AUDIO_DSP"],
     "runtime": "python", "code_controlled": True, "headless": True,
     "windows": True, "cpu": True, "gpu_required": GPU_NONE,
     "cpu_fallback": True, "license_code": "GPL-3.0 (verified — VIRAL)",
     "license_model": "n/a", "needs_credentials": False,
     "needs_download": False, "probe": ("module", "pedalboard"),
     "gui_only": False, "evidence": "TIER 2: documented, NOT integrated"},
    {"id": "aubio", "capabilities": ["BEAT_DETECTION"],
     "runtime": "python", "code_controlled": True, "headless": True,
     "windows": True, "cpu": True, "gpu_required": GPU_NONE,
     "cpu_fallback": True, "license_code": "GPL-3.0 (verified — VIRAL)",
     "license_model": "n/a", "needs_credentials": False,
     "needs_download": False, "probe": ("module", "aubio"),
     "gui_only": False, "evidence": "TIER 2: documented, NOT integrated"},
    {"id": "remotion", "capabilities": ["PROGRAMMATIC_VIDEO", "MOTION_GRAPHICS",
                                        "KINETIC_TYPOGRAPHY",
                                        "DATA_VISUALIZATION"],
     "runtime": "node", "code_controlled": True, "headless": True,
     "windows": True, "cpu": True, "gpu_required": GPU_NONE,
     "cpu_fallback": True,
     "license_code": "proprietary source-available; FREE only individuals/<=3-person orgs; paid Company license 4+ for-profit (verified)",
     "license_model": "n/a", "needs_credentials": False,
     "needs_download": True, "probe": ("always", None),
     "gui_only": False, "evidence": "TIER 2 contract-only; needs npm+Chrome"},
    {"id": "chromium", "capabilities": ["HEADLESS_RENDER"],
     "runtime": "native", "code_controlled": True, "headless": True,
     "windows": True, "cpu": True, "gpu_required": GPU_NONE,
     "cpu_fallback": True, "license_code": "BSD-3", "license_model": "n/a",
     "needs_credentials": False, "needs_download": True,
     "probe": ("bin", "chrome"),
     "gui_only": False, "evidence": "TIER 1 need (~150 MB)"},
    {"id": "rapidocr", "capabilities": ["OCR", "SCREEN_TEXT"],
     "runtime": "python", "code_controlled": True, "headless": True,
     "windows": True, "cpu": True, "gpu_required": GPU_NONE,
     "cpu_fallback": True, "license_code": "Apache-2.0",
     "license_model": "bundled onnx models (verify per-model)",
     "needs_credentials": False, "needs_download": True,
     "probe": ("module", "rapidocr_onnxruntime"),
     "gui_only": False, "evidence": "onnxruntime CPU stack match"},
    {"id": "pycaption", "capabilities": ["SUBTITLE_CONVERT"],
     "runtime": "python", "code_controlled": True, "headless": True,
     "windows": True, "cpu": True, "gpu_required": GPU_NONE,
     "cpu_fallback": True, "license_code": "MIT", "license_model": "n/a",
     "needs_credentials": False, "needs_download": False,
     "probe": ("module", "pycaption"),
     "gui_only": False, "evidence": "SRT/VTT interchange"},
    {"id": "opencolorio", "capabilities": ["COLOR_TRANSFORM"],
     "runtime": "python", "code_controlled": True, "headless": True,
     "windows": True, "cpu": True, "gpu_required": GPU_NONE,
     "cpu_fallback": True, "license_code": "Apache-2.0",
     "license_model": "n/a", "needs_credentials": False,
     "needs_download": False, "probe": ("module", "PyOpenColorIO"),
     "gui_only": False, "evidence": "config-free transform path"},
    {"id": "blender", "capabilities": ["3D_RENDER", "3D_ANIM"],
     "runtime": "native", "code_controlled": True, "headless": True,
     "windows": True, "cpu": True, "gpu_required": GPU_OPTIONAL,
     "cpu_fallback": True, "license_code": "GPL-3.0 (subprocess-contained)",
     "license_model": "n/a", "needs_credentials": False,
     "needs_download": True, "probe": ("bin", "blender"),
     "gui_only": False, "evidence": "TIER 3 portable-detect"},
]


def _probe_ok(kind: str, target: str | None) -> bool:
    if kind == "always":
        return True
    if kind == "engine_ffmpeg":
        try:
            from engine.rendering.ffmpeg import which_ffmpeg
            return which_ffmpeg() is not None
        except Exception:
            return False
    if kind == "bin":
        assert target is not None
        return shutil.which(target) is not None
    if kind == "module":
        assert target is not None
        return importlib.util.find_spec(target) is not None
    return False


def discover() -> dict[str, dict]:
    """Probe the live environment. Returns {provider_id: status-record}."""
    out: dict[str, dict] = {}
    for p in PROVIDERS:
        kind, target = p["probe"]
        present = _probe_ok(kind, target)
        if p["id"] in ("pedalboard", "aubio"):
            status = ST_LICENSE_BLOCKED
            reason = (f"{p['license_code']} — documented only, not integrated "
                      f"(present={present})")
        elif not present:
            status, reason = ST_MISSING, f"{kind}:{target} not found"
        elif p["id"] == "remotion":
            status = ST_LICENSE_BLOCKED
            reason = ("company-license gate + npm/Chrome weight — "
                      "contract-only, evaluation use")
        else:
            status, reason = ST_AVAILABLE, "probe ok"
        out[p["id"]] = {"status": status, "reason": reason,
                        "capabilities": list(p["capabilities"])}
    return out


def providers_for(capability: str) -> list[dict]:
    """All registered providers offering a capability (sorted, deterministic)."""
    return sorted((p for p in PROVIDERS if capability in p["capabilities"]),
                  key=lambda p: p["id"])


def hardware_profile() -> dict:
    """Best-effort local hardware facts (never installs anything)."""
    import multiprocessing
    import os
    cpu = multiprocessing.cpu_count()
    ram_gb = None
    try:
        import ctypes

        class _MS(ctypes.Structure):
            _fields_ = [("length", ctypes.c_ulong),
                        ("mem_load", ctypes.c_ulong),
                        ("total_phys", ctypes.c_ulonglong),
                        ("avail_phys", ctypes.c_ulonglong),
                        ("total_page", ctypes.c_ulonglong),
                        ("avail_page", ctypes.c_ulonglong),
                        ("total_virt", ctypes.c_ulonglong),
                        ("avail_virt", ctypes.c_ulonglong),
                        ("avail_ext", ctypes.c_ulonglong)]

        ms = _MS()
        ms.length = ctypes.sizeof(_MS)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(ms))
        ram_gb = round(ms.total_phys / (1024 ** 3), 1)
    except Exception:
        ram_gb = None
    ffmpeg = shutil.which("ffmpeg")
    return {"os": os.name, "cpu_count": cpu, "ram_gb": ram_gb,
            "ffmpeg_on_path": bool(ffmpeg),
            "cuda_likely": False,
            "note": "940MX 2 GB class GPU treated as unusable for ML render"}


def gate(provider_id: str) -> dict:
    """Single-provider gate: AVAILABLE or exact block reason. No fallback."""
    disc = discover()
    rec = disc.get(provider_id)
    if rec is None:
        return {"provider": provider_id, "status": "UNKNOWN_PROVIDER",
                "reason": "not registered"}
    return {"provider": provider_id, "status": rec["status"],
            "reason": rec["reason"]}
