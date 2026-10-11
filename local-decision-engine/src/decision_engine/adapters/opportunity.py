"""Adapter for ai-opportunity-engine: cheap pre-filter before any LLM call.

Pipeline position:
    COLLECT -> NORMALIZE -> [DECISION GATE here] -> FILTER -> SCORE
    -> DEEP ANALYSIS -> OPPORTUNITY

Contract: prefilter_item() returns (verdict, confidence, details) where
verdict is "keep" | "drop" | "review". "review" (low confidence) must keep
the raw data and continue to existing logic — the gate never deletes.
"""
from __future__ import annotations

from typing import Any, Dict

from ..engine import DecisionEngine, LocalDecisionEngine


class OpportunityGate:
    """Cheap filter/scorer. Disabled by default; benchmark before enabling."""

    def __init__(self, engine: DecisionEngine | None = None,
                 threshold: float = 0.6, enabled: bool = False):
        self.engine = engine or LocalDecisionEngine()
        self.threshold = threshold
        self.enabled = enabled

    def prefilter_item(self, text: str) -> Dict[str, Any]:
        """Triage one raw request. Never drops on low confidence (returns review)."""
        if not self.enabled:
            return {"verdict": "review", "reason": "gate disabled (opt-in)",
                    "confidence": 0.0}
        if not (text or "").strip():
            return {"verdict": "drop", "reason": "empty text", "confidence": 1.0}
        out = self.engine.decide_with_fallback(text, {
            "opp": {"type": "choice", "instructions": "Is this a real service opportunity?",
                    "criteria": {"real": "real service opportunity with a paying client",
                                 "maybe": "maybe, needs clarification",
                                 "spam": "irrelevant or spam"}},
            "online": {"type": "choice", "instructions": "Does it need an online service?",
                       "criteria": {"yes": "needs an online or digital service",
                                    "no": "needs a physical offline service"}},
            "priority": {"type": "choice", "instructions": "Priority?",
                         "criteria": {"high": "urgent blocking issue",
                                      "medium": "normal time pressure",
                                      "low": "minor background task"}}},
            threshold=self.threshold)
        if out["status"] != "ok":
            return {"verdict": "review", "reason": out["status"],
                    "confidence": 0.0, "detail": out}
        opp = out["answers"]["opp"]
        if opp["choice"] == "spam" and opp["confidence"] >= self.threshold:
            return {"verdict": "drop", "reason": "spam/irrelevant",
                    "confidence": opp["confidence"], "detail": out["answers"]}
        return {"verdict": "keep", "reason": f"opp={opp['choice']}",
                "confidence": opp["confidence"], "detail": out["answers"]}

    def worth_deep_analysis(self, text: str) -> Dict[str, Any]:
        """Second gate before expensive LLM analysis."""
        if not self.enabled:
            return {"verdict": "review", "reason": "gate disabled (opt-in)"}
        return self.prefilter_item(text)
