"""Visual Director (Phase F/G/H): script -> visual director plan.

Per sentence/idea: meaning, emotion, info type, opportunity, metaphor,
shot type, asset requirement, motion, typography, SFX, music, transition,
camera. Derived from meaning via rules, never a fixed template.
Story grammar (HOOK..ENDING) + metaphor engine (15 categories).
Pure + deterministic.
"""
from __future__ import annotations

import re

STATES = ("HOOK", "SETUP", "QUESTION", "PROBLEM", "CONTEXT", "EXPLANATION",
          "CONTRAST", "EXAMPLE", "STATISTIC", "PROCESS", "ESCALATION",
          "SURPRISE", "PAYOFF", "INSIGHT", "CTA", "ENDING")

EMOTION = (
    ("urgent|الآن|breaking|عاجل|fast", "urgency"),
    ("question|؟|\\?|how|why|إزاي|ليه", "curiosity"),
    ("calm|steady|deliberate|هادي|بشويش", "calm"),
    ("risk|danger|problem|مشكلة|خطر|fail", "tension"),
    ("win|success|payoff|كسب|نجاح|future|مستقبل", "optimism"),
    ("surpris|unexpected|لكن|but|actually|فجأة", "surprise"),
)

INFO_TYPE = (
    ("\\d+%|\\d+\\s*(second|minute|hour|ثانية|دقيقة|ساعة)|statistic|نسبة",
     "STATISTIC"),
    ("\\b(AI|workflow|tool|decision|video|مونتاج|ذكاء)\\b", "TECH_TERM"),
    ("before|after|old|new|vs|مقابل|زمان|دلوقتي", "CONTRAST"),
    ("how|step|first|then|finally|أول|بعدين|أخيرا", "PROCESS"),
)

METAPHORS = {
    "TRANSFORMATION": ["before_after", "workflow_acceleration",
                       "pipeline_morph"],
    "COMPARISON": ["split_screen", "side_by_side", "old_vs_new"],
    "GROWTH": ["rising_bars", "expanding_network", "counter_up"],
    "SPEED": ["timeline_compression", "rapid_cuts", "motion_lines"],
    "BOTTLENECK": ["narrowing_funnel", "waiting_cursor", "piling_tasks"],
    "NETWORK": ["expanding_nodes", "connection_lines"],
    "AUTOMATION": ["sequential_operations", "hands_off_keys"],
    "SCALE": ["zoom_out_reveal", "multiplying_grid"],
    "RISK": ["warning_callout", "red_accent_hold"],
    "DISCOVERY": ["spotlight_reveal", "magnifier_push"],
    "CONNECTION": ["linking_lines", "handshake_frame"],
    "SEPARATION": ["split_wipe", "dividing_line"],
    "REPLACEMENT": ["crossfade_swap", "empty_chair"],
    "COLLABORATION": ["human_machine_frame", "side_by_side_work"],
    "FLOW": ["directional_lines", "left_to_right_drift"],
}

def _metaphor_category(text: str) -> str:
    t = text.lower()
    if re.search(r"chang|transform|تحو|غيّر|بدل", t):
        return "TRANSFORMATION"
    if re.search(r"vs|versus|مقابل|old.*new|before.*after", t):
        return "COMPARISON"
    if re.search(r"grow|more|scale|increase|كبر|زاد", t):
        return "GROWTH"
    if re.search(r"fast|quick|speed|second|أسرع|ثواني|دقايق", t):
        return "SPEED"
    if re.search(r"stuck|slow|wait|bottleneck|عطل|مستني", t):
        return "BOTTLENECK"
    if re.search(r"network|connect|nodes|شبكة", t):
        return "NETWORK"
    if re.search(r"automat|workflow|pipeline|تلقائي|سير", t):
        return "AUTOMATION"
    if re.search(r"human|person|hand|together|إنسان|إيد|فريق", t):
        return "COLLABORATION"
    if re.search(r"risk|danger|warning|خطر|تحذير", t):
        return "RISK"
    if re.search(r"discov|find|reveal|اكتشف", t):
        return "DISCOVERY"
    return "FLOW"


def _emotion(text: str) -> str:
    for pattern, emo in EMOTION:
        if re.search(pattern, text, re.IGNORECASE):
            return emo
    return "neutral"


def _info_type(text: str) -> str:
    for pattern, kind in INFO_TYPE:
        if re.search(pattern, text, re.IGNORECASE):
            return kind
    return "STATEMENT"


def direct_sentence(text: str, state: str = "EXPLANATION",
                    index: int = 0) -> dict:
    """Direct one sentence/idea into a full visual plan record. Pure."""
    state = state.upper() if state.upper() in STATES else "EXPLANATION"
    cat = _metaphor_category(text)
    strategies = METAPHORS[cat]
    return {
        "idea": text[:160],
        "intent": cat.lower(),
        "emotion": _emotion(text),
        "info_type": _info_type(text),
        "visual_opportunity": strategies[index % len(strategies)],
        "visual_metaphor": cat,
        "shot_type": ("close_up" if state in ("HOOK", "STATISTIC")
                      else "medium" if state in ("EXPLANATION", "EXAMPLE")
                      else "wide"),
        "asset_type": ("broll_dynamic" if state in ("HOOK", "ESCALATION")
                       else "procedural_graphic"
                       if _info_type(text) == "STATISTIC" else "broll"),
        "motion": ("hard cuts" if state == "HOOK" else "push"
                   if state in ("PAYOFF", "ENDING") else "hold"),
        "typography": ("keyword_emphasis" if _info_type(text) in
                        ("TECH_TERM", "STATISTIC") else "headline"),
        "sfx": ("sting" if state in ("HOOK", "STATISTIC") else
                "transition_tick" if state == "PROCESS" else "none"),
        "music_state": ("build" if state in ("ESCALATION", "HOOK")
                        else "resolve" if state in ("PAYOFF", "ENDING")
                        else "bed"),
        "transition_intent": ("hard cut" if state != "ENDING" else "fade"),
        "camera": ("slow_push" if state in ("PAYOFF", "ENDING")
                   else "static_or_cuts"),
        "state": state,
    }


def direct_script(sentences: list, states: list | None = None) -> list[dict]:
    """Direct a whole script. states[i] assigns story grammar. Pure."""
    states = states or []
    return [direct_sentence(
        s if isinstance(s, str) else s.get("text", ""),
        states[i] if i < len(states) else "EXPLANATION", i)
        for i, s in enumerate(sentences)]


def arc_for_duration(total_s: float) -> list[str]:
    """Short-form arc: HOOK -> DEVELOPMENT -> ESCALATION -> PAYOFF -> ENDING."""
    if total_s < 45:
        return ["HOOK", "EXPLANATION", "PAYOFF", "ENDING"]
    return ["HOOK", "SETUP", "PROBLEM", "EXPLANATION", "ESCALATION",
            "PAYOFF", "ENDING"]
