"""Phase 27 — autonomous production controller (state machine + checkpoints).

Runs an ordered phase list with injected runners, persists a checkpoint
(state.json) after every phase, and resumes from the latest valid
checkpoint after a crash. Runners are injected so planning phases run
for real while render phases honestly report BLOCKED without ffmpeg.

Checkpoint: {phase, status, artifacts, decisions, failures, retries,
manifests}. Deterministic: no wall-clock inside phase decisions (only
logged timestamps in checkpoint metadata, excluded from comparisons).
"""
from __future__ import annotations

import time

from engine.core.project_store import load_project, project_dir

CONTROLLER_VERSION = "1.0.0"

TERMINAL = ("FINAL_PASS", "BLOCKED", "BLOCKED_REQUIRES_HUMAN_REVIEW",
            "FAILED")


def _state_path(project_id: str):
    return project_dir(project_id) / "autonomy" / "state.json"


def _read(path):
    import json
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _write(path, payload):
    import json
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False),
                   encoding="utf-8")
    tmp.replace(path)


def run_pipeline(project_id: str, phases: list[str],
                 runners: dict, resume: bool = True) -> dict:
    """Run phases in order. Each runner(pid, state) returns a phase result
    dict with at least {"status": ...}. Unknown runner -> BLOCKED."""
    project = load_project(project_id)
    pid = project.id
    spath = _state_path(pid)
    state = _read(spath) if resume else None
    if not isinstance(state, dict) or state.get("controller_version") != \
            CONTROLLER_VERSION:
        state = {"controller_version": CONTROLLER_VERSION, "project": pid,
                 "phases": [], "status": "RUNNING", "retries": {},
                 "decisions": [], "failures": [], "manifests": {}}
    done = {p["phase"] for p in state["phases"] if p.get("status") == "OK"}
    for phase in phases:
        if phase in done:
            continue
        runner = runners.get(phase)
        started = round(time.time(), 3)
        if runner is None:
            result = {"status": "BLOCKED",
                      "reason": f"no runner registered for phase {phase}"}
        else:
            try:
                result = dict(runner(pid, state))
            except Exception as exc:  # failure isolation per phase
                result = {"status": "FAILED",
                          "reason": f"{type(exc).__name__}: {exc}"}
        result.setdefault("status", "FAILED")
        entry = {"phase": phase, "status": "OK"
                 if result["status"] in ("OK", "FINAL_PASS") else result["status"],
                 "detail": result, "at": started}
        if entry["status"] == "OK":
            if state["status"] in TERMINAL:
                state["status"] = "RUNNING"  # resume made progress
        else:
            state["status"] = entry["status"]
            state["failures"].append({"phase": phase, "detail": result})
        state["phases"].append(entry)
        _write(spath, state)
        if state["status"] in TERMINAL:
            break
    else:
        latest: dict[str, str] = {}
        for p in state["phases"]:
            latest[p["phase"]] = p.get("status", "")
        pending = [ph for ph in phases if latest.get(ph) != "OK"]
        state["status"] = latest.get(pending[-1], "FAILED") \
            if pending else "FINAL_PASS"
        _write(spath, state)
    return state


def recover(project_id: str) -> dict | None:
    """Latest valid checkpoint, or None."""
    project = load_project(project_id)
    state = _read(_state_path(project.id))
    if isinstance(state, dict) and state.get("controller_version") == \
            CONTROLLER_VERSION:
        return state
    return None
