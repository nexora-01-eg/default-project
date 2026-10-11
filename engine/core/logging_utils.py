"""JSONL run logging: one event per line, human-readable via `status`."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def log_event(log_file: Path, stage: str, op: str, status: str = "ok",
              duration_s: float = 0.0, output: str = "",
              versions: dict | None = None, extra: dict | None = None) -> dict:
    event: dict[str, Any] = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "stage": stage,
        "op": op,
        "status": status,
        "duration_s": round(duration_s, 3),
        "output": output,
        "versions": versions or {},
        "extra": extra or {},
    }
    log_file.parent.mkdir(parents=True, exist_ok=True)
    with log_file.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event) + "\n")
    return event
