"""Decision gate for ai-opportunity-engine (opt-in, off by default).

Intended position in oppengine/pipeline.py (NOT wired yet — enable only
after benchmarking):

    COLLECT -> RAW -> NORMALIZE -> [DECISION GATE here] -> ... existing ...

Wiring (one block, inside the ANALYZE loop, before AIR.analyze):

    from . import decision_gate as DECG
    gate = DECG.prefilter_item(raw.get("original_text", ""))
    if gate["verdict"] == "drop":
        run["rejected"] += 1
        continue  # skip LLM entirely; raw row stays in DB
    # "keep" and "review" continue to existing logic unchanged.

Set LOCAL_DECISION_ENGINE_ROOT to the local-decision-engine folder, or put
its src/ on PYTHONPATH. Without it, prefilter_item() returns
verdict="review" and the pipeline continues unchanged.
"""
from __future__ import annotations

import os
import sys
from typing import Any, Dict

_GATE = None
_GATE_ERROR = ""


def _load():
    global _GATE, _GATE_ERROR
    if _GATE is not None or _GATE_ERROR:
        return
    try:
        from decision_engine.adapters.opportunity import OpportunityGate  # type: ignore
        _GATE = OpportunityGate
    except ImportError as exc:
        root = os.environ.get("LOCAL_DECISION_ENGINE_ROOT", "")
        src = os.path.join(root, "src") if root else ""
        if src and os.path.isdir(src) and src not in sys.path:
            sys.path.insert(0, src)
            try:
                from decision_engine.adapters.opportunity import (  # type: ignore
                    OpportunityGate)
                _GATE = OpportunityGate
                return
            except ImportError as exc2:
                exc = exc2
        _GATE_ERROR = str(exc)[:200]


def _gate():
    _load()
    if _GATE is None:
        return None
    return _GATE(enabled=os.environ.get("OPP_DECISION_GATE", "0") == "1")


def prefilter_item(text: str) -> Dict[str, Any]:
    """(verdict, confidence, detail). 'review' keeps existing behavior."""
    g = _gate()
    if g is None:
        return {"verdict": "review",
                "reason": "engine unavailable: " + _GATE_ERROR,
                "confidence": 0.0}
    return g.prefilter_item(text)


def worth_deep_analysis(text: str) -> Dict[str, Any]:
    g = _gate()
    if g is None:
        return {"verdict": "review",
                "reason": "engine unavailable: " + _GATE_ERROR}
    return g.worth_deep_analysis(text)
