"""Parameterized motion design system (additive).

Animations are data: {"animation": "SPRING_IN", "duration": 0.45, ...}.
Each preset maps to (a) ASS override tags via creative.motion for text,
and (b) an FFmpeg-side camera move executed through the ffmpeg adapter
(camera_push). Grammar states (HOOK/SETUP/...) define density/intensity.
Pure mapping + thin execution; no new renderer.
"""
from __future__ import annotations

from engine.creative import motion as _motion

PRESETS = {
    "SPRING_IN": {"ass": "rise", "camera": None, "duration": 0.45},
    "FADE_IN": {"ass": "fade", "camera": None, "duration": 0.30},
    "SLIDE_LEFT": {"ass": "slide_in:left", "camera": None, "duration": 0.35},
    "SLIDE_RIGHT": {"ass": "slide_in:right", "camera": None,
                    "duration": 0.35},
    "PUSH_IN": {"ass": "rise", "camera": {"zoom_from": 1.0, "zoom_to": 1.12},
                "duration": 4.0},
    "PULL_BACK": {"ass": "fade", "camera": {"zoom_from": 1.12, "zoom_to": 1.0},
                  "duration": 4.0},
    "HOLD": {"ass": "fade", "camera": None, "duration": 0.30},
}

# Full vocabulary (§5 list). Supported entries map to ASS/camera ops;
# the rest return structured CAPABILITY_MISSING (no fake motion).
PRIMITIVES = {
    "fade": ("ASS fade", None), "rise": ("ASS rise", None),
    "slide": ("ASS slide_in", None), "scale": ("ASS emphasis", None),
    "punch": ("static reframe crop", None),
    "overshoot": ("ASS rise (no true spring dynamics)", None),
    "spring": (None, "needs web runtime"),
    "settle": ("ASS fade", None), "stagger": ("ASS sequential cues", None),
    "reveal": ("ASS fade", None), "wipe": ("hard cut + fade", None),
    "mask_reveal": (None, "needs mask compositing path"),
    "crop_reveal": ("ASS slide_in", None),
    "blur_reveal": (None, "needs animated blur path"),
    "tracking_reveal": (None, "needs tracked text path"),
    "type_on": ("sequential cues", None),
    "emphasis_pulse": ("ASS emphasis", None),
    "number_count_up": (None, "needs raster frame sequence"),
    "progress_animation": (None, "needs raster/vector runtime"),
    "chart_draw": (None, "needs vector runtime"),
    "path_animation": (None, "needs vector runtime"),
    "parallax": (None, "needs depth layers"),
    "camera_push": ("zoompan push", None),
    "camera_pull": ("zoompan pull", None),
    "camera_pan": ("zoompan x-pan", None),
    "camera_tilt": ("zoompan y-pan", None),
    "focus_transition": (None, "needs animated blur path"),
    "depth_shift": (None, "needs depth layers"),
    "object_drift": ("slow zoompan", None),
    "orbit": (None, "needs 3D runtime"),
    "shake": (None, "needs stabilized-shake path"),
    "impact": ("punch + sting", None),
    "glitch": (None, "needs RGB-split shader path"),
    "distortion": (None, "needs displacement path"),
    "light_sweep": (None, "needs gradient sweep path"),
    "particle_burst": (None, "needs particle runtime"),
}

_MISSING_INFO = {
    "needs web runtime": ("WEB_RUNTIME", "Chromium+GSAP/Remotion contract",
                          "CPU", "npm packages + ~150 MB Chromium"),
    "needs mask compositing path": ("MASK_COMPOSITE", "ffmpeg masked merge",
                                    "CPU", "luma-mask chain adapter"),
    "needs animated blur path": ("ANIMATED_BLUR", "gblur expression",
                                 "CPU", "filter-graph adapter"),
    "needs tracked text path": ("TEXT_TRACK", "detector + overlay track",
                                "CPU", "YOLO-class detector (AGPL blocked)"),
    "needs raster frame sequence": ("RASTER_SEQ", "Pillow frame loop",
                                    "CPU", "arabic_reshaper for AR text"),
    "needs vector runtime": ("VECTOR_RUNTIME", "resvg/Chromium",
                             "CPU", "resvg binary or Chromium"),
    "needs depth layers": ("DEPTH", "depth estimator", "GPU",
                           "MiDaS-class model (TIER 4)"),
    "needs 3D runtime": ("THREE_D", "Blender/three.js contract", "CPU/GPU",
                         "portable Blender or Chromium"),
    "needs stabilized-shake path": ("CAMERA_SHAKE", "vidstab + re-add",
                                    "CPU", "vid.stabilize adapter"),
    "needs RGB-split shader path": ("GLITCH", "chromahold/shuffleplanes",
                                    "CPU", "filter-graph adapter"),
    "needs displacement path": ("DISPLACE", "displace filter chain", "CPU",
                                "filter-graph adapter"),
    "needs gradient sweep path": ("LIGHT_SWEEP", "gradient overlay anim",
                                  "CPU", "filter-graph adapter"),
    "needs particle runtime": ("PARTICLES", "tsparticles/Matter.js", "CPU",
                               "Chromium runtime"),
}


