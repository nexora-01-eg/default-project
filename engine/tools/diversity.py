"""Diversity Memory + pre-render creative planning (Planner Intelligence 3).

Moves repetition control from post-render review into pre-render
planning: memory tracks what was used, budget scales with production
size, validator inspects the whole plan, repair fixes the plan (never
renders a bad one), ranking blends relevance with diversity contribution.

Deterministic: sorted ids, no wall-clock, explicit seed recorded.
Semantic relevance is never sacrificed for diversity: an irrelevant
asset is never selected; a highly relevant repeat may stand with a
recorded reason.
"""
from __future__ import annotations

import math

VERSION = "3.0.0"

DIMENSIONS = ("asset", "asset_category", "shot_type", "composition",
              "camera", "motion", "transition", "typography", "graphics",
              "visual_metaphor", "color_treatment", "sfx", "music_state",
              "spatial_position", "visual_direction")

RELATIONS = ("CONTINUE", "CONTRAST", "ZOOM_IN", "ZOOM_OUT", "CAUSE",
             "EFFECT", "QUESTION", "ANSWER", "BEFORE", "AFTER", "EXAMPLE",
             "DETAIL", "SUMMARY", "CALLBACK", "RESET")

ESCALATION = ("INTRO", "DEVELOPMENT", "ESCALATION", "PEAK", "PAYOFF",
              "ENDING")
ESCALATION_INTENSITY = {"INTRO": 0.2, "DEVELOPMENT": 0.45, "ESCALATION": 0.7,
                        "PEAK": 1.0, "PAYOFF": 0.4, "ENDING": 0.15}


class DiversityMemory:
    """Deterministic usage memory across one production plan."""

    def __init__(self, seed: int = 7):
        self.seed = seed
        self.uses: dict[str, dict[str, list[int]]] = {}
        self.shots: list[dict] = []

    def record(self, index: int, shot: dict) -> None:
        dims = {d: str(shot.get(d, shot.get(_ALIASES.get(d, d), "")))
                for d in DIMENSIONS}
        self.shots.append({"index": index, "dims": dims,
                           "callback": shot.get("callback")})
        for dim, val in dims.items():
            if val:
                self.uses.setdefault(dim, {}).setdefault(val, []).append(
                    index)
        combo = f"{dims.get('camera', '')}+{dims.get('composition', '')}"
        if combo.strip("+"):
            self.uses.setdefault("__combo__", {}).setdefault(
                combo, []).append(index)

    def count(self, dim: str, value: str) -> int:
        return len(self.uses.get(dim, {}).get(str(value), []))

    def last_used(self, dim: str, value: str, now: int) -> int | None:
        hist = self.uses.get(dim, {}).get(str(value), [])
        past = [i for i in hist if i < now]
        return (now - max(past)) if past else None

    def state(self) -> dict:
        return {"version": VERSION, "seed": self.seed,
                "shots": len(self.shots)}


_ALIASES = {"asset": "asset", "shot_type": "shot_type"}


def repetition_type(prev: dict, cand: dict) -> str | None:
    """Classify repetition between previous shot and candidate. Pure."""
    if cand.get("callback", {}).get("allowed"):
        return None
    if prev.get("asset") and prev["asset"] == cand.get("asset"):
        return "EXACT_REPETITION"
    if (prev.get("asset_category") and
            prev["asset_category"] == cand.get("asset_category") and
            prev.get("composition") == cand.get("composition")):
        return "NEAR_REPETITION"
    if (prev.get("shot_type") == cand.get("shot_type") and
            prev.get("composition") == cand.get("composition")):
        return "STRUCTURAL_REPETITION"
    if prev.get("motion") and prev["motion"] == cand.get("motion"):
        return "MOTION_REPETITION"
    if prev.get("camera") and prev["camera"] == cand.get("camera"):
        return "CAMERA_REPETITION"
    if prev.get("typography") and prev["typography"] == cand.get("typography"):
        return "TYPOGRAPHY_REPETITION"
    if (prev.get("visual_metaphor") and
            prev["visual_metaphor"] == cand.get("visual_metaphor")):
        return "METAPHOR_REPETITION"
    if prev.get("sfx") and prev["sfx"] == cand.get("sfx"):
        return "AUDIO_REPETITION"
    return None


