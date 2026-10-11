"""Phase 29 — local production memory (append-only JSONL, per project).

Records asset history, selections, rejections + reasons, renders, reviews,
repairs, and configs. Local and inspectable: plain JSONL under
projects/<pid>/memory/. Stores hashes and relative references, never media
bytes and never credentials.
"""
from __future__ import annotations

import time

from engine.core.project_store import load_project, project_dir

MEMORY_VERSION = "1.0.0"
ALLOWED_KINDS = ("asset_selected", "asset_rejected", "render", "review",
                 "repair", "style_config", "project_config", "note")


def _mem_dir(project_id: str):
    d = project_dir(project_id) / "memory"
    d.mkdir(parents=True, exist_ok=True)
    return d


def remember(project_id: str, kind: str, payload: dict) -> dict:
    """Append one memory event. Raises on unknown kind or secrets."""
    if kind not in ALLOWED_KINDS:
        raise ValueError(f"unknown memory kind {kind!r}")
    blob = str(payload)
    for banned in ("password", "secret", "api_key", "apikey", "token"):
        if banned in blob.lower():
            raise ValueError("refusing to store potential secret")
    import json
    project = load_project(project_id)
    event = {"kind": kind, "at": round(time.time(), 3),
             "memory_version": MEMORY_VERSION, **payload}
    with open(_mem_dir(project.id) / "events.jsonl", "a",
              encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
    return event


def recall(project_id: str, kind: str | None = None, limit: int = 50) -> list[dict]:
    """Read back events (newest last). Pure read."""
    import json
    load_project(project_id)
    path = project_dir(project_id) / "memory" / "events.jsonl"
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    out = []
    for line in lines:
        if not line.strip():
            continue
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if kind is None or e.get("kind") == kind:
            out.append(e)
    return out[-limit:]
