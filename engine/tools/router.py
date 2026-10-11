"""Capability router: request -> scored providers -> recorded decision.

Scoring dimensions (fixed weights, deterministic):
  capability_fit 30 | code_control 15 | local_exec 10 | hardware_fit 15
  determinism 10 | license_fit 10 | integration_cost 5 | maintenance 5

Rules:
- Providers with status != AVAILABLE are never selected; they appear as
  considered-with-reason in the decision record.
- Without explicit ``allow_fallback=True``, an unavailable preferred
  provider yields TOOL_UNAVAILABLE / HARDWARE_BLOCKED / LICENSE_BLOCKED
  (propagated from discovery) — never a silent substitution.
- Every decision is a plain dict (JSON-serializable) with scores kept.
"""
from __future__ import annotations

from . import registry

WEIGHTS = {
    "capability_fit": 30,
    "code_control": 15,
    "local_exec": 10,
    "hardware_fit": 15,
    "determinism": 10,
    "license_fit": 10,
    "integration_cost": 5,
    "maintenance": 5,
}

# Static suitability facts per provider id (0..1). Deterministic by design;
# evidence strings live in the arsenal doc + adapter tests.
_SUITABILITY: dict[str, dict] = {
    "ffmpeg": {"fit": 1.0, "control": 1.0, "local": 1.0, "hw": 1.0,
               "determ": 1.0, "lic": 0.7, "cost": 1.0, "maint": 1.0},
    "ffprobe": {"fit": 1.0, "control": 1.0, "local": 1.0, "hw": 1.0,
                "determ": 1.0, "lic": 0.7, "cost": 1.0, "maint": 1.0},
    "faster-whisper": {"fit": 1.0, "control": 1.0, "local": 1.0, "hw": 0.8,
                       "determ": 0.9, "lic": 1.0, "cost": 1.0, "maint": 1.0},
    "piper": {"fit": 0.8, "control": 1.0, "local": 1.0, "hw": 1.0,
              "determ": 0.8, "lic": 0.6, "cost": 1.0, "maint": 0.8},
    "onnxruntime": {"fit": 0.9, "control": 1.0, "local": 1.0, "hw": 1.0,
                    "determ": 1.0, "lic": 1.0, "cost": 1.0, "maint": 1.0},
    "opencv": {"fit": 1.0, "control": 1.0, "local": 1.0, "hw": 1.0,
               "determ": 1.0, "lic": 1.0, "cost": 1.0, "maint": 1.0},
    "pyav": {"fit": 1.0, "control": 1.0, "local": 1.0, "hw": 1.0,
             "determ": 1.0, "lic": 1.0, "cost": 1.0, "maint": 1.0},
    "pillow": {"fit": 1.0, "control": 1.0, "local": 1.0, "hw": 1.0,
               "determ": 1.0, "lic": 1.0, "cost": 1.0, "maint": 1.0},
    "scenedetect": {"fit": 1.0, "control": 1.0, "local": 1.0, "hw": 1.0,
                    "determ": 0.9, "lic": 1.0, "cost": 1.0, "maint": 1.0},
    "ass-libass": {"fit": 0.8, "control": 1.0, "local": 1.0, "hw": 1.0,
                   "determ": 1.0, "lic": 1.0, "cost": 1.0, "maint": 1.0},
    "librosa": {"fit": 1.0, "control": 1.0, "local": 1.0, "hw": 1.0,
                "determ": 1.0, "lic": 1.0, "cost": 0.9, "maint": 1.0},
    "soundfile": {"fit": 1.0, "control": 1.0, "local": 1.0, "hw": 1.0,
                  "determ": 1.0, "lic": 1.0, "cost": 1.0, "maint": 1.0},
    "pydub": {"fit": 1.0, "control": 1.0, "local": 1.0, "hw": 1.0,
              "determ": 1.0, "lic": 1.0, "cost": 1.0, "maint": 0.8},
    "pyloudnorm": {"fit": 1.0, "control": 1.0, "local": 1.0, "hw": 1.0,
                   "determ": 1.0, "lic": 1.0, "cost": 1.0, "maint": 0.9},
    "opentimelineio": {"fit": 1.0, "control": 1.0, "local": 1.0, "hw": 1.0,
                       "determ": 1.0, "lic": 1.0, "cost": 0.9, "maint": 1.0},
    "svgwrite": {"fit": 1.0, "control": 1.0, "local": 1.0, "hw": 1.0,
                 "determ": 1.0, "lic": 1.0, "cost": 1.0, "maint": 0.9},
    "webrtcvad": {"fit": 0.9, "control": 1.0, "local": 1.0, "hw": 1.0,
                  "determ": 1.0, "lic": 1.0, "cost": 1.0, "maint": 0.5},
    "moviepy": {"fit": 0.9, "control": 1.0, "local": 1.0, "hw": 0.9,
                "determ": 0.8, "lic": 1.0, "cost": 0.7, "maint": 0.9},
    "jsonschema": {"fit": 1.0, "control": 1.0, "local": 1.0, "hw": 1.0,
                   "determ": 1.0, "lic": 1.0, "cost": 1.0, "maint": 1.0},
    "rembg": {"fit": 1.0, "control": 1.0, "local": 1.0, "hw": 0.8,
              "determ": 0.9, "lic": 0.8, "cost": 0.9, "maint": 1.0},
    "colour-science": {"fit": 1.0, "control": 1.0, "local": 1.0, "hw": 1.0,
                       "determ": 1.0, "lic": 1.0, "cost": 0.9, "maint": 1.0},
    "mediapipe": {"fit": 0.9, "control": 1.0, "local": 1.0, "hw": 0.9,
                  "determ": 0.9, "lic": 0.8, "cost": 0.8, "maint": 1.0},
    "scikit-image": {"fit": 0.9, "control": 1.0, "local": 1.0, "hw": 1.0,
                     "determ": 1.0, "lic": 1.0, "cost": 0.9, "maint": 1.0},
}

