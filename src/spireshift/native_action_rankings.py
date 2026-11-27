"""Current-menu ranking diagnostics; no outcomes, labels or policy updates."""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Any

from spireshift.full_run_ppo_math import log_softmax
from spireshift.neural_combat import _numpy

CONTRACT = "same_public_menu_raw_actor_rank_margin_and_sampling_v1"


def selected(logs: Sequence[float], draw: float | None) -> int:
    if not logs:
        raise ValueError("Rank only a nonempty current legal menu")
    if draw is None:
        return max(range(len(logs)), key=lambda i: (logs[i], -i))
    if type(draw) is not float or not 0 <= draw < 1:
        raise ValueError("Use the recorded finite uniform draw")
    cumulative = 0.0
    for i, value in enumerate(logs):
        cumulative += math.exp(value)
        if draw < cumulative:
            return i
    return len(logs) - 1


def scores(x: Any, parameters: tuple[Any, Any, Any, Any]) -> tuple[float, ...]:
    """Same float64 kernel as score_features, with immutable parameters unpacked once."""
    np = _numpy()
    w, bias, out, linear = parameters
    result = np.tanh(x @ w.T + bias) @ out + x @ linear
    if result.shape != (len(x),) or not np.isfinite(result).all():
        raise ValueError("Nonfinite or incorrectly shaped saved action scores")
    return tuple(float(v) for v in result)


def describe(values: Sequence[float], temperature: float = 0.8) -> dict[str, Any]:
    if not values or any(type(v) not in (int, float) or not math.isfinite(v) for v in values):
        raise ValueError("Rank finite action scores on the same nonempty menu")
    order = sorted(range(len(values)), key=lambda i: (-values[i], i))
    logs = log_softmax(values, temperature)
    mean = math.fsum(values) / len(values)
    return {
        "greedy_index": order[0],
        "order": order,
        "margin": float(values[order[0]] - values[order[1]]) if len(values) > 1 else None,
        "centered_RMS": math.sqrt(math.fsum((v - mean) ** 2 for v in values) / len(values)),
        "score_mean": mean,
        "entropy": -math.fsum(math.exp(p) * p for p in logs),
        "logs": list(logs),
    }


def compare(
    before: Sequence[float], after: Sequence[float], *, draw: float | None = None
) -> dict[str, Any]:
    if len(before) != len(after):
        raise ValueError("A changed legal menu is not a ranking comparison")
    a, b = describe(before), describe(after)
    best = a["greedy_index"]
    inversions = strict_pairs = 0
    for i in range(len(before)):
        for j in range(i):
            left, right = before[i] - before[j], after[i] - after[j]
            if left != 0 and right != 0:
                strict_pairs += 1
                inversions += (left > 0) != (right > 0)
    return {
        "greedy_changed": best != b["greedy_index"],
        "original_best_rank_after": b["order"].index(best),
        "original_best_signed_margin_after": (
            float(after[best] - max(v for i, v in enumerate(after) if i != best))
            if len(after) > 1
            else None
        ),
        "before_margin": a["margin"],
        "after_margin": b["margin"],
        "before_centered_RMS": a["centered_RMS"],
        "after_centered_RMS": b["centered_RMS"],
        "entropy_change": b["entropy"] - a["entropy"],
        "KL_before_to_after": max(
            0.0,
            math.fsum(math.exp(p) * (p - q) for p, q in zip(a["logs"], b["logs"], strict=True)),
        ),
        "strict_pair_inversions": inversions,
        "strict_pairs_compared": strict_pairs,
        "same_draw_choice_changed": (
            selected(a["logs"], draw) != selected(b["logs"], draw) if draw is not None else None
        ),
    }
