"""Structured JSONL logging with secret redaction."""
import datetime
import json
import os

from .security import redact_secrets

LOG_DIR = "logs"


def _ensure():
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
    except OSError:
        pass


def log(stage, op, status="ok", output=None, **fields):
    _ensure()
    rec = {
        "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "stage": stage,
        "op": op,
        "status": status,
        "output": redact_secrets(json.dumps(output, ensure_ascii=False, default=str)) if output is not None else None,
    }
    for k, v in fields.items():
        try:
            rec[k] = json.loads(json.dumps(v, ensure_ascii=False, default=str))
        except Exception:
            rec[k] = str(v)
    line = redact_secrets(json.dumps(rec, ensure_ascii=False))
    try:
        with open(os.path.join(LOG_DIR, "oppengine.jsonl"), "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError:
        pass
    return rec
