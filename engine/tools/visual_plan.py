"""Visual storytelling engine (additive): narration -> shot intents.

Pipeline: narration segment -> concept keywords -> visual intent ->
shot type + asset requirement + motion language + graphic language +
audio accent + transition. Reuses director.plan_shots for storyboards
and the capability router for motion/graphic provider choice. Pure.
"""
from __future__ import annotations

import re

INTENTS = (
    ("repetitive|workload|team|squad|montage of work", "repetitive_task",
     "many quick cuts of hands-on work", "fast cuts", "PUNCH_IN"),
    ("analy|scan|data|detect|timeline|processing", "analysis",
     "scanning/data visual over footage", "push + overlay graphic", "CALLOUT"),
    ("automat|faster|rapid|seconds|workflow", "acceleration",
     "sequential operations at speed", "montage", "SPEED_RAMP"),
    ("human|person|hand|together|collaborat|decision|choice", "humanSubmit",
     "human presence with technology", "slow push", "LOWER_THIRD"),
    ("future|tomorrow|next|callback|closing", "payoff",
     "cinematic wide + callback visual", "deliberate hold", "TITLE_CARD"),
    ("hook|question|؟|\\?", "hook",
     "high-impact opener, >=3 shots in 5 s", "hard cuts", "HEADLINE"),
)

_DEFAULT = ("beat", "supporting visual that carries the line", "hard cut",
            "HEADLINE")


def concept_of(text: str) -> tuple[str, str, str, str]:
    """Map narration text -> (intent, visual, motion, graphic). Pure."""
    t = text.lower()
    for pattern, intent, visual, motion, graphic in INTENTS:
        if re.search(pattern, t):
            return intent, visual, motion, graphic
    return _DEFAULT


def plan_visual_beats(narration: list[dict],
                      asset_pool: list[dict] | None = None) -> list[dict]:
    """Enrich narration segments with visual intent + transition. Pure."""
    beats = []
    for i, seg in enumerate(narration):
        intent, visual, motion, graphic = concept_of(seg.get("text", ""))
        prev = beats[-1]["intent"] if beats else None
        transition = ("fade in" if i == 0 else
                      "hard cut" if intent != prev else "match rhythm")
        beats.append({"id": seg.get("id", f"n{i + 1}"),
                      "span": seg.get("span", [0.0, 0.0]),
                      "text": seg.get("text", ""), "intent": intent,
                      "visual": visual, "motion": motion,
                      "graphic": graphic, "transition": transition,
                      "audio_accent": ("sting" if intent == "hook"
                                       else "none")})
    return beats


def storyboard(narration: list[dict], asset_pool: list[dict],
               voice_mode: str = "TEXT_DRIVEN") -> list[dict]:
    """Shot-level storyboard via the existing director planner."""
    from engine.autonomy.director import plan_shots
    scenes = [{"id": s.get("id", f"n{i + 1}"),
               "span": s.get("span", [0.0, 0.0]),
               "text": s.get("text", ""),
               "need": s.get("need", ""),
               "visual": s.get("visual", "")}
              for i, s in enumerate(narration)]
    return plan_shots(scenes, asset_pool, voice_mode=voice_mode)


