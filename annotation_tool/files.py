"""Обход изображений и соглашение о соседних файлах описаний."""

from __future__ import annotations

import hashlib
from pathlib import Path

from .config import IMAGE_SUFFIXES, project_path, relative_path


def find_images(dataset_root: str | Path) -> list[Path]:
    root = project_path(dataset_root)
    if not root.is_dir():
        raise ValueError(f"Каталог набора не найден: {relative_path(root)}")
    return sorted(
        (path for path in root.rglob("*") if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES),
        key=lambda path: relative_path(path),
    )


def annotation_path(image_path: str | Path) -> Path:
    """Описание располагается в той же папке как ``figure_N.txt``."""
    image = project_path(image_path)
    return image.with_suffix(".txt")


def item_id(image_path: str | Path) -> str:
    path = relative_path(image_path)
    return hashlib.sha256(path.encode("utf-8")).hexdigest()[:16]
