"""Actionable visual-issue checks (additive; existing reviewers untouched).

Each check returns issue dicts shaped for the repair router:
{issue, severity, shot_ids, evidence, repair:{capability,...}}.
Inputs are timeline/artifact records, never pixels (frame review stays
human). Pure functions.
"""
from __future__ import annotations


def check_motion_static(timeline: dict) -> list[dict]:
    """Flag shots with no motion treatment (repair: CAMERA_PUSH)."""
    out = []
    for s in timeline.get("segments", []):
        if s.get("kind") != "clip":
            continue
        if not s.get("motion"):
            a, b = s.get("span", [0, 0])
            if (b - a) >= 4.0:
                out.append({"issue": "MOTION_TOO_STATIC",
                            "severity": "MEDIUM",
                            "shot_ids": [s.get("label", "?")],
                            "evidence": f"{b - a:.1f}s clip without motion",
                            "repair": {"capability": "CAMERA_PUSH",
                                       "strength": 0.12}})
    return out


def check_text_density(ass_events: int, duration_s: float,
                       layers: int = 2) -> list[dict]:
    """Flag caption/text overload risk (repair: caption planner)."""
    if duration_s <= 0:
        return []
    density = ass_events / duration_s
    if layers > 2 or density > 1.2:
        return [{"issue": "TEXT_OVERLOAD", "severity": "HIGH",
                 "shot_ids": [],
                 "evidence": f"{ass_events} events / {duration_s:.0f}s, "
                             f"{layers} layers",
                 "repair": {"capability": "CAPTION_SIMPLIFY",
                            "max_layers": 2}}]
    return []


def check_repetition(files: list[str]) -> list[dict]:
    """Flag cross-scene asset reuse (repair: asset matcher)."""
    reuse = len(files) - len(set(files))
    if reuse > 2:
        return [{"issue": "ASSET_REPETITION", "severity": "MEDIUM",
                 "shot_ids": [],
                 "evidence": f"cross-scene reuse={reuse}",
                 "repair": {"capability": "ASSET_REPLACE"}}]
    return []


def check_audio_balance(mean_db: float | None,
                        peak_db: float | None) -> list[dict]:
    """Flag loudness problems (repair: audio subsystem)."""
    out = []
    if peak_db is not None and peak_db > -1.0:
        out.append({"issue": "AUDIO_CLIPPING_RISK", "severity": "HIGH",
                    "shot_ids": [],
                    "evidence": f"peak {peak_db:.1f} dB",
                    "repair": {"capability": "GAIN_REDUCE"}})
    if mean_db is not None and mean_db < -28.0:
        out.append({"issue": "AUDIO_TOO_QUIET", "severity": "MEDIUM",
                    "shot_ids": [],
                    "evidence": f"mean {mean_db:.1f} dB",
                    "repair": {"capability": "GAIN_RAISE"}})
    return out


def review_all(timeline: dict, ass_events: int, files: list[str],
               mean_db: float | None = None,
               peak_db: float | None = None) -> dict:
    """Run all additive checks. Returns {issues[], verdict}."""
    issues = (check_motion_static(timeline)
              + check_text_density(ass_events,
                                   float(timeline.get("total", 0) or 0))
              + check_repetition(files)
              + check_audio_balance(mean_db, peak_db))
    verdict = ("PASS" if not issues else
               "FAIL" if any(i["severity"] == "HIGH" for i in issues)
               else "REVIEW")
    return {"issues": issues, "verdict": verdict}
