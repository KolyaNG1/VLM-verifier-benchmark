"""Проверка ответа VLM и нормализация аудита без внешних библиотек."""

from __future__ import annotations

import json
from typing import Any

from .config import BenchmarkConfig
from .scoring import VALID_SCORES, coverage, faithfulness, overall


class EvaluationError(ValueError):
    """Ответ модели нельзя использовать в метриках."""


def parse_and_normalize(content: str, config: BenchmarkConfig) -> dict[str, Any]:
    try:
        payload = json.loads(content)
    except json.JSONDecodeError as error:
        raise EvaluationError(f"Ответ не является JSON: {error.msg}") from error
    if not isinstance(payload, dict):
        raise EvaluationError("Корневой JSON должен быть объектом")

    text_entities = payload.get("text_entities")
    visual_entities = payload.get("visual_entities")
    checks = payload.get("entity_checks")
    unsupported = payload.get("unsupported_visual_entities")
    scores = payload.get("scores")
    audit = payload.get("audit")
    if not isinstance(text_entities, list) or len(text_entities) < 3:
        raise EvaluationError("Нужно не менее трёх текстовых сущностей")
    if not isinstance(visual_entities, list) or not isinstance(checks, list) or not isinstance(unsupported, list):
        raise EvaluationError("Сущности и сопоставления должны быть списками")
    if not isinstance(scores, dict):
        raise EvaluationError("Поле scores должно быть объектом")
    if not isinstance(audit, dict) or any(not isinstance(audit.get(name), str) for name in ("faithfulness", "clarity", "compactness", "style")):
        raise EvaluationError("audit должен содержать краткое обоснование каждой оси")

    text_ids: set[str] = set()
    for entity in text_entities:
        if not isinstance(entity, dict) or not all(isinstance(entity.get(key), str) and entity[key].strip() for key in ("id", "entity", "text_evidence")):
            raise EvaluationError("Текстовая сущность требует id, entity и text_evidence")
        if entity["id"] in text_ids:
            raise EvaluationError("Идентификаторы текстовых сущностей должны быть уникальны")
        text_ids.add(entity["id"])

    statuses: dict[str, str] = {}
    for check in checks:
        if not isinstance(check, dict):
            raise EvaluationError("Элемент entity_checks должен быть объектом")
        text_id = check.get("text_entity_id")
        status = check.get("status")
        if text_id not in text_ids or status not in {"supported", "missing"}:
            raise EvaluationError("Каждое сопоставление должно связывать текстовую сущность со статусом supported/missing")
        if text_id in statuses:
            raise EvaluationError("Для текстовой сущности допустимо только одно сопоставление")
        statuses[text_id] = status
    if set(statuses) != text_ids:
        raise EvaluationError("Каждая текстовая сущность должна быть сопоставлена")
    if any(not isinstance(item, dict) or not isinstance(item.get("visual_entity_id"), str) for item in unsupported):
        raise EvaluationError("Неподдержанные сущности должны ссылаться на visual_entity_id")

    for name in ("faithfulness", "clarity", "compactness", "style"):
        if scores.get(name) not in VALID_SCORES:
            raise EvaluationError(f"scores.{name} должен быть одним из 1, 3, 5")

    present = sum(status == "supported" for status in statuses.values())
    missing = sum(status == "missing" for status in statuses.values())
    unsupported_count = len(unsupported)
    computed_coverage = coverage(present, missing)
    computed_f = faithfulness(present, unsupported_count, missing, config)
    computed_scores = {
        "faithfulness": computed_f,
        "clarity": scores["clarity"],
        "compactness": scores["compactness"],
        "style": scores["style"],
    }
    computed_overall = overall(computed_scores, config)
    warnings: list[str] = []
    reported_counts = payload.get("counts")
    if isinstance(reported_counts, dict) and any(reported_counts.get(key) != value for key, value in {"P": present, "U": unsupported_count, "M": missing}.items()):
        warnings.append("Счётчики модели отличаются от локального пересчёта")
    if payload.get("coverage") != computed_coverage:
        warnings.append("Coverage модели отличается от локального пересчёта")
    if scores.get("faithfulness") != computed_f:
        warnings.append("Faithfulness модели отличается от правила P/U/M")
    if scores.get("overall") != computed_overall:
        warnings.append("Overall модели отличается от локального пересчёта")

    return {
        "status": "success",
        "model_output": payload,
        "computed": {
            "counts": {"P": present, "U": unsupported_count, "M": missing},
            "coverage": computed_coverage,
            "scores": {**computed_scores, "overall": computed_overall},
        },
        "validation_warnings": warnings,
    }
