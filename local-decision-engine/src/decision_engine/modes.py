"""Decision modes: DISABLED -> SHADOW -> CANARY -> ACTIVE.

- DISABLED: engine never called, zero behavior change.
- SHADOW (default): engine runs alongside, records only, changes nothing.
- CANARY (opt-in): a sampled % is evaluated; results recorded; the existing
  decision is ALWAYS returned unchanged. Canary never changes outcomes.
- ACTIVE: defined for configuration completeness only. This module never
  activates it; nothing in this repo switches to ACTIVE.

Kill switch: LOCAL_DECISION_ENGINE_ENABLED=0 -> everything behaves DISABLED.
Policy is configurable via env, never hard-coded:
    HIGH_CONFIDENCE_THRESHOLD (default 0.8)
    LOW_CONFIDENCE_ACTION     (default REVIEW_REQUIRED)
    CANARY_PERCENT            (default 0)
"""
from __future__ import annotations

import hashlib
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, Optional

from .engine import DecisionEngine, LocalDecisionEngine


class DecisionMode(str, Enum):
    DISABLED = "disabled"
    SHADOW = "shadow"
    CANARY = "canary"
    ACTIVE = "active"


CURRENT_DEFAULT = DecisionMode.SHADOW


@dataclass
class SafetyPolicy:
    high_confidence_threshold: float = 0.8
    low_confidence_action: str = "REVIEW_REQUIRED"
    canary_percent: float = 0.0
    timeout_s: float = 5.0

    @classmethod
    def from_env(cls) -> "SafetyPolicy":
        return cls(
            high_confidence_threshold=float(
                os.environ.get("HIGH_CONFIDENCE_THRESHOLD", "0.8")),
            low_confidence_action=os.environ.get(
                "LOW_CONFIDENCE_ACTION", "REVIEW_REQUIRED"),
            canary_percent=float(os.environ.get("CANARY_PERCENT", "0")),
        )


def kill_switch() -> bool:
    """True = engine allowed. LOCAL_DECISION_ENGINE_ENABLED=0 kills everything."""
    return os.environ.get("LOCAL_DECISION_ENGINE_ENABLED", "1") != "0"


def resolve_mode(requested: DecisionMode | str = CURRENT_DEFAULT) -> DecisionMode:
    if not kill_switch():
        return DecisionMode.DISABLED
    if isinstance(requested, DecisionMode):
        return requested
    try:
        return DecisionMode(str(requested).lower())
    except ValueError:
        return DecisionMode.DISABLED


ALLOWED_LOG_KEYS = {"timestamp", "mode", "decision", "confidence",
                    "latency_ms", "agreement"}


def _in_canary(ref: str, percent: float) -> bool:
    """Deterministic sampling: sha1(ref) % 100 < percent. Reproducible."""
    if percent <= 0:
        return False
    if percent >= 100:
        return True
    h = int(hashlib.sha1(ref.encode()).hexdigest(), 16) % 100
    return h < percent


@dataclass
class ModeResult:
    existing_decision: Any
    local_decision: Optional[Dict[str, Any]] = None
    confidence: float = 0.0
    latency_ms: float = 0.0
    agreement: Optional[bool] = None
    action: str = "existing"  # existing | review_required
    log: Dict[str, Any] = field(default_factory=dict)


class ModeGate:
    """Runs the engine per mode. Existing decision is NEVER modified.

    existing_fn: zero-arg callable returning the existing decision (lazy, so
    DISABLED mode never even builds it). local_fn: zero-arg callable returning
    (answers_dict, confidence). Any exception anywhere -> fail open.
    """

    def __init__(self, engine: Optional[DecisionEngine] = None,
                 policy: Optional[SafetyPolicy] = None):
        self.engine = engine  # may be None -> unavailable -> fail open
        self.policy = policy or SafetyPolicy.from_env()

    def evaluate(self, mode: DecisionMode | str, ref: str,
                 existing_fn: Callable[[], Any],
                 local_fn: Optional[Callable[[], Any]] = None,
                 compare: Optional[Callable[[Any, Any], bool]] = None) -> ModeResult:
        m = resolve_mode(mode)
        ts = time.strftime("%Y-%m-%dT%H:%M:%S")
        if m == DecisionMode.DISABLED:
            existing = self._safe(existing_fn)
            return ModeResult(existing_decision=existing,
                              log=self._log(ts, m, None, 0.0, 0.0, None))
        if m == DecisionMode.SHADOW:
            existing = self._safe(existing_fn)
            local, conf, dt = self._safe_local(local_fn, ref)
            agr = self._safe_compare(compare, existing, local)
            action = "existing" if (local and conf >= self.policy.high_confidence_threshold) \
                else self.policy.low_confidence_action.lower() \
                if local else "existing"
            # SHADOW never changes anything: action recorded, existing returned.
            return ModeResult(existing_decision=existing, local_decision=local,
                              confidence=conf, latency_ms=dt, agreement=agr,
                              action="existing",
                              log=self._log(ts, m, self._summ(local), conf, dt, agr))
        if m == DecisionMode.CANARY:
            existing = self._safe(existing_fn)
            if not _in_canary(ref, self.policy.canary_percent):
                return ModeResult(existing_decision=existing, action="existing",
                                  log=self._log(ts, m, None, 0.0, 0.0, None))
            local, conf, dt = self._safe_local(local_fn, ref)
            agr = self._safe_compare(compare, existing, local)
            return ModeResult(existing_decision=existing, local_decision=local,
                              confidence=conf, latency_ms=dt, agreement=agr,
                              action="existing",  # canary records only
                              log=self._log(ts, m, self._summ(local), conf, dt, agr))
        # ACTIVE is configuration-only: this repo never routes here.
        existing = self._safe(existing_fn)
        return ModeResult(existing_decision=existing, action="existing",
                          log=self._log(ts, m, None, 0.0, 0.0, None))

    def _safe(self, fn):
        try:
            return fn()
        except Exception as exc:  # fail open to existing behavior
            return {"__existing_error__": str(exc)[:120]}

    def _safe_local(self, local_fn, ref):
        # local_fn wraps the engine call (with its own timeout). Any failure
        # -> (None, 0.0): fail open, existing behavior continues.
        if local_fn is None:
            return None, 0.0, 0.0
        t0 = time.time()
        try:
            out = local_fn()
            if isinstance(out, tuple) and len(out) == 2:
                local, conf = out
            elif isinstance(out, dict):
                local, conf = out, float(out.get("confidence", 0.0))
            else:
                local, conf = {"value": out}, 0.0
            return local, float(conf), round((time.time() - t0) * 1000, 3)
        except Exception:
            return None, 0.0, round((time.time() - t0) * 1000, 3)

    def _safe_compare(self, compare, existing, local):
        if compare is None or local is None:
            return None
        try:
            return bool(compare(existing, local))
        except Exception:
            return None

    def _summ(self, local):
        if not isinstance(local, dict):
            return local
        return {k: v for k, v in local.items() if k in ("choice", "type")}

    def _log(self, ts, mode, decision, conf, dt, agr):
        mname = mode.value if isinstance(mode, DecisionMode) else str(mode)
        entry = {"timestamp": ts, "mode": mname,
                 "decision": decision, "confidence": round(float(conf or 0.0), 4),
                 "latency_ms": dt, "agreement": agr}
        assert set(entry) <= ALLOWED_LOG_KEYS, "log schema violation"
        return entry


def default_engine() -> LocalDecisionEngine:
    return LocalDecisionEngine()
