"""DecisionEngine abstraction — backends are swappable without touching callers.

- LocalDecisionEngine (default): offline rules-tfidf backend, no model files.
- NliDecisionEngine: reserved name for the optional DeBERTa NLI backend
  (0.87 GB download, installed only after a benchmark gate approves it).
- HostedJevEngine: passthrough to a real local-jev server (vendor/local-jev
  run via WSL2) or any Jev-wire-compatible endpoint on this machine.
- LLMFallbackEngine: never invents credentials; answers AUTH_REQUIRED when
  no local LLM endpoint is configured.

Callers use ``engine.decide(...)`` / ``decide_with_fallback(...)`` — never
backend internals.
"""
from __future__ import annotations

import json
import time
import urllib.request
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from . import scorer
from .primitives import choice_answer, noul_answer, score_answer
from .questions import ContextOverflow, QuestionError, as_text, parse_question

AUTH_REQUIRED = "AUTH_REQUIRED"
DEFAULT_MODEL = "rules-tfidf"
MODEL_ALIASES = ("jev-latest", "jev-preview", "local-jev-latest")
MAX_STATE_CHARS = 20000  # local-jev truncates; we shorten keep-start+end too


@dataclass
class DecisionResult:
    model: str
    answers: Dict[str, dict]
    truncated: bool = False
    usage: dict = field(default_factory=lambda: {"input_tokens": 0, "output_tokens": 0})


def _shorten(state: str) -> tuple:
    if len(state) <= MAX_STATE_CHARS:
        return state, False
    head = MAX_STATE_CHARS * 3 // 4
    tail = MAX_STATE_CHARS - head
    return state[:head] + "\n…[truncated]…\n" + state[-tail:], True


def answer_question(state: str, wire: dict, model_name: str) -> dict:
    q = parse_question(wire)
    if q.type == "choice":
        opts = [f"{k}: {d}" for k, d in zip(q.keys, q.descriptions)]
        probs = scorer.score_options(state, q.instructions, opts)
        return choice_answer(list(q.keys), probs)
    if q.type == "score":
        opts = list(q.descriptions)
        probs = scorer.score_options(state, q.instructions, opts)
        return score_answer(list(q.legend), probs)
    # noul: yes-hypothesis vs no-hypothesis. Each side gets explicit
    # affirm/deny tokens so bare instructions still separate ("not"/"no"
    # are content tokens, not stopwords, for exactly this reason).
    yes_text = (q.instructions + " " + q.yes + " yes affirmed true").strip()
    no_text = ((q.no or ("Not the case: " + (q.instructions or "this"))) + " no denied false").strip()
    probs = scorer.score_options(state, q.instructions, [yes_text, no_text])
    return noul_answer(probs[0])


class DecisionEngine(ABC):
    name = "base"

    @abstractmethod
    def system_one(self, state: Any, questions: Dict[str, dict],
                   model: str = DEFAULT_MODEL) -> DecisionResult:
        ...

    # ---- convenience API (stable across backends) ----
    def decide(self, state: Any, questions: Dict[str, dict],
               model: str = DEFAULT_MODEL) -> Dict[str, dict]:
        """Return the answers dict only. Raises QuestionError on bad input."""
        return self.system_one(state, questions, model).answers

    def decide_with_fallback(self, state: Any, questions: Dict[str, dict],
                             threshold: float = 0.6,
                             fallback: Optional["DecisionEngine"] = None) -> dict:
        """Gate on confidence: high -> accept, low -> fallback or review flag."""
        started = time.time()
        try:
            res = self.system_one(state, questions)
        except Exception as exc:  # backend down -> never stop the caller
            return {"status": "backend_error", "error": str(exc)[:300],
                    "fallback": "review", "latency_s": round(time.time() - started, 3)}
        low = [k for k, a in res.answers.items()
               if a.get("confidence", a.get("noul", 1.0)) < threshold
               and a.get("type") != "noul"]
        low += [k for k, a in res.answers.items()
                if a.get("type") == "noul" and abs(a["noul"] - 0.5) < (0.5 - threshold / 2)]
        out = {"status": "ok" if not low else "needs_review",
               "answers": res.answers, "model": res.model,
               "low_confidence": low,
               "latency_s": round(time.time() - started, 3)}
        if low and fallback is not None:
            try:
                fb = fallback.system_one(state, {k: questions[k] for k in low})
                out["fallback_answers"] = fb.answers
                out["fallback_model"] = fb.model
                out["status"] = "fallback_used"
            except Exception as exc:
                out["fallback_error"] = str(exc)[:300]
        return out


