"""Детерминированные правила расчёта метрик L2."""

from __future__ import annotations

from .config import BenchmarkConfig


VALID_SCORES = frozenset({1, 3, 5})


def coverage(present: int, missing: int) -> float:
    total = present + missing
    if total < 1:
        raise ValueError("Для Coverage нужна хотя бы одна текстовая сущность")
    return present / total


def faithfulness(present: int, unsupported: int, missing: int, config: BenchmarkConfig) -> int:
    if min(present, unsupported, missing) < 0:
        raise ValueError("Счётчики сущностей не могут быть отрицательными")
    ratio = coverage(present, missing)
    if unsupported >= 2:
        return 1
    if unsupported == 1:
        return 1 if missing >= 1 else 3
    if ratio >= config.faithfulness_max:
        return 5
    if ratio >= config.faithfulness_mid:
        return 3
    return 1


def overall(scores: dict[str, int], config: BenchmarkConfig) -> float:
    required = ("faithfulness", "clarity", "compactness", "style")
    if any(scores.get(name) not in VALID_SCORES for name in required):
        raise ValueError("Каждая ось должна иметь значение 1, 3 или 5")
    result = (
        config.weight_faithfulness * scores["faithfulness"]
        + config.weight_clarity * scores["clarity"]
        + config.weight_compactness * scores["compactness"]
        + config.weight_style * scores["style"]
    )
    return round(result, 8)


def outcome(left: int | float, right: int | float) -> str:
    if left > right:
        return "win"
    if left < right:
        return "lose"
    return "tie"
