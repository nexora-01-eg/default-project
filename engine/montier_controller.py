"""Public, deterministic Codex-to-Al-Montier production controller.

This deliberately exposes contracts and artifacts, not private renderer calls.
It does not invent missing production capabilities.
"""
from __future__ import annotations

import json
from pathlib import Path

REQUIRED_PLAN_KEYS = {
    "project", "target", "voice", "narration", "scenes", "shots", "assets",
    "captions", "motion", "transitions", "audio", "qc", "review", "acceptance_criteria",
}
PHASES = ("analyze", "plan", "storyboard", "assets", "voice", "captions", "motion",
          "audio", "render", "review", "repair", "final_report")


class ContractError(ValueError):
    pass


def load_contract(path: str | Path) -> dict:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    missing = sorted(REQUIRED_PLAN_KEYS - payload.keys())
    if missing:
        raise ContractError("production contract missing: " + ", ".join(missing))
    target = payload["target"]
    if target.get("width") != 1080 or target.get("height") != 1920 or target.get("fps") != 30:
        raise ContractError("this production contract requires 1080x1920 at 30 FPS")
    if not isinstance(payload["shots"], list) or not payload["shots"]:
        raise ContractError("contract must contain at least one shot")
    return payload


def inspect_contract(path: str | Path) -> dict:
    plan = load_contract(path)
    starts = [float(s["start"]) for s in plan["shots"]]
    ends = [float(s["end"]) for s in plan["shots"]]
    return {"status": "VALID", "schema": plan.get("schema_version"),
            "project": plan["project"]["id"], "shot_count": len(plan["shots"]),
            "duration_s": round(max(ends) - min(starts), 3),
            "voice_status": plan["voice"]["status"], "phases": list(PHASES)}


def checkpoint(project_dir: str | Path, phase: str, status: str, detail: dict) -> Path:
    if phase not in PHASES:
        raise ContractError(f"unknown controller phase: {phase}")
    root = Path(project_dir)
    state_path = root / "controller_state.json"
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {"phases": []}
    state["phases"].append({"phase": phase, "status": status, "detail": detail})
    state["current_phase"] = phase
    state["status"] = status
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    return state_path
