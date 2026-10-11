"""Local Decision Engine — a local, open-source decision layer.

DISCLAIMER: This is a local open-source decision engine inspired by /
compatible with the Jev/System One style of decision interface. It is NOT
the original TypeSafe Jev model, and it is not affiliated with or endorsed
by TypeSafe. See README.md.
"""

__version__ = "0.1.0"
__backend__ = "rules-tfidf"

from .engine import (
    AUTH_REQUIRED,
    DecisionEngine,
    HostedJevEngine,
    LLMFallbackEngine,
    LocalDecisionEngine,
    DecisionResult,
    create_engine,
)

__all__ = [
    "__version__",
    "__backend__",
    "AUTH_REQUIRED",
    "DecisionEngine",
    "HostedJevEngine",
    "LLMFallbackEngine",
    "LocalDecisionEngine",
    "DecisionResult",
    "create_engine",
]
