"""Adapter for the news tool (الحمامة): 1000 news -> 150 -> LLM -> 20.

    1000 items
      v
    LOCAL DECISION ENGINE (this adapter: keep/maybe/drop per item)
      v
    ~150 items
      v
    LLM summarization (existing logic, unchanged)
      v
    20 important items

Raw items are always preserved; low confidence -> "maybe" (human/second look).
"""
from __future__ import annotations

from typing import Any, Dict, List

from ..engine import DecisionEngine, LocalDecisionEngine


class NewsGate:
    """AI-related? important? duplicate-ish/noise? worth summarizing?"""

    def __init__(self, engine: DecisionEngine | None = None,
                 threshold: float = 0.6, enabled: bool = False):
        self.engine = engine or LocalDecisionEngine()
        self.threshold = threshold
        self.enabled = enabled

    def triage(self, text: str) -> Dict[str, Any]:
        if not self.enabled:
            return {"verdict": "maybe", "reason": "gate disabled (opt-in)"}
        if not (text or "").strip():
            return {"verdict": "drop", "reason": "empty", "confidence": 1.0}
        out = self.engine.decide_with_fallback(text, {
            "relevance": {"type": "choice",
                          "instructions": "Is this AI related and worth summarizing?",
                          "criteria": {"yes": "AI related and worth summarizing",
                                       "maybe": "possibly relevant, needs a second look",
                                       "no": "not AI related or pure noise"}}},
            threshold=self.threshold)
        if out["status"] != "ok":
            return {"verdict": "maybe", "reason": out["status"], "detail": out}
        a = out["answers"]["relevance"]
        if a["choice"] == "no" and a["confidence"] >= self.threshold:
            return {"verdict": "drop", "confidence": a["confidence"],
                    "detail": out["answers"]}
        if a["choice"] == "yes" and a["confidence"] >= self.threshold:
            return {"verdict": "keep", "confidence": a["confidence"],
                    "detail": out["answers"]}
        return {"verdict": "maybe", "confidence": a["confidence"],
                "detail": out["answers"]}

    def filter_batch(self, items: List[str]) -> Dict[str, Any]:
        """Filter a batch; returns kept/maybe/dropped index lists. Input order kept."""
        kept, maybe, dropped = [], [], []
        for i, text in enumerate(items):
            v = self.triage(text)["verdict"]
            (kept if v == "keep" else dropped if v == "drop" else maybe).append(i)
        return {"keep": kept, "maybe": maybe, "drop": dropped,
                "reduction": f"{len(items)} -> {len(kept) + len(maybe)} "
                             f"({len(dropped)} dropped pre-LLM)"}
