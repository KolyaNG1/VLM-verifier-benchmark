"""Markdown-шаблоны и безопасное представление мультимодального запроса."""

from __future__ import annotations

import base64
import hashlib
import mimetypes
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .dataset import DatasetPair, sha256_file


MARKER_RE = re.compile(r"(<caption>|<text>|<image>)")
SYSTEM_MESSAGE = (
    "Ты судья научной иллюстрации. Следуй пользовательскому шаблону и верни "
    "ровно один JSON-объект без Markdown-ограждения."
)


class PromptError(ValueError):
    """Шаблон нельзя безопасно превратить в запрос."""


@dataclass(frozen=True)
class PromptTemplate:
    path: Path
    source: str
    sha256: str

    @property
    def name(self) -> str:
        return self.path.name

    def marker_counts(self) -> dict[str, int]:
        return {marker: self.source.count(marker) for marker in ("<caption>", "<text>", "<image>")}


def load_template(path: Path) -> PromptTemplate:
    path = path.resolve()
    if not path.is_file():
        raise PromptError(f"Не найден файл промпта: {path}")
    source = path.read_text(encoding="utf-8")
    if not source.strip():
        raise PromptError("Файл промпта пуст")
    return PromptTemplate(path=path, source=source, sha256=hashlib.sha256(source.encode("utf-8")).hexdigest())


def _data_url(image_path: Path) -> str:
    media_type, _ = mimetypes.guess_type(image_path.name)
    if media_type not in {"image/jpeg", "image/png", "image/webp", "image/gif"}:
        raise PromptError(f"Неподдерживаемый формат картинки: {image_path}")
    encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
    return f"data:{media_type};base64,{encoded}"


def build_messages(template: PromptTemplate, pair: DatasetPair, image_path: Path) -> list[dict[str, Any]]:
    """Рендерит маркеры слева направо в части пользовательского сообщения."""
    parts: list[dict[str, Any]] = []
    chunks = MARKER_RE.split(template.source)
    for chunk in chunks:
        if not chunk:
            continue
        if chunk == "<caption>":
            parts.append({"type": "text", "text": pair.caption})
        elif chunk == "<text>":
            parts.append({"type": "text", "text": pair.text_block})
        elif chunk == "<image>":
            parts.append({"type": "image_url", "image_url": {"url": _data_url(image_path)}})
        else:
            parts.append({"type": "text", "text": chunk})
    if not any(part["type"] == "image_url" for part in parts):
        raise PromptError("В промпте нет <image>; VLM не получит картинку")
    return [{"role": "system", "content": SYSTEM_MESSAGE}, {"role": "user", "content": parts}]


def safe_messages(template: PromptTemplate, pair: DatasetPair, image_path: Path, project_root: Path) -> list[dict[str, Any]]:
    """Представление запроса для артефакта: без base64 и без секрета."""
    image_path = image_path.resolve()
    media_type, _ = mimetypes.guess_type(image_path.name)
    try:
        relative = str(image_path.relative_to(project_root.resolve()))
    except ValueError:
        relative = str(image_path)
    image_descriptor = {
        "path": relative,
        "media_type": media_type,
        "bytes": image_path.stat().st_size,
        "sha256": sha256_file(image_path),
    }
    parts: list[dict[str, Any]] = []
    for chunk in MARKER_RE.split(template.source):
        if not chunk:
            continue
        if chunk == "<caption>":
            parts.append({"type": "text", "text": pair.caption})
        elif chunk == "<text>":
            parts.append({"type": "text", "text": pair.text_block})
        elif chunk == "<image>":
            parts.append({"type": "image_url", "image": image_descriptor})
        else:
            parts.append({"type": "text", "text": chunk})
    return [{"role": "system", "content": SYSTEM_MESSAGE}, {"role": "user", "content": parts}]


def preview_text(template: PromptTemplate, pair: DatasetPair, image_path: Path) -> str:
    """Текстовая проверка шаблона без кодирования изображения."""
    return (
        template.source.replace("<caption>", pair.caption)
        .replace("<text>", pair.text_block)
        .replace("<image>", f"[IMAGE: {image_path}]")
    )
