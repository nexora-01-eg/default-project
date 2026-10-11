"""Pure maths for the three decision primitives.

Mirrors the Jev wire shapes used by local-jev (choice / score / noul),
implemented with the standard library only (no numpy) so the engine runs
offline on any Python 3.10+.
"""
from __future__ import annotations

import math

ROUND = 4
MAX_CHOICES = 255
MIN_LEVELS, MAX_LEVELS = 1, 10


def softmax(logits, temperature: float = 1.0) -> list:
    t = max(float(temperature), 1e-6)
    z = [float(x) / t for x in logits]
    m = max(z)
    exps = [math.exp(v - m) for v in z]
    s = sum(exps)
    return [e / s for e in exps]


def confidence(probs) -> float:
    """Peakiness of a distribution: 1.0 = all mass on one option, 0.0 = uniform.

    n-option generalisation of (3 * p_max - 1) / 2.
    """
    probs = list(probs)
    n = len(probs)
    if n < 2:
        return 1.0
    return float(max(0.0, (n * max(probs) - 1.0) / (n - 1.0)))


def choice_answer(keys: list, probs) -> dict:
    probs = [float(p) for p in probs]
    best = max(range(len(keys)), key=lambda i: probs[i])
    return {
        "type": "choice",
        "choice": keys[best],
        "confidence": round(confidence(probs), ROUND),
        "probabilities": {k: round(float(p), ROUND) for k, p in zip(keys, probs)},
    }


def score_answer(levels: list, probs) -> dict:
    probs = [float(p) for p in probs]
    expected = sum(i * p for i, p in enumerate(probs))
    return {
        "type": "score",
        "score": round(expected, ROUND),
        "confidence": round(confidence(probs), ROUND),
        "legend": {str(i): level for i, level in enumerate(levels)},
        "probabilities": {str(i): round(float(p), ROUND) for i, p in enumerate(probs)},
    }


def noul_answer(p_true: float) -> dict:
    return {"type": "noul", "noul": round(float(p_true), ROUND)}