def describe(primitive: str) -> dict:
    """Describe one primitive: supported impl or structured missing. Pure."""
    key = primitive.lower()
    if key not in PRIMITIVES:
        return {"primitive": primitive, "supported": False,
                "reason": "unknown primitive"}
    impl, need = PRIMITIVES[key]
    if impl is not None:
        return {"primitive": primitive, "supported": True, "via": impl,
                "params": ["duration", "easing", "delay", "intensity",
                           "direction", "anchor", "start", "end"]}
    cap, alt, hw, dep = _MISSING_INFO[need]
    return {"primitive": primitive, "supported": False,
            "missing": {"capability": cap, "provider": "none-registered",
                        "reason": need, "hardware": hw,
                        "dependency": dep, "alternative": alt,
                        "quality_preserved": False}}


def motion_grammar(role: str) -> str:
    """Phase D: meaning -> preset name (NO_MOTION is a valid answer). Pure."""
    return {"INTRO": "FADE_IN", "KEYWORD": "SPRING_IN",
            "STATISTIC": "HOLD", "COMPARISON": "SLIDE_LEFT",
            "PROBLEM": "HOLD", "IMPORTANT_FACT": "PUSH_IN",
            "PROCESS": "SLIDE_RIGHT", "TRANSFORMATION": "PUSH_IN",
            "CTA": "SPRING_IN", "ENDING": "FADE_IN",
            "BODY": "HOLD", "NONE": "NO_MOTION"}.get(role.upper(), "HOLD")

GRAMMAR = {
    "HOOK": {"shot_density": "high", "motion_intensity": 1.0,
             "typography": "headline", "camera": "hard cuts",
             "sfx_density": "high", "music": "in", "transition": "hard cut",
             "graphics": "many"},
    "SETUP": {"shot_density": "medium", "motion_intensity": 0.6,
              "typography": "headline", "camera": "push",
              "sfx_density": "low", "music": "bed", "transition": "hard cut",
              "graphics": "some"},
    "PROBLEM": {"shot_density": "medium", "motion_intensity": 0.6,
                "typography": "headline", "camera": "push",
                "sfx_density": "low", "music": "bed",
                "transition": "hard cut", "graphics": "some"},
    "EXPLANATION": {"shot_density": "medium", "motion_intensity": 0.5,
                    "typography": "keyword", "camera": "hold",
                    "sfx_density": "none", "music": "bed",
                    "transition": "hard cut", "graphics": "some"},
    "CONTRAST": {"shot_density": "high", "motion_intensity": 0.8,
                 "typography": "stat", "camera": "whip-ish cuts",
                 "sfx_density": "medium", "music": "lift",
                 "transition": "hard cut", "graphics": "many"},
    "STATISTIC": {"shot_density": "low", "motion_intensity": 0.4,
                  "typography": "stat", "camera": "hold",
                  "sfx_density": "sting", "music": "dip",
                  "transition": "fade", "graphics": "one big"},
    "EXAMPLE": {"shot_density": "high", "motion_intensity": 0.7,
                "typography": "keyword", "camera": "montage",
                "sfx_density": "low", "music": "drive",
                "transition": "hard cut", "graphics": "some"},
    "ESCALATION": {"shot_density": "high", "motion_intensity": 0.9,
                   "typography": "headline", "camera": "push",
                   "sfx_density": "medium", "music": "lift",
                   "transition": "hard cut", "graphics": "many"},
    "PAYOFF": {"shot_density": "low", "motion_intensity": 0.5,
               "typography": "headline", "camera": "slow push",
               "sfx_density": "low", "music": "resolve",
               "transition": "fade", "graphics": "one"},
    "CTA": {"shot_density": "low", "motion_intensity": 0.5,
            "typography": "headline", "camera": "hold",
            "sfx_density": "none", "music": "resolve",
            "transition": "fade", "graphics": "one"},
    "ENDING": {"shot_density": "low", "motion_intensity": 0.3,
               "typography": "endcard", "camera": "deliberate hold",
               "sfx_density": "none", "music": "out",
               "transition": "fade", "graphics": "one"},
}


def ass_tags(animation: str) -> str:
    """Map a preset name to ASS override tags. Pure."""
    spec = PRESETS.get(animation, PRESETS["HOLD"])
    ass = spec["ass"]
    if ass == "rise":
        return _motion.rise(540, 1560)
    if ass.startswith("slide_in"):
        side = ass.split(":")[1]
        return _motion.slide_in(540, 300, side)
    return _motion.fade()


def camera_contract(animation: str, src: str, dst: str,
                    duration: float | None = None,
                    encoder: str = "libx264") -> dict | None:
    """Map a preset to an ffmpeg-adapter camera contract (or None). Pure."""
    spec = PRESETS.get(animation, PRESETS["HOLD"])
    if not spec["camera"]:
        return None
    return {"op": "camera_push", "src": src, "dst": dst,
            "zoom_from": spec["camera"]["zoom_from"],
            "zoom_to": spec["camera"]["zoom_to"],
            "duration": duration or spec["duration"], "encoder": encoder}


def grammar_state(name: str) -> dict:
    """Visual grammar lookup. Pure."""
    return dict(GRAMMAR.get(name.upper(), GRAMMAR["EXPLANATION"]))
