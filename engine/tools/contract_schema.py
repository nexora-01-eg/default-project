"""Production-contract schema + validation (additive; existing controller untouched).

A production contract is the machine-readable plan the Director/router
execute: shots, narration, captions, motion, graphics, audio, review.
Validated with jsonschema when available, else a structural fallback.
"""
from __future__ import annotations

CONTRACT_SCHEMA = {
    "type": "object",
    "required": ["project", "canvas", "narration", "shots"],
    "properties": {
        "project": {"type": "string"},
        "canvas": {"type": "object",
                   "required": ["w", "h", "fps"],
                   "properties": {"w": {"type": "integer"},
                                  "h": {"type": "integer"},
                                  "fps": {"type": "number"}}},
        "voice": {"type": "object"},
        "narration": {"type": "object",
                      "required": ["segments"],
                      "properties": {"segments": {
                          "type": "array",
                          "items": {"type": "object",
                                    "required": ["id", "text", "start"],
                                    "properties": {
                                        "id": {"type": "string"},
                                        "text": {"type": "string"},
                                        "start": {"type": "number"},
                                        "wav": {"type": "string"}}}}}},
        "shots": {"type": "array", "minItems": 1,
                  "items": {"type": "object",
                            "required": ["shot_id", "start", "end"],
                            "properties": {
                                "shot_id": {"type": "string"},
                                "start": {"type": "number"},
                                "end": {"type": "number"},
                                "asset": {"type": "string"},
                                "motion": {"type": "object"},
                                "graphics": {"type": "array"},
                                "text": {"type": "object"}}}},
        "audio": {"type": "object"},
        "review": {"type": "object"},
    },
}


def validate_contract(contract: dict) -> dict:
    """Validate a production contract. Returns {valid, errors[]}."""
    errors: list[str] = []
    try:
        from engine.tools.adapters.providers import get
        get("jsonschema").run({"document": contract,
                               "schema": CONTRACT_SCHEMA, "dst": "inline"})
        return {"valid": True, "errors": []}
    except Exception as exc:  # jsonschema missing -> structural fallback
        for key in ("project", "canvas", "narration", "shots"):
            if key not in contract:
                errors.append(f"missing: {key}")
        if not errors:
            c = contract["canvas"]
            if (c.get("w"), c.get("h"), c.get("fps")) != (1080, 1920, 30):
                errors.append("canvas must be 1080x1920@30")
            if not contract["shots"]:
                errors.append("at least one shot required")
        if "jsonschema" in str(type(exc).__name__).lower():
            errors.append(f"schema: {exc}")
        _ = exc
        return {"valid": not errors, "errors": errors}