def plan_shots_diverse(narration: list[dict], asset_pool: list[dict],
                       voice_mode: str = "TEXT_DRIVEN",
                       seed: int = 7) -> dict:
    """Diversity-aware shot planning (additive; plan_shots untouched).

    Runs the base planner, then enforces diversity memory + budget +
    validation + planner-level repair BEFORE any rendering. Returns
    {shots, validation, repairs, memory, log} — fully deterministic.
    """
    from engine.tools import diversity as _dv
    base = storyboard(narration, asset_pool, voice_mode=voice_mode)
    total = round(max((s.get("end", 0) for s in base), default=0.0), 2)
    clips = [s for s in base]
    budget = _dv.diversity_budget(
        total, len(clips),
        "high" if total > 60 else "medium" if total > 30 else "low")
    mem, log, enriched = _dv.DiversityMemory(seed=seed), [], []
    by_file = {a.get("file"): a for a in asset_pool}
    for i, sh in enumerate(clips):
        fn = sh.get("asset")
        dims = {"asset": fn or "",
                "asset_category": ",".join(
                    (by_file.get(fn) or {}).get("tags", [])[:2]),
                "shot_type": "medium", "composition": "center",
                "camera": "hold", "motion": sh.get("motion", ""),
                "transition": "hard cut",
                "typography": sh.get("caption_behavior", "headline"),
                "graphics": "none", "visual_metaphor": sh.get("need", ""),
                "color_treatment": "uniform", "sfx": "none",
                "music_state": "bed", "spatial_position": "center",
                "visual_direction": sh.get("visual_objective", "")[:40]}
        cands, seen_cats = [], set()
        for a in sorted(asset_pool, key=lambda x: x.get("file", "")):
            tags = " ".join(a.get("tags", [])).lower()
            need = str(sh.get("need", "")).lower()
            rel = (sum(1 for t in need.split() if t and t in tags) /
                   max(len(need.split()), 1))
            if a.get("dur", 0) < (sh.get("end", 0) - sh.get("start", 0)):
                continue
            cands.append({"id": a["file"], "relevance": round(rel, 3),
                          "acceptable": rel > 0 or a["file"] == fn,
                          "dims": {"asset": a["file"],
                                   "asset_category": ",".join(
                                       a.get("tags", [])[:2]),
                                   "motion": dims["motion"],
                                   "camera": dims["camera"]}})
        res = _dv.rank_relative(cands, mem, i, budget["window"])
        ranked = res["ranked"]
        pick = ranked[0]["id"] if ranked else fn
        dec = dict(res["decision"])
        dec["shot"] = sh.get("shot_id")
        dec["floor"] = res["floor"]
        dec["leader"] = res["leader"]
        dec["contenders"] = len(ranked)
        log.append(dec)
        if pick != fn:
            log[-1]["base_pick"] = fn
        enriched.append(enrich_shot(dict(sh, asset=pick,
                                         reason="diversity-ranked")))
        mem.record(i, {"asset": pick,
                       "asset_category": ",".join(
                           (by_file.get(pick) or {}).get("tags", [])[:2]),
                       "shot_type": "medium", "composition": "center",
                       "camera": "hold", "motion": sh.get("motion", ""),
                       "transition": "hard cut",
                       "typography": sh.get("caption_behavior", "headline"),
                       "graphics": "none",
                       "visual_metaphor": sh.get("need", ""),
                       "color_treatment": "uniform", "sfx": "none",
                       "music_state": "bed", "spatial_position": "center",
                       "visual_direction": ""})
    validation = _dv.validate_creative_plan(
        [{"shot_id": s.get("shot_id"), "kind": "clip",
          "start": s.get("start"), "end": s.get("end"),
          "asset": s.get("asset"), "motion": s.get("motion"),
          "texts": []} for s in enriched], total, budget)
    fixed = _dv.repair_plan(
        [{"shot_id": s.get("shot_id"), "kind": "clip",
          "start": s.get("start"), "end": s.get("end"),
          "asset": s.get("asset"), "motion": s.get("motion"),
          "texts": []} for s in enriched],
        [f for f in validation["findings"] if f["auto_repairable"]], mem)
    return {"shots": enriched, "repaired": fixed["repairs"],
            "validation": validation, "budget": budget,
            "memory": mem.state(),
            "log": log, "planner_version": "visual_plan/3.0",
            "diversity_model_version": _dv.VERSION, "seed": seed}


def enrich_shot(shot: dict, direction: dict | None = None) -> dict:
    """Add Phase-I 2.0 fields to a director shot. Pure."""
    direction = direction or {}
    a, b = shot.get("start", 0.0), shot.get("end", 0.0)
    out = dict(shot)
    if isinstance(out.get("asset_score"), tuple):
        out["asset_score"] = list(out["asset_score"])
    out.update({
        "start_time": a, "end_time": b,
        "narrative_span": direction.get("idea", shot.get("narrative", "")),
        "semantic_goal": direction.get("intent", ""),
        "visual_goal": direction.get("visual_strategy",
                                     shot.get("visual_objective", "")),
        "shot_type": direction.get("shot_type", "medium"),
        "asset_requirement": shot.get("need", ""),
        "selected_asset": shot.get("asset"),
        "composition": {"subject": "center", "safe_text": True,
                        "hierarchy": "caption+keyword"},
        "camera": direction.get("camera", shot.get("motion", "")),
        "motion": {"primitive": "HOLD", "duration": round(b - a, 2)},
        "typography": {"mode": shot.get("caption_behavior", "headline")},
        "caption_mode": shot.get("caption_behavior", "headline"),
        "transition": "hard cut",
        "music_state": direction.get("music_state", "bed"),
        "sfx": direction.get("sfx", "none"),
        "confidence": ("HIGH_CONFIDENCE" if shot.get("asset") else
                       "LOW_CONFIDENCE"),
        "provenance": {"planner": "visual_plan.storyboard",
                       "reason": shot.get("reason", "")},
    })
    return out


