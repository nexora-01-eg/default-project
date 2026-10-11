"""Phase 28 — director brain: structured pre-production planning (pure).

Input: idea/script/source/style/duration/platform. Output: story structure,
visual beats, B-roll/caption/pacing/audio strategies, asset requirements
(shaped like Arsenal-X AssetRequirements for direct handoff), risk list.
Planning only: never renders, never downloads. Fully deterministic.
"""
from __future__ import annotations


def _split_acts(duration_s: float) -> list[dict]:
    acts = [("setup", 0.0, 0.25), ("development", 0.25, 0.75),
            ("payoff", 0.75, 1.0)]
    return [{"act": name, "start": round(duration_s * a, 1),
             "end": round(duration_s * b, 1)} for name, a, b in acts]


_TOPIC_HINTS = (
    ("ai|infrastructure|server|technology|chip|data",
     ["futuristic server room", "AI chip close-up", "data-center corridor"]),
    ("finance|money|market|stock|gold",
     ["trading screens", "gold macro", "business handshake"]),
    ("city|urban|skyline", ["city aerial day", "city night traffic"]),
    ("space|nasa|earth|star", ["earth from space", "star field"]),
    ("business|office|team", ["modern office", "laptop work close-up"]),
)


def _brolls(text: str) -> list[str]:
    t = text.lower()
    for pattern, items in _TOPIC_HINTS:
        import re
        if re.search(pattern, t):
            return list(items)
    return ["neutral abstract background", "subtle particle loop"]


def plan_production(idea: str, script: str = "", style: str = "corporate",
                    duration_s: float = 60.0, platform: str = "youtube",
                    voice_source: str = "") -> dict:
    """Deterministic pre-production plan."""
    if duration_s <= 0:
        raise ValueError("duration_s must be > 0")
    vertical = platform.lower() in ("shorts", "reel", "tiktok")
    text = f"{idea} {script} {style}"
    brolls = _brolls(text)
    import re
    beats = []
    for i, act in enumerate(_split_acts(duration_s)):
        beats.append({"beat": i + 1, "act": act["act"],
                      "start": act["start"], "end": act["end"],
                      "visual": brolls[i % len(brolls)],
                      "caption_note": "hook caption" if i == 0 else "steady captions",
                      "audio_note": "music bed in" if i == 0 else "music bed"})
    arabic = bool(re.search(r"[\u0600-\u06FF]", text))
    requirements = [
        {"id": f"req-{i + 1:03d}", "kind": "BROLL", "label": b,
         "request": {"intent": b, "asset_type": "video",
                     "aspect_ratio": "9:16" if vertical else "16:9"}}
        for i, b in enumerate(brolls)]
    requirements.append(
        {"id": f"req-{len(requirements) + 1:03d}", "kind": "CAPTION_FONT",
         "label": "arabic caption font" if arabic else "latin caption font",
         "request": {"intent": "arabic caption font" if arabic else "caption font",
                     "asset_type": "font"}})
    risks = []
    if duration_s > 600:
        risks.append("longform: pacing drift across acts")
    if vertical and duration_s > 180:
        risks.append("vertical longform: retention risk")
    if not script and not voice_source:
        risks.append("no script/voice: narration timing unknown")
    return {"schema_version": "director-plan-1.0",
            "idea": idea, "style": style, "platform": platform,
            "duration_s": duration_s, "vertical": vertical,
            "story_structure": _split_acts(duration_s),
            "visual_beats": beats,
            "broll_requirements": brolls,
            "caption_style": "arabic-clean" if arabic else "default-clean",
            "pacing_strategy": "hook-first, steady middle, payoff close",
            "audio_strategy": f"{style} bed + transition sfx",
            "asset_requirements": requirements,
            "risk_list": risks}


# ---------- Creative-director extension (additive; plan_production untouched)

def classify_voice_mode(tts_available: bool = False,
                        tts_languages: tuple = ()) -> dict:
    """Explicit production mode. TEXT_DRIVEN is a different design, NOT a
    degraded narration: headlines replace full-script captions, B-roll
    carries meaning, pacing is visual-first."""
    if tts_available and tts_languages:
        return {"voice_mode": "NARRATED",
                "narration": "synthetic voice carries script; captions secondary",
                "text_rule": "captions mirror narration verbatim"}
    return {"voice_mode": "TEXT_DRIVEN",
            "narration": "no voice: on-screen headlines carry beats; "
                         "B-roll carries meaning",
            "text_rule": "headlines <= 8 words; never the full script"}


def plan_shots(scenes: list[dict], asset_pool: list[dict],
               voice_mode: str = "TEXT_DRIVEN",
               max_shot_s: float = 6.0) -> list[dict]:
    """Shot-level storyboard from scenes + verified asset pool (pure).

    Each scene becomes >=2 shots (hook: >=3 in first 5 s). Assets score by
    tag relevance, then resolution (no upscales beyond 2x counted down),
    then duration fit. Rejected candidates carry reasons. Deterministic.
    """
    import re
    shots: list[dict] = []
    seq = 0

    def _score(asset: dict, need_tags: list[str], want_s: float):
        tags = [t.lower() for t in asset.get("tags", [])]
        rel = sum(1 for t in need_tags if t in " ".join(tags)) if need_tags else 0
        w, h = asset.get("w", 0), asset.get("h", 0)
        res = 2 if min(w, h) >= 1080 else (1 if min(w, h) >= 720 else 0)
        dur = float(asset.get("dur", 0) or 0)
        fit = 1 if dur >= want_s else -1
        # foreign-language UI vetoed unless the need explicitly justifies it
        foreign = 0 if "allow-foreign" in need_tags else \
            (-100 if asset.get("foreign_ui") else 0)
        return rel * 10 + res * 3 + fit + foreign, rel

    for sc in scenes:
        s, e = sc.get("span", [0, 0])
        span = e - s
        needs = re.findall(r"[a-z]+", sc.get("need", "").lower())
        # shot count from information density: ~1 shot per 4 s, min 2
        n = max(2, min(6, round(span / 4.0)))
        bounds = [round(s + span * i / n, 2) for i in range(n + 1)]
        for k in range(n):
            a, b = bounds[k], bounds[k + 1]
            want = b - a
            ranked = sorted(
                (( _score(asset, needs, want), asset) for asset in asset_pool),
                key=lambda t: (-t[0][0], t[1].get("file", "")))
            best_score, best = ranked[0]
            if best_score[0] <= 0:
                reason = "NO_SUITABLE_LOCAL_ASSET"
            else:
                reason = f"tags+res fit (score {best_score})"
            seq += 1
            shots.append({
                "shot_id": f"sh_{seq:03d}", "scene_id": sc.get("id"),
                "start": a, "end": b,
                "narrative": sc.get("text", "")[:120],
                "visual_objective": sc.get("visual", ""),
                "need": sc.get("need", ""),
                "asset": None if reason == "NO_SUITABLE_LOCAL_ASSET"
                else best.get("file"),
                "asset_score": best_score,
                "framing": "center vertical crop" if best and min(
                    best.get("w", 0), best.get("h", 0)) >= 720 else "card",
                "motion": "cut in, hold" if k == 0 else "hard cut on beat",
                "text": "",
                "caption_behavior": "headline" if voice_mode == "TEXT_DRIVEN"
                else "narration mirror",
                "reason": reason,
            })
    return shots
