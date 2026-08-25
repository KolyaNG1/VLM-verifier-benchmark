"""Общие пути и безопасная работа с относительными путями."""

from __future__ import annotations

from pathlib import Path


TOOL_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = TOOL_ROOT.parent
DEFAULT_DATASET_ROOT = Path("nikolay_ai_360_student")
DEFAULT_PROMPT = Path("nikolay_ai_360_annotation/prompts/annotation_fewshot.md")
DEFAULT_ARTIFACTS_ROOT = Path("nikolay_ai_360_annotation_artifacts")
DEFAULT_STATE = DEFAULT_ARTIFACTS_ROOT / "review_state.json"
IMAGE_SUFFIXES = {".png"}


def project_path(value: str | Path) -> Path:
    """Разрешает путь относительно корня проекта и не допускает выход наружу."""
    candidate = Path(value)
    resolved = candidate.resolve() if candidate.is_absolute() else (PROJECT_ROOT / candidate).resolve()
    try:
        resolved.relative_to(PROJECT_ROOT.resolve())
    except ValueError as error:
        raise ValueError(f"Путь должен находиться внутри проекта: {value}") from error
    return resolved


def relative_path(value: str | Path) -> str:
    """Возвращает POSIX-путь относительно корня проекта для файлов состояния."""
    return project_path(value).relative_to(PROJECT_ROOT.resolve()).as_posix()
