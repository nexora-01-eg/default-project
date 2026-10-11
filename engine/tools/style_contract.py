"""Visual Style Contract (Phase N): declare once, check every shot. Pure."""
from __future__ import annotations

DEFAULT_CONTRACT = {
    "primary_font": "Arial",
    "secondary_font": "Arial",
    "typography_hierarchy": ["Title", "Key", "Body"],
    "spacing": {"margin_h": 90, "margin_v_body": 190,
                "margin_v_key": 230},
    "corner_radius": 40,
    "graphic_language": "flat_dark_card",
    "motion_language": "rise_fade_slide",
    "transition_language": "hard_cut_with_fades",
    "color_treatment": "uniform_saturation_1.15",
    "caption_style": "Body_bottom_center",
    "headline_style": "Title_center",
    "overlay_style": "Key_top_center",
    "palette": ["#0B102E", "#FFD98A", "#FFFFFF"],
    "max_text_layers": 2,
}


def check_shot(shot: dict, contract: dict | None = None) -> list[dict]:
    """Check one shot record against the style contract. Pure."""
    contract = contract or DEFAULT_CONTRACT
    issues = []
    fonts = {t.get("font", contract["primary_font"])
             for t in shot.get("texts", [])}
    if len(fonts - {contract["primary_font"],
                    contract["secondary_font"]}) > 0:
        issues.append({"issue": "STYLE_FONT", "shot": shot.get("shot_id",
                                                               "?"),
                       "evidence": f"fonts {sorted(fonts)}",
                       "repair": {"capability": "STYLE_UNIFY"}})
    if len(shot.get("texts", [])) > contract["max_text_layers"]:
        issues.append({"issue": "STYLE_LAYERS", "shot": shot.get("shot_id",
                                                                 "?"),
                       "evidence": "too many text layers",
                       "repair": {"capability": "CAPTION_SIMPLIFY"}})
    if shot.get("motion") not in (None, "", "cut", "fade", "rise", "slide",
                                  "push", "punch", "hard cut", "hold",
                                  "fade in", "montage", "slow push",
                                  "deliberate hold"):
        issues.append({"issue": "STYLE_MOTION", "shot": shot.get("shot_id",
                                                                 "?"),
                       "evidence": f"motion {shot.get('motion')!r} outside "
                                   "motion language",
                       "repair": {"capability": "MOTION_REPLACE"}})
    return issues


def check_production(shots: list[dict],
                     contract: dict | None = None) -> dict:
    """Whole-production style audit. Pure."""
    issues = [i for s in shots for i in check_shot(s, contract)]
    return {"issues": issues,
            "verdict": "PASS" if not issues else "REVIEW"}
