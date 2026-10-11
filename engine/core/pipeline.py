"""Stage registry + content-hash cache (never analyze the same media twice)."""
from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CACHE_DIR = ROOT / ".cache"

_REGISTRY: dict[str, Callable] = {}


def stage(name: str):
    def deco(fn: Callable):
        _REGISTRY[name] = fn
        return fn
    return deco


def registered() -> list[str]:
    return sorted(_REGISTRY)


def cache_key(file_path: str | Path, stage_name: str, config: dict) -> str:
    p = Path(file_path)
    h = hashlib.sha256()
    h.update(stage_name.encode())
    h.update(json.dumps(config, sort_keys=True, default=str).encode())
    if p.is_file():
        h.update(f"{p.stat().st_size}:{p.stat().st_mtime_ns}".encode())
        with p.open("rb") as fh:
            h.update(fh.read(1 << 20))  # first MB is enough to disambiguate
    else:
        h.update(str(p).encode())
    return h.hexdigest()[:32]


def cached(key: str) -> Path | None:
    dest = CACHE_DIR / f"{key}.json"
    return dest if dest.is_file() else None


def store(key: str, payload: dict) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    dest = CACHE_DIR / f"{key}.json"
    dest.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return dest
