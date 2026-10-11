"""SFX director (Phase L) + music director (Phase M). Pure decisions.

SFX: every decision carries purpose/timing/source/gain/duration/
confidence; silence is a valid decision. Music: story-state machine
(INTRO/LOW/BUILD/TENSION/PEAK/RELEASE/ENDING) with ducking + beat-aware
cuts. Execution stays in gateway ops (gain/fade/mix) + librosa beats.
"""
from __future__ import annotations

SFX_RULES = {
    "HOOK": ("sting", "hook impact", -12.0, 1.2),
    "STATISTIC": ("tick", "stat reveal", -14.0, 0.6),
    "PROCESS": ("transition_tick", "step change", -16.0, 0.4),
    "PAYOFF": ("accent", "restrained payoff", -12.0, 1.0),
    "ENDING": ("none", "resolve in silence", 0.0, 0.0),
}

MUSIC_STATES = ("INTRO", "LOW", "BUILD", "TENSION", "PEAK", "RELEASE",
                "ENDING")
STATE_GAIN = {"INTRO": 0.0, "LOW": -6.0, "BUILD": -3.0, "TENSION": -4.0,
              "PEAK": -1.5, "RELEASE": -4.0, "ENDING": -2.0}
STATE_FOR_STORY = {"HOOK": "INTRO", "SETUP": "LOW", "PROBLEM": "TENSION",
                   "EXPLANATION": "LOW", "CONTRAST": "BUILD",
                   "STATISTIC": "PEAK", "EXAMPLE": "BUILD",
                   "ESCALATION": "TENSION", "PROCESS": "BUILD",
                   "SURPRISE": "PEAK", "PAYOFF": "RELEASE",
                   "INSIGHT": "RELEASE", "CTA": "RELEASE",
                   "ENDING": "ENDING", "QUESTION": "LOW", "CONTEXT": "LOW"}


def sfx_for(state: str, at: float) -> dict:
    """Semantic SFX decision for a story state at time t. Pure."""
    kind, purpose, gain, dur = SFX_RULES.get(state.upper(),
                                             ("none", "no accent", 0.0, 0.0))
    return {"kind": kind, "purpose": purpose, "at": round(at, 2),
            "gain_db": gain, "duration_s": dur,
            "confidence": "HIGH_CONFIDENCE" if kind != "none"
                          else "HIGH_CONFIDENCE",
            "source": "Arsenal SFX (attenuated) or none"}


def music_plan(story: list[dict], total_s: float) -> list[dict]:
    """Story states -> ducked gain segments across the timeline. Pure."""
    if not story:
        return [{"start": 0.0, "end": round(total_s, 2), "gain_db": -6.0,
                 "state": "LOW"}]
    span = total_s / len(story)
    out = []
    for i, s in enumerate(story):
        state = STATE_FOR_STORY.get(str(s).upper(), "LOW")
        out.append({"start": round(i * span, 2),
                    "end": round(min((i + 1) * span, total_s), 2),
                    "gain_db": STATE_GAIN[state], "state": state})
    return out


def snap_to_beats(cuts: list[float], beats: list[float],
                  window: float = 1.5) -> list[dict]:
    """Snap planned cut times to nearest detected beats. Pure."""
    out = []
    for c in cuts:
        near = min(beats, key=lambda b: abs(b - c), default=None)
        if near is not None and abs(near - c) <= window:
            out.append({"planned": c, "snapped": round(near, 2),
                        "shift": round(near - c, 2)})
        else:
            out.append({"planned": c, "snapped": c, "shift": 0.0})
    return out