_DEFAULT_SUITABILITY = {"fit": 0.5, "control": 0.5, "local": 0.5, "hw": 0.5,
                        "determ": 0.5, "lic": 0.5, "cost": 0.5, "maint": 0.5}

_MISSING_PENALTY = {"TOOL_UNAVAILABLE": 0.0, "LICENSE_BLOCKED": 0.0,
                    "HARDWARE_BLOCKED": 0.0}


def _score(pid: str) -> tuple[float, dict]:
    s = _SUITABILITY.get(pid, _DEFAULT_SUITABILITY)
    parts = {
        "capability_fit": WEIGHTS["capability_fit"] * s["fit"],
        "code_control": WEIGHTS["code_control"] * s["control"],
        "local_exec": WEIGHTS["local_exec"] * s["local"],
        "hardware_fit": WEIGHTS["hardware_fit"] * s["hw"],
        "determinism": WEIGHTS["determinism"] * s["determ"],
        "license_fit": WEIGHTS["license_fit"] * s["lic"],
        "integration_cost": WEIGHTS["integration_cost"] * s["cost"],
        "maintenance": WEIGHTS["maintenance"] * s["maint"],
    }
    return round(sum(parts.values()), 2), {k: round(v, 2) for k, v in parts.items()}


def resolve(capability: str, params: dict | None = None,
            preferred: str | None = None,
            allow_fallback: bool = False) -> dict:
    """Resolve one capability request. Returns a recorded decision dict."""
    params = dict(params or {})
    disc = registry.discover()
    candidates = registry.providers_for(capability)
    considered = []
    eligible = []
    for p in candidates:
        pid = p["id"]
        st = disc.get(pid, {"status": registry.ST_MISSING,
                            "reason": "unregistered"})
        total, parts = _score(pid)
        rec = {"provider": pid, "status": st["status"],
               "reason": st["reason"], "score": total, "parts": parts}
        considered.append(rec)
        if st["status"] == registry.ST_AVAILABLE:
            eligible.append(rec)
    considered.sort(key=lambda r: (-r["score"], r["provider"]))
    eligible.sort(key=lambda r: (-r["score"], r["provider"]))

    if preferred is not None:
        pref = next((r for r in considered if r["provider"] == preferred),
                    None)
        if pref is None:
            return {"capability": capability, "params": params,
                    "decision": "UNKNOWN_PROVIDER",
                    "selected": None, "considered": considered,
                    "reason": f"preferred={preferred} not registered"}
        if pref["status"] == registry.ST_AVAILABLE:
            return {"capability": capability, "params": params,
                    "decision": "SELECTED_PREFERRED",
                    "selected": pref, "considered": considered,
                    "reason": f"preferred={preferred} available"}
        if not allow_fallback:
            return {"capability": capability, "params": params,
                    "decision": pref["status"],
                    "selected": None, "considered": considered,
                    "reason": (f"preferred={preferred} {pref['status']}: "
                               f"{pref['reason']} (no silent fallback)")}
    if not eligible:
        top = considered[0] if considered else None
        decision = top["status"] if top else "CAPABILITY_MISSING"
        if decision == registry.ST_AVAILABLE:
            decision = "CAPABILITY_MISSING"
        return {"capability": capability, "params": params,
                "decision": decision, "selected": None,
                "considered": considered,
                "reason": "no AVAILABLE provider for capability"}
    picked = eligible[0]
    if preferred is not None and picked["provider"] != preferred:
        return {"capability": capability, "params": params,
                "decision": "SELECTED_FALLBACK", "selected": picked,
                "considered": considered,
                "reason": (f"preferred={preferred} unavailable; explicit "
                           f"allow_fallback selected {picked['provider']} "
                           f"(score {picked['score']})")}
    return {"capability": capability, "params": params,
            "decision": "SELECTED", "selected": picked,
            "considered": considered,
            "reason": f"top score {picked['score']}"}