def diversity_budget(total_s: float, n_shots: int,
                     density: str = "medium") -> dict:
    """Scale diversity requirements with production size. Pure."""
    dens = {"low": 0.7, "medium": 1.0, "high": 1.3}.get(density, 1.0)
    ask = max(2, round(math.sqrt(max(n_shots, 1)) * dens))
    return {"max_asset_reuse": max(1, ask // 2),
            "min_distinct_motions": min(n_shots, max(2, ask)),
            "min_distinct_cameras": min(n_shots, max(2, ask - 1)),
            "min_distinct_metaphors": min(n_shots, max(2, ask - 1)),
            "hook_min_cuts": 3 if total_s >= 20 else 2,
            "window": 5}


def validate_creative_plan(shots: list[dict], total_s: float,
                           budget: dict | None = None) -> dict:
    """Pre-render plan validation -> PASS/WARNING/FAIL + findings. Pure."""
    budget = budget or diversity_budget(
        total_s, len([s for s in shots if s.get("kind", "clip") == "clip"]))
    findings = []
    clips = [s for s in shots if s.get("kind", "clip") == "clip"]

    def add(shot, dim, ev, sev, fix, safe):
        findings.append({"shot_id": shot.get("shot_id", "?"), "dimension": dim,
                         "evidence": ev, "severity": sev,
                         "suggested_correction": fix,
                         "auto_repairable": safe})

    assets = [s.get("asset") for s in clips if s.get("asset")]
    reuse = len(assets) - len(set(assets))
    if reuse > budget["max_asset_reuse"]:
        add({}, "asset", f"reuse={reuse} > {budget['max_asset_reuse']}",
            "FAIL", "replace repeats with distinct matches", True)
    elif reuse > 0:
        add({}, "asset", f"reuse={reuse}", "WARNING",
            "prefer unused matches", True)
    for dim, key in (("motion", "min_distinct_motions"),
                     ("camera", "min_distinct_cameras"),
                     ("visual_metaphor", "min_distinct_metaphors")):
        vals = {str(s.get(dim, "")) for s in clips if s.get(dim)}
        if len(vals) < budget[key] and len(clips) >= budget[key]:
            add({}, dim, f"distinct={len(vals)} < {budget[key]}", "WARNING",
                f"alternate {dim}", True)
    early = [s for s in shots if s.get("start", 99) < 5.0]
    if len(early) < budget["hook_min_cuts"]:
        add({}, "hook", f"{len(early)} shots <5 s",
            "FAIL", "split opening into quick cuts", True)
    for s in clips:
        dur = round(s.get("end", 0) - s.get("start", 0), 2)
        if dur > 20:
            add(s, "pacing", f"{dur}s hold", "FAIL", "split shot", True)
        if not s.get("asset") and s.get("kind", "clip") == "clip":
            add(s, "asset", "no asset selected", "FAIL",
                "match or procedural card", True)
        texts = s.get("texts", [])
        if len(texts) > 2:
            add(s, "text", f"{len(texts)} layers", "FAIL", "demote body",
                True)
    ends = [s.get("end", 0) for s in shots]
    if ends and total_s - max(ends) > 3.0:
        add({}, "ending", "dead tail", "FAIL", "trim tail", True)
    # visual escalation: motion intensity should rise then resolve
    seq = [float(s.get("intensity", 0.5)) for s in clips]
    if len(seq) >= 4 and max(seq) == seq[0]:
        add({}, "escalation", "peak at opening", "WARNING",
            "save peak for payoff", False)
    verdict = ("FAIL" if any(f["severity"] == "FAIL" for f in findings)
               else "WARNING" if findings else "PASS")
    return {"verdict": verdict, "findings": findings, "budget": budget}


def rank_candidates(cands: list[dict], memory: DiversityMemory, now: int,
                    window: int = 5) -> list[dict]:
    """Blend relevance with diversity contribution. Pure + deterministic.

    Each candidate: {id, relevance 0..1, dims{...}, acceptable bool}.
    Unacceptable (irrelevant) candidates never win. A relevant repeat may
    stand when alternatives are worse — with recorded reason.
    """
    scored = []
    for c in sorted(cands, key=lambda x: x["id"]):
        if not c.get("acceptable", True):
            continue
        penalty = 0.0
        reasons = []
        for dim in DIMENSIONS:
            val = str(c.get("dims", {}).get(dim, ""))
            if not val:
                continue
            gap = memory.last_used(dim, val, now)
            if gap is not None and gap <= window:
                w = 0.06 if dim in ("asset", "shot_type", "motion",
                                    "camera") else 0.02
                penalty += w * (window + 1 - gap)
                reasons.append(f"{dim}={val} used {gap} ago")
        total = round(c.get("relevance", 0.5) - penalty, 4)
        scored.append({"id": c["id"], "score": total,
                       "relevance": c.get("relevance", 0.5),
                       "penalty": round(penalty, 4),
                       "reasons": reasons or ["topical fit"]})
    scored.sort(key=lambda r: (-r["score"], r["id"]))
    return scored


def repair_plan(shots: list[dict], findings: list[dict],
                memory: DiversityMemory) -> dict:
    """Repair safe findings pre-render. Returns {shots, repairs[]}. Pure."""
    out, repairs = [], []
    for s in shots:
        cur = dict(s)
        for f in findings:
            if f.get("shot_id") not in (cur.get("shot_id"),) and \
                    f.get("shot_id"):
                continue
            if not f.get("auto_repairable"):
                continue
            dim = f["dimension"]
            if dim == "asset" and not cur.get("asset"):
                cur["asset"] = "CARD:procedural"
                cur["reason"] = "no match -> procedural card"
                repairs.append({"shot": cur.get("shot_id"), "fix": dim,
                                "to": "CARD:procedural"})
            elif dim in ("motion", "camera", "typography"):
                alts = {"motion": "HOLD", "camera": "static",
                        "typography": "headline"}
                if cur.get(dim) and memory.count(dim, cur[dim]) > 0:
                    cur[dim] = alts[dim]
                    repairs.append({"shot": cur.get("shot_id"), "fix": dim,
                                    "to": alts[dim]})
        out.append(cur)
    return {"shots": out, "repairs": repairs}


RANK_CONFIG_DEFAULT = {
    "semantic_floor_ratio": 0.85,
    "semantic_floor_delta": 0.15,
    "minimum_diversity_gain": 0.05,
    "maximum_semantic_tradeoff": 0.15,
}

_PENALTY_W = {"asset": 0.06, "shot_type": 0.06, "motion": 0.06,
              "camera": 0.06}


def _penalty_for(dims: dict, memory: "DiversityMemory", now: int,
                 window: int) -> tuple[float, list[str]]:
    penalty, hits = 0.0, []
    for dim, val in dims.items():
        val = str(val or "")
        if not val:
            continue
        gap = memory.last_used(dim, val, now)
        if gap is not None and gap <= window:
            w = _PENALTY_W.get(dim, 0.02)
            penalty += w * (window + 1 - gap)
            hits.append(dim)
    return round(penalty, 4), hits


def diversity_contribution(dims: dict, memory: "DiversityMemory", now: int,
                           window: int = 5) -> dict:
    """Deterministic novelty breakdown per dimension. Pure."""
    parts = {}
    for dim in ("asset", "shot_type", "composition", "motion", "camera",
                "visual_metaphor", "typography"):
        val = str(dims.get(dim, "") or "")
        if not val:
            parts[dim] = 0.0
            continue
        gap = memory.last_used(dim, val, now)
        if gap is None:
            parts[dim] = 1.0
        elif gap > window:
            parts[dim] = 0.5
        else:
            parts[dim] = round(max(0.0, (gap - 1) / max(window - 1, 1)), 3)
    total = round(sum(parts.values()) / len(parts), 3)
    return {"parts": parts, "total": total}


def rank_relative(cands: list[dict], memory: "DiversityMemory", now: int,
                  window: int = 5, config: dict | None = None,
                  context: dict | None = None) -> dict:
    """Relative-floor ranking with explicit keep/swap decision. Pure.

    1 leader (max relevance) -> 2 floor -> 3 filter -> 4 utility ->
    5 compare -> 6 record. Semantic acceptability first, then diversity.
    Returns {ranked[], decision{...}, floor, leader}.
    """
    cfg = dict(RANK_CONFIG_DEFAULT)
    cfg.update(config or {})
    context = context or {}
    pool = sorted([dict(c) for c in cands if c.get("acceptable", True)],
                  key=lambda x: x["id"])
    if not pool:
        return {"ranked": [], "floor": 0.0, "leader": None,
                "decision": {"decision": "NO_ACCEPTABLE_ALTERNATIVE",
                             "reason": "no acceptable candidates"}}
    leader = max(pool, key=lambda c: (c.get("relevance", 0.0), c["id"]))
    lrel = float(leader.get("relevance", 0.0))
    floor = round(max(cfg["semantic_floor_ratio"] * lrel,
                      lrel - cfg["semantic_floor_delta"]), 4)
    eligible = [c for c in pool
                if float(c.get("relevance", 0.0)) >= floor
                and (lrel - float(c.get("relevance", 0.0)))
                <= cfg["maximum_semantic_tradeoff"]]
    if leader not in eligible:
        eligible = [leader] + eligible
    scored = []
    for c in eligible:
        pen, hits = _penalty_for(c.get("dims", {}), memory, now, window)
        util = round(float(c.get("relevance", 0.0)) - pen, 4)
        contrib = diversity_contribution(c.get("dims", {}), memory, now,
                                         window)
        scored.append({"id": c["id"],
                       "relevance": float(c.get("relevance", 0.0)),
                       "penalty": pen, "utility": util,
                       "contribution": contrib["total"],
                       "hit_dims": hits})
    scored.sort(key=lambda r: (-r["utility"], -r["relevance"], r["id"]))
    # tie-break prefers the leader (relevance-first on ties)
    top_util = scored[0]["utility"]
    tied = [r for r in scored if r["utility"] == top_util]
    winner = next((r for r in tied if r["id"] == leader["id"]), tied[0])
    if winner["id"] == leader["id"]:
        gain = 0.0
        if len(eligible) <= 1:
            dec, why = ("KEEP_BECAUSE_ALTERNATIVES_TOO_WEAK",
                        "no alternative above relative floor")
        elif context.get("callback"):
            dec, why = ("CALLBACK_ALLOWED",
                        "explicit intentional callback")
        elif context.get("coherence_keep"):
            dec, why = ("KEEP_FOR_COHERENCE", context["coherence_keep"])
        else:
            dec = "KEEP_BEST_SEMANTIC"
            alt_gain = max(
                [r["utility"] - winner["utility"] for r in scored
                 if r["id"] != winner["id"]], default=0.0)
            why = ("best semantic score stands; best alternative gain "
                   f"{round(alt_gain, 4)} < "
                   f"{cfg['minimum_diversity_gain']}")
            gain = round(alt_gain, 4)
        decision = {"decision": dec, "original": leader["id"],
                    "replacement": leader["id"], "semantic_delta": 0.0,
                    "diversity_gain": gain, "reason": why}
    else:
        gain = round(winner["utility"] - next(
            r["utility"] for r in scored if r["id"] == leader["id"]), 4)
        if gain < cfg["minimum_diversity_gain"]:
            decision = {"decision": "KEEP_BEST_SEMANTIC",
                        "original": leader["id"],
                        "replacement": leader["id"], "semantic_delta": 0.0,
                        "diversity_gain": gain,
                        "reason": "diversity gain below minimum; "
                                  "semantic leader stands"}
            winner = next(r for r in scored if r["id"] == leader["id"])
        else:
            lpen = {d for d in next(
                r["hit_dims"] for r in scored if r["id"] == leader["id"])}
            wpen = set(winner["hit_dims"])
            relieved = sorted(lpen - wpen)
            dim = (relieved[0].upper() if relieved else "DIVERSITY")
            decision = {"decision": f"SWAP_FOR_{dim}_VARIETY",
                        "original": leader["id"],
                        "replacement": winner["id"],
                        "semantic_delta": round(winner["relevance"] - lrel,
                                                4),
                        "diversity_gain": gain,
                        "reason": ("semantic score above relative floor "
                                   "while relieving "
                                   f"{','.join(relieved) or 'general'} "
                                   "repetition")}
    return {"ranked": scored, "floor": floor, "leader": leader["id"],
            "decision": decision}


def select_motion(appropriate: list[str], memory: "DiversityMemory", now: int,
                  story_state: str = "", window: int = 5) -> dict:
    """Planner-owned motion choice: appropriateness first, then variety.

    May return NONE when the list is empty. Never rotates mechanically:
    a repeated motion wins only when alternatives are worse. Pure.
    """
    if not appropriate:
        return {"motion": "NONE",
                "reason": "no motion appropriate for this beat"}
    cands = [{"id": m, "relevance": 0.9 - 0.05 * i,
              "dims": {"motion": m}, "acceptable": True}
             for i, m in enumerate(dict.fromkeys(appropriate))]
    res = rank_relative(cands, memory, now, window)
    dec = res["decision"]
    if dec["decision"].startswith("SWAP"):
        reason = (f"motion variety: {dec['original']} -> "
                  f"{dec['replacement']} ({dec['reason']})")
    else:
        reason = (f"kept {res['leader']} for {story_state or 'beat'}; "
                  f"{dec['reason']}")
    return {"motion": res["ranked"][0]["id"] if res["ranked"] else "NONE",
            "reason": reason, "decision": dec["decision"]}


def select_camera(appropriate: list[str], composition: str,
                  memory: "DiversityMemory", now: int,
                  window: int = 5) -> dict:
    """Planner-owned camera choice, composition-aware. Pure."""
    if not appropriate:
        return {"camera": "static",
                "reason": "no camera move appropriate", "decision": "NONE"}
    cands = [{"id": c, "relevance": 0.9 - 0.05 * i,
              "dims": {"camera": c, "composition": composition},
              "acceptable": True}
             for i, c in enumerate(dict.fromkeys(appropriate))]
    res = rank_relative(cands, memory, now, window)
    dec = res["decision"]
    return {"camera": res["ranked"][0]["id"] if res["ranked"] else "static",
            "reason": f"camera for {composition}: {dec['reason']}",
            "decision": dec["decision"]}


def combo_repeat(memory: "DiversityMemory", camera: str, composition: str,
                 now: int, window: int = 5) -> dict:
    """Warn on push+center style combo repetition. Pure."""
    key = f"{camera}+{composition}"
    hist = memory.uses.get("camera", {})
    _ = hist
    combo_hist = memory.uses.get("__combo__", {}).get(key, [])
    run = 0
    for i in range(now - 1, -1, -1):
        if i in combo_hist:
            run += 1
        else:
            break
    return {"combo": key, "consecutive": run,
            "warn": run >= 2,
            "reason": f"{key} used {run}x consecutively" if run >= 2 else ""}


def plan_report(decisions: list[dict]) -> dict:
    """Inspectable plan-level decision report. Pure."""
    swaps = [d for d in decisions if d.get("decision", "").startswith("SWAP")]
    keeps = [d for d in decisions if d.get("decision", "").startswith("KEEP")
             or d.get("decision") in ("CALLBACK_ALLOWED", "REPEAT_ALLOWED")]
    return {"candidate_decisions": len(decisions),
            "swaps": len(swaps), "keeps": len(keeps),
            "by_type": sorted({d.get("decision", "?") for d in decisions}),
            "decisions": decisions}


def rhythm_profile(durations: list[float],
                   intensities: list[float]) -> dict:
    """Lightweight rhythm model: levels + reset advice. Pure."""
    def level(x, lo=3.0, hi=7.0):
        return "LOW" if x < lo else "HIGH" if x > hi else "MEDIUM"
    dur_l = [level(d) for d in durations]
    run = 1
    for i in range(1, len(dur_l)):
        run = run + 1 if dur_l[i] == dur_l[i - 1] == "HIGH" else 1
    return {"durations": dur_l,
            "intensities": ["PEAK" if v >= 0.9 else
                            "HIGH" if v >= 0.65 else
                            "MEDIUM" if v >= 0.35 else "LOW"
                            for v in intensities],
            "reset_advised": run >= 4,
            "high_run": run}


def relation_to(prev_state: str, cur_state: str) -> str:
    """Shot-to-shot relationship from story states. Pure."""
    if prev_state == cur_state:
        return "CONTINUE"
    table = {("HOOK", "PROBLEM"): "QUESTION", ("PROBLEM", "EXPLANATION"): "CAUSE",
             ("EXPLANATION", "EXAMPLE"): "EXAMPLE",
             ("EXAMPLE", "PAYOFF"): "EFFECT",
             ("PAYOFF", "ENDING"): "SUMMARY"}
    if (prev_state, cur_state) in table:
        return table[(prev_state, cur_state)]
    if cur_state == "ENDING":
        return "SUMMARY"
    if prev_state == "ENDING":
        return "RESET"
    return "CONTRAST"


def escalation_map(states: list[str], total_s: float) -> list[dict]:
    """Map story states onto the escalation curve. Pure."""
    order = ["HOOK", "SETUP", "PROBLEM", "CONTEXT", "EXPLANATION",
             "CONTRAST", "EXAMPLE", "STATISTIC", "PROCESS", "ESCALATION",
             "QUESTION", "SURPRISE", "INSIGHT", "PAYOFF", "CTA", "ENDING"]
    phase_of = {"HOOK": "INTRO", "SETUP": "DEVELOPMENT",
                "PROBLEM": "DEVELOPMENT", "CONTEXT": "DEVELOPMENT",
                "EXPLANATION": "DEVELOPMENT", "CONTRAST": "ESCALATION",
                "EXAMPLE": "ESCALATION", "STATISTIC": "PEAK",
                "PROCESS": "ESCALATION", "ESCALATION": "ESCALATION",
                "QUESTION": "DEVELOPMENT", "SURPRISE": "PEAK",
                "INSIGHT": "PAYOFF", "PAYOFF": "PAYOFF", "CTA": "PAYOFF",
                "ENDING": "ENDING"}
    span = total_s / max(len(states), 1)
    return [{"state": s,
             "phase": phase_of.get(s, "DEVELOPMENT"),
             "intensity": ESCALATION_INTENSITY[phase_of.get(
                 s, "DEVELOPMENT")],
             "start": round(i * span, 2), "end": round((i + 1) * span, 2)}
            for i, s in enumerate(states) if s in order or True]