def to_json_safe(obj):
    """Convert planner records to JSON-safe structures. Pure."""
    if isinstance(obj, tuple):
        return [to_json_safe(v) for v in obj]
    if isinstance(obj, list):
        return [to_json_safe(v) for v in obj]
    if isinstance(obj, dict):
        return {k: to_json_safe(v) for k, v in obj.items()}
    return obj


def attach_motion_camera(shots: list[dict], options: list[dict] | None = None,
                         seed: int = 7) -> tuple[list[dict], list[dict]]:
    """Planner-owned motion/camera per shot via selectors + shared memory.

    options[i] = {"motion": [...], "camera": [...], "composition": str,
    "state": str}. Returns (shots, decisions). Pure except no IO.
    """
    from engine.tools import diversity as _dv
    options = options or []
    mem = _dv.DiversityMemory(seed=seed)
    out, decisions = [], []
    for i, sh in enumerate(shots):
        opt = options[i] if i < len(options) else {}
        comp = opt.get("composition", "center")
        state = opt.get("state", "")
        mo = _dv.select_motion(opt.get("motion", ["hold"]), mem, i, state)
        mem.record(i, {"motion": mo["motion"]})
        ca = _dv.select_camera(opt.get("camera", ["static"]), comp, mem, i)
        mem.record(i, {"camera": ca["camera"], "composition": comp})
        dur = round(sh.get("end", 0) - sh.get("start", 0), 2)
        shot = dict(sh)
        shot["motion"] = {"type": mo["motion"],
                          "parameters": {"duration": dur},
                          "reason": mo["reason"], "source": "planner",
                          "decision": mo["decision"]}
        shot["camera"] = {"type": ca["camera"],
                          "parameters": {"composition": comp},
                          "reason": ca["reason"], "source": "planner",
                          "decision": ca["decision"]}
        shot["composition"] = comp
        out.append(shot)
        decisions.append({"shot": sh.get("shot_id"), "motion": mo,
                          "camera": ca})
    return out, decisions


def validate_shots(shots: list[dict]) -> list[dict]:
    """Shot-level validation. Returns issue dicts. Pure."""
    issues = []
    motions, files = [], []
    prev_end = 0.0
    for s in shots:
        a = s.get("start_time", s.get("start", 0))
        b = s.get("end_time", s.get("end", 0))
        dur = round(b - a, 2)
        sid = s.get("shot_id", "?")
        if a < prev_end - 0.01:
            issues.append({"issue": "SHOT_OVERLAP", "shot": sid,
                           "evidence": f"starts {a} before prev end"})
        if dur <= 0:
            issues.append({"issue": "DEAD_SECTION", "shot": sid,
                           "evidence": f"duration {dur}"})
        if dur > 20:
            issues.append({"issue": "PACING_TOO_SLOW", "shot": sid,
                           "evidence": f"{dur}s single shot"})
        if not s.get("selected_asset") and not s.get("asset"):
            issues.append({"issue": "NO_ASSET", "shot": sid,
                           "evidence": s.get("reason", "unmatched")})
        motions.append(str(s.get("motion")))
        if s.get("selected_asset") or s.get("asset"):
            files.append(s.get("selected_asset") or s.get("asset"))
        if (s.get("typography", {}) if isinstance(s.get("typography"), dict)
                else {}).get("mode") == "full_script":
            issues.append({"issue": "EXCESSIVE_TEXT", "shot": sid,
                           "evidence": "full script on screen"})
        prev_end = b
    if len(set(motions)) <= 1 and len(shots) > 3:
        issues.append({"issue": "REPETITIVE_MOTION", "shot": "all",
                       "evidence": f"1 motion pattern in {len(shots)} shots"})
    reuse = len(files) - len(set(files))
    if reuse > 2:
        issues.append({"issue": "REPETITIVE_SHOTS", "shot": "all",
                       "evidence": f"reuse={reuse}"})
    return issues