class LocalDecisionEngine(DecisionEngine):
    """Default backend: fully offline, no weights, stdlib only."""

    name = "local"
    model_name = "rules-tfidf"

    MODELS = [
        {"name": "rules-tfidf", "description": "Offline token-overlap decision backend (no weights, <1 MB RAM).",
         "release_date": "2026-09-23"},
        {"name": "nli-deberta-large", "description": "Optional NLI backend (0.87 GB download, gated by benchmark). NOT installed.",
         "release_date": "2024-04-01"},
    ]

    def system_one(self, state: Any, questions: Dict[str, dict],
                   model: str = DEFAULT_MODEL) -> DecisionResult:
        if model in MODEL_ALIASES:
            model = DEFAULT_MODEL
        if model == "nli-deberta-large":
            raise RuntimeError(
                "model_unavailable: nli-deberta-large weights are not installed. "
                "See docs/LOCAL_DECISION_MODEL_BENCHMARK.md for the install gate.")
        if model != DEFAULT_MODEL:
            raise KeyError(f"Unknown model '{model}'. See GET /v1/models.")
        if not isinstance(questions, dict) or not questions:
            raise QuestionError("questions must be a non-empty object", ("questions",))
        text = as_text(state)
        if not text:
            raise QuestionError("state must not be empty", ("state",))
        text, truncated = _shorten(text)
        answers = {}
        for qname, wire in questions.items():
            try:
                answers[str(qname)] = answer_question(text, wire, model)
            except QuestionError as err:
                raise QuestionError(err.msg, ("questions", str(qname), *err.loc))
        if len(text) > MAX_STATE_CHARS * 4:
            raise ContextOverflow("state is too long even after shortening")
        usage = {"input_tokens": max(1, len(text) // 4), "output_tokens": len(answers)}
        return DecisionResult(model=DEFAULT_MODEL, answers=answers,
                              truncated=truncated, usage=usage)


class NliDecisionEngine(LocalDecisionEngine):
    """Reserved name for the optional DeBERTa backend. Not installed yet."""

    name = "nli"
    model_name = "nli-deberta-large"

    def system_one(self, state, questions, model="nli-deberta-large"):
        raise RuntimeError(
            "model_unavailable: install gate not passed yet — "
            "run `decision-engine benchmark` first, then approve the 0.87 GB download.")


class HostedJevEngine(DecisionEngine):
    """Passthrough to a Jev-wire-compatible server (e.g. vendor local-jev via WSL2)."""

    name = "hosted"

    def __init__(self, base_url: str = "http://127.0.0.1:8765", api_key: Optional[str] = None,
                 timeout: int = 30):
        if not base_url.startswith(("http://127.0.0.1", "http://localhost")):
            raise ValueError("HostedJevEngine allows loopback URLs only (local by default).")
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    def system_one(self, state, questions, model="jev-latest") -> DecisionResult:
        body = json.dumps({"state": state, "model": model, "questions": questions}).encode()
        req = urllib.request.Request(self.base_url + "/v1/systemone", data=body,
                                     headers={"Content-Type": "application/json"})
        if self.api_key:
            req.add_header("Authorization", f"Bearer {self.api_key}")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                payload = json.loads(r.read().decode())
        except OSError as exc:
            raise RuntimeError(f"host unreachable: {exc}") from exc
        return DecisionResult(model=payload.get("model", "hosted"),
                              answers=payload.get("answers", {}),
                              usage=payload.get("usage", {"input_tokens": 0, "output_tokens": 0}))


class LLMFallbackEngine(DecisionEngine):
    """Fallback that needs a local LLM endpoint. Never invents credentials."""

    name = "llm-fallback"

    def __init__(self, base_url: Optional[str] = None, api_key: Optional[str] = None):
        self.base_url = base_url
        self.api_key = api_key

    def system_one(self, state, questions, model="llm-fallback") -> DecisionResult:
        if not self.base_url or not self.api_key:
            raise RuntimeError(AUTH_REQUIRED + ": LLMFallbackEngine has no credentials configured; "
                               "keeping existing logic instead of calling a paid service.")
        raise RuntimeError(AUTH_REQUIRED + ": remote fallback is disabled by policy (local-only).")


def create_engine(kind: str = "local", **kwargs) -> DecisionEngine:
    kinds = {"local": LocalDecisionEngine, "nli": NliDecisionEngine,
             "hosted": HostedJevEngine, "llm": LLMFallbackEngine}
    if kind not in kinds:
        raise ValueError(f"unknown engine '{kind}'; choose from {sorted(kinds)}")
    return kinds[kind](**kwargs)
