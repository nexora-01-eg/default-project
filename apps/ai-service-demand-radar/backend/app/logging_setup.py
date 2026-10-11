"""Structured logging (Phase 16).

Every log record is written to two sinks:

1. `logs/radar.jsonl`  — one JSON object per line, machine readable, rotated by
   size, containing: ts, level, component, source, job, status, duration_ms,
   error, retry_count (+ arbitrary extras).
2. `logs/radar.log`    — human readable mirror.

A bounded in-memory ring buffer keeps the most recent records so the dashboard
can expose "recent errors" without re-reading the whole file.

Secrets are never logged: `scrub()` redacts known-sensitive keys and any value
that looks like an API key.
"""

from __future__ import annotations

import json
import logging
import logging.handlers
import re
import threading
import time
from collections import deque
from pathlib import Path
from typing import Any

from .config import LOGS_DIR, get_settings

JSONL_PATH = LOGS_DIR / "radar.jsonl"
TEXT_PATH = LOGS_DIR / "radar.log"

_SECRET_KEY_RE = re.compile(r"(api[_-]?key|token|secret|password|authorization)", re.I)
_SECRET_VALUE_RE = re.compile(r"\b(sk-[A-Za-z0-9]{12,}|ghp_[A-Za-z0-9]{12,}|Bearer\s+\S+)")
_RING: deque[dict[str, Any]] = deque(maxlen=500)
_RING_LOCK = threading.Lock()
_CONFIGURED = False


def scrub(value: Any) -> Any:
    """Recursively redact secrets from a structure before it is logged."""
    if isinstance(value, dict):
        return {
            key: ("__REDACTED__" if _SECRET_KEY_RE.search(str(key)) else scrub(item))
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple, set)):
        return [scrub(item) for item in value]
    if isinstance(value, str):
        return _SECRET_VALUE_RE.sub("__REDACTED__", value)
    return value


class JsonLineFormatter(logging.Formatter):
    """Emit one compact JSON object per record."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created))
            + f".{int(record.msecs):03d}Z",
            "level": record.levelname,
            "logger": record.name,
            "component": getattr(record, "component", record.name),
            "message": record.getMessage(),
        }
        for key in ("source", "job", "status", "duration_ms", "error", "retry_count", "url", "extra"):
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = scrub(value)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        _push_ring(payload)
        return json.dumps(payload, ensure_ascii=False)


class TextFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        parts = [
            time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(record.created)),
            f"{record.levelname:<8}",
            f"[{getattr(record, 'component', record.name)}]",
            record.getMessage(),
        ]
        for key in ("source", "job", "status", "duration_ms", "retry_count"):
            value = getattr(record, key, None)
            if value is not None:
                parts.append(f"{key}={value}")
        line = " ".join(str(part) for part in parts)
        if record.exc_info:
            line += "\n" + self.formatException(record.exc_info)
        return line


def _push_ring(payload: dict[str, Any]) -> None:
    if payload.get("level") in {"ERROR", "CRITICAL", "WARNING"}:
        with _RING_LOCK:
            _RING.appendleft(payload)


def recent_errors(limit: int = 50) -> list[dict[str, Any]]:
    with _RING_LOCK:
        return list(_RING)[:limit]


def clear_ring() -> None:
    with _RING_LOCK:
        _RING.clear()


def configure_logging(level: int | None = None) -> None:
    """Idempotent logging setup (safe to call from API, CLI and tests)."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    settings = get_settings()
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger("radar")
    root.setLevel(level or (logging.DEBUG if settings.debug else logging.INFO))
    root.propagate = False
    for handler in list(root.handlers):
        root.removeHandler(handler)

    json_handler = logging.handlers.RotatingFileHandler(
        JSONL_PATH, maxBytes=5_000_000, backupCount=3, encoding="utf-8"
    )
    json_handler.setFormatter(JsonLineFormatter())
    root.addHandler(json_handler)

    text_handler = logging.handlers.RotatingFileHandler(
        TEXT_PATH, maxBytes=5_000_000, backupCount=3, encoding="utf-8"
    )
    text_handler.setFormatter(TextFormatter())
    root.addHandler(text_handler)

    stream = logging.StreamHandler()
    stream.setFormatter(TextFormatter())
    root.addHandler(stream)

    # keep third-party noise down
    for noisy in ("httpx", "httpcore", "urllib3", "apscheduler"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    _CONFIGURED = True


def get_logger(component: str) -> logging.LoggerAdapter:
    configure_logging()
    return logging.LoggerAdapter(logging.getLogger("radar"), {"component": component})


def truncate_logs(keep_days: int) -> int:
    """Delete rotated log files older than `keep_days` (Phase 20)."""
    removed = 0
    cutoff = time.time() - keep_days * 86400
    for path in list(LOGS_DIR.glob("radar.jsonl.*")) + list(LOGS_DIR.glob("radar.log.*")):
        try:
            if path.stat().st_mtime < cutoff:
                path.unlink()
                removed += 1
        except OSError:
            continue
    return removed


def log_file_paths() -> dict[str, str]:
    return {"jsonl": str(JSONL_PATH), "text": str(TEXT_PATH)}


def tail_logs(lines: int = 200) -> list[str]:
    if not TEXT_PATH.exists():
        return []
    return TEXT_PATH.read_text(encoding="utf-8", errors="replace").splitlines()[-lines:]


def describe_csv_path(name: str) -> Path:  # pragma: no cover - convenience
    return LOGS_DIR / name