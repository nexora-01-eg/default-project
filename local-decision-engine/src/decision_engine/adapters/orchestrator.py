"""Adapter for AI-Agent-Orchestrator: LocalDecisionEngineAdapter.

Optional accelerator for the existing SmartRouter — it does NOT replace it.
Typical use: ask cheap gating questions first (route hint, retry?, LLM
needed?, needs review?), then let the existing router/adapters decide.

Usage:
    from decision_engine.adapters.orchestrator import LocalDecisionEngineAdapter
    gate = LocalDecisionEngineAdapter()  # enabled=False by default
    hint = gate.route_hint("Refactor the rendering module across 40 files")
    # hint -> {"agent": "OpenCode", "confidence": 0.9, "status": "ok"}
    # Feed it to SmartRouter as a hint, or ignore it when status != "ok".
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from ..engine import DecisionEngine, LocalDecisionEngine


class LocalDecisionEngineAdapter:
    """Optional decision accelerator. Disabled by default; safe to construct."""

    def __init__(self, engine: Optional[DecisionEngine] = None,
                 threshold: float = 0.6, enabled: bool = False):
        self.engine = engine or LocalDecisionEngine()
        self.threshold = threshold
        self.enabled = enabled

    def _guard(self):
        if not self.enabled:
            return {"status": "disabled", "hint": None,
                    "reason": "adapter is opt-in; enable after benchmarking"}

    def route_hint(self, task: str) -> Dict[str, Any]:
        """Suggest which agent fits. Returns hint + confidence, or review flag."""
        g = self._guard()
        if g:
            return g
        out = self.engine.decide_with_fallback(task, {
            "agent": {"type": "choice", "instructions": "Which agent should handle this task?",
                      "criteria": {"OpenCode": "large multi-file coding work",
                                   "Aider": "git-heavy scoped code change",
                                   "Qwen": "complex orchestration and planning",
                                   "Gemini": "internet research task"}}},
            threshold=self.threshold)
        if out["status"] != "ok":
            return {"status": out["status"], "hint": None,
                    "low_confidence": out.get("low_confidence", [])}
        a = out["answers"]["agent"]
        return {"status": "ok", "hint": {"agent": a["choice"],
                                         "confidence": a["confidence"],
                                         "probabilities": a["probabilities"]}}

    def classify_task(self, task: str) -> Dict[str, Any]:
        g = self._guard()
        if g:
            return g
        return self.engine.decide_with_fallback(task, {
            "kind": {"type": "choice", "instructions": "What kind of work is this?",
                     "criteria": {"coding": "write or change code",
                                  "research": "look up information online",
                                  "writing": "write prose or docs",
                                  "ops": "run, deploy or fix systems"}}},
            threshold=self.threshold)

    def decide_retry(self, agent_output: str, exit_code: int = 0) -> Dict[str, Any]:
        g = self._guard()
        if g:
            return g
        return self.engine.decide_with_fallback(
            f"exit={exit_code} output: {agent_output[:2000]}", {
                "retry": {"type": "choice", "instructions": "Should we retry the agent?",
                          "criteria": {"retry": "output is empty or broken, retry",
                                       "accept": "output looks complete, accept",
                                       "review": "uncertain, send to human review"}}},
            threshold=self.threshold)

    def decide_fallback(self, error: str) -> Dict[str, Any]:
        g = self._guard()
        if g:
            return g
        return self.engine.decide_with_fallback(error[:2000], {
            "fallback": {"type": "choice", "instructions": "Which fallback fits this failure?",
                         "criteria": {"retry_same": "transient error, retry same agent",
                                      "switch_agent": "agent limitation, switch agent",
                                      "human": "needs human judgment"}}},
            threshold=self.threshold)

    def needs_large_llm(self, task: str) -> Dict[str, Any]:
        """Gate: local decision enough, or spend LLM computation?"""
        g = self._guard()
        if g:
            return g
        return self.engine.decide_with_fallback(task, {
            "gate": {"type": "choice",
                     "instructions": "Does this task require a large LLM?",
                     "criteria": {"llm": "needs writing, coding or deep reasoning",
                                  "local": "a fast local decision is enough"}}},
            threshold=self.threshold)

    def needs_review(self, agent_result: str) -> Dict[str, Any]:
        g = self._guard()
        if g:
            return g
        return self.engine.decide_with_fallback(agent_result[:2000], {
            "review": {"type": "noul",
                       "instructions": "This agent result needs human review"}},
            threshold=self.threshold)
