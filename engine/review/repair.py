"""Phase 26 — repair routing loop (planning only, additive).

EXECUTE -> REVIEW -> FAIL -> CLASSIFY -> ROUTE -> REPLAN -> (render gated)
-> REVIEW AGAIN. This module classifies independent-review findings and
routes them to responsible subsystems with a deterministic repair plan and
bounded attempts. It never rerenders (ffmpeg-gated) and never fabricates a
PASS: after MAX attempts the project is BLOCKED_REQUIRES_HUMAN_REVIEW.
"""
from __future__ import annotations

from engine.core.project_store import load_project, project_dir

REPAIR_VERSION = "1.0.0"
ENGINE_TAG = "phase26-1.0"
MAX_AUTOMATIC_REPAIR_ATTEMPTS = 2

ROUTES = {
    "captions": "caption subsystem (Phase 14: re-segment/re-map/re-approve)",
    "editing": "editing subsystem (Phase 8/10: re-decide EDL, re-validate)",
    "visual": "asset subsystem (Arsenal-X: replace/re-verify visual asset)",
    "audio": "audio subsystem (Phase 3: re-analyze, re-check sync)",
    "technical": "rendering subsystem (Phase 9/13: re-render, re-QC)",
    "provenance": "approval subsystem (re-approve with valid bindings)",
    # Creative-director routes (additive; same generic planning applies).
    "BAD_ASSET": "asset planner (Arsenal-X: replace with verified match)",
    "WEAK_SHOT_SEQUENCE": "director (re-plan shots for the scene)",
    "STATIC_PACING": "timeline editor (split shots, vary rhythm)",
    "CAPTION_OVERLOAD": "caption system (headlines only, demote body)",
    "WEAK_MOTION": "director motion vocabulary (motivated moves/fades)",
    "AUDIO_BALANCE": "audio subsystem (per-scene gains, fades)",
    "VISUAL_INCONSISTENCY": "asset selection (coherent set, resolution floor)",
    # Visual-production-2.0 routes (additive; reviewer2 issue names).
    "MOTION_TOO_STATIC": "motion system (CAMERA_PUSH refinance, strength 0.12)",
    "TEXT_OVERLOAD": "typography rules (<=2 layers, demote body)",
    "ASSET_REPETITION": "asset matcher (replace repeats)",
    "AUDIO_CLIPPING_RISK": "audio subsystem (GAIN_REDUCE + safety)",
    "AUDIO_TOO_QUIET": "audio subsystem (GAIN_RAISE, watch ceiling)",
    "BAD_CAPTION_TIMING": "caption system (phrase-level fallback)",
    "SHOT_OVERLAP": "timeline editor (re-time)",
    "DEAD_SECTION": "timeline editor (remove)",
    "PACING_TOO_SLOW": "timeline editor (split shot)",
    "NO_ASSET": "asset matcher (match or procedural graphic)",
    "EXCESSIVE_TEXT": "typography rules (demote to keyword)",
    "REPETITIVE_MOTION": "motion system (alternate primitive)",
    "WEAK_COMPOSITION": "composition rules (reframe)",
    "VISUAL_HIERARCHY": "typography rules (single focal)",
    "STYLE_FONT": "style contract (unify family)",
    "STYLE_LAYERS": "style contract (demote)",
    "STYLE_MOTION": "style contract (replace primitive)",
}

# Visual-production-2.0 repair budget (new loop only; legacy constant kept).
MAX_V2_REPAIR_ROUNDS = 3


class RepairError(RuntimeError):
    """Repair planning failure."""


def classify_failure(review_payload: dict) -> list[dict]:
    """Map failing/review checks to responsible subsystems (deterministic)."""
    routed = []
    for c in review_payload.get("checks", []):
        name = str(c.get("name", ""))
        detail = str(c.get("detail", ""))
        status = detail.split(" | ", 1)[0]
        if status == "PASS":
            continue
        category = name.split(":", 1)[0] if ":" in name else "technical"
        subsystem = ROUTES.get(category, "human operator (unmapped category)")
        routed.append({"check": name, "status": status,
                       "subsystem": subsystem, "evidence": detail})
    routed.sort(key=lambda r: (r["subsystem"], r["check"]))
    return routed


def plan_repair(project_id: str, review_payload: dict,
                max_attempts: int = MAX_AUTOMATIC_REPAIR_ATTEMPTS) -> dict:
    """Deterministic repair plan with attempt accounting."""
    project = load_project(project_id)
    pid = project.id
    state_path = project_dir(pid) / "qc" / "repair_state.json"
    import json
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        state = {"attempts_used": 0}
    routed = classify_failure(review_payload)
    verdict = review_payload.get("verdict", "REVIEW")
    if verdict == "PASS" or not routed:
        return {"project": pid, "action": "NONE",
                "reason": "review is clean", "attempts_used": state["attempts_used"],
                "max_attempts": max_attempts, "routes": []}
    if state["attempts_used"] >= max_attempts:
        return {"project": pid, "action": "BLOCKED_REQUIRES_HUMAN_REVIEW",
                "reason": f"attempt budget exhausted ({max_attempts})",
                "attempts_used": state["attempts_used"],
                "max_attempts": max_attempts, "routes": routed}
    actions = []
    for r in routed:
        if r["status"] == "FAIL":
            actions.append({"kind": "REPLAN", "target": r["check"],
                            "handler": r["subsystem"], "reason": r["evidence"]})
        else:
            actions.append({"kind": "REVIEW_AGAIN", "target": r["check"],
                            "handler": r["subsystem"], "reason": r["evidence"]})
    return {"project": pid, "action": "REPAIR_PLANNED",
            "attempts_used": state["attempts_used"],
            "max_attempts": max_attempts, "routes": routed,
            "actions": actions,
            "note": "render execution is ffmpeg-gated; operator applies actions"}


def record_attempt(project_id: str) -> dict:
    """Increment the attempt counter (called when a repair cycle runs)."""
    import json
    project = load_project(project_id)
    pid = project.id
    state_path = project_dir(pid) / "qc" / "repair_state.json"
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        state = {"attempts_used": 0}
    state["attempts_used"] = int(state.get("attempts_used", 0)) + 1
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")
    return state


CREATIVE_ROUTES = {
    "hook": "WEAK_SHOT_SEQUENCE",
    "scene_": "WEAK_SHOT_SEQUENCE",
    "caption_density": "CAPTION_OVERLOAD",
    "ending": "WEAK_SHOT_SEQUENCE",
    "repetition": "BAD_ASSET",
    "asset_quality": "BAD_ASSET",
    "asset_relevance": "BAD_ASSET",
    "motion": "WEAK_MOTION",
    "audio_states": "AUDIO_BALANCE",
}


def route_creative(creative_report: dict) -> list[dict]:
    """Route creative-review FAIL/REVIEW checks to subsystems (pure).

    Matches check names against CREATIVE_ROUTES prefixes; unknown checks
    go to a human operator (never silently dropped).
    """
    routed = []
    for c in creative_report.get("checks", []):
        if c.get("verdict") == "PASS":
            continue
        name = str(c.get("name", ""))
        key = next((k for k in CREATIVE_ROUTES if name.startswith(k)),
                   None)
        route = CREATIVE_ROUTES.get(key, "HUMAN_OPERATOR") if key \
            else "HUMAN_OPERATOR"
        subsystem = ROUTES.get(route, "human operator (unmapped category)")
        routed.append({"check": name, "status": c.get("verdict"),
                       "route": route, "subsystem": subsystem,
                       "evidence": c.get("evidence")})
    routed.sort(key=lambda r: (r["route"], r["check"]))
    return routed
