"""Конфигурация воспроизводимого запуска."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA_ROOT = PROJECT_ROOT / "data"
DEFAULT_PROMPT_PATH = PROJECT_ROOT / "prompts" / "vlm_judge" / "v001_baseline.md"
DEFAULT_RUNS_ROOT = PROJECT_ROOT / "runs"


@dataclass(frozen=True)
class BenchmarkConfig:
    """Параметры, которые обязательно сохраняются вместе с запуском."""

    model: str = "z-ai/glm-4.6v"
    temperature: float = 0.0
    top_p: float = 1.0
    seed: int = 42
    # Рассуждение и итоговый JSON делят один лимит у OpenRouter. 16K оставляет
    # достаточно места сложной визуальной проверке и структурированному аудиту.
    max_tokens: int = 16384
    reasoning_effort: str = "medium"
    timeout_seconds: int = 180
    network_attempts: int = 3
    invalid_response_attempts: int = 2
    pair_workers: int = 1
    # Пары запускаются последовательно; внутри каждой стороны выполняются
    # параллельно, поэтому этот снимок конфигурации остаётся равным одному.
    workers: int = 1
    # Обычный запуск не имеет денежного потолка. Для контролируемого прогона
    # пользователь может явно передать --max-cost-usd.
    max_cost_usd: float | None = None
    faithfulness_mid: float = 0.60
    faithfulness_max: float = 0.80
    weight_faithfulness: float = 0.45
    weight_clarity: float = 0.25
    weight_compactness: float = 0.15
    weight_style: float = 0.15
    protocol: str = "blind_orig_fail_parallel_v1"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "BenchmarkConfig":
        allowed = {field.name for field in cls.__dataclass_fields__.values()}
        return cls(**{key: item for key, item in value.items() if key in allowed})
