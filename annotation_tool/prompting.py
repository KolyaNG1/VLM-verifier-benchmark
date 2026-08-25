"""Чтение Markdown-промпта и сборка мультимодальных сообщений."""

from __future__ import annotations

import base64
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import project_path, relative_path


@dataclass(frozen=True)
class FewShotExample:
    image_path: Path
    annotation_path: Path


@dataclass(frozen=True)
class PromptTemplate:
    path: Path
    instructions: str
    examples: tuple[FewShotExample, ...]

    def require_ready_examples(self) -> None:
        if not self.examples:
            raise ValueError("В промпте должен быть хотя бы один ручной пример.")
        missing: list[str] = []
        for example in self.examples:
            if not example.image_path.is_file():
                missing.append(f"нет картинки {relative_path(example.image_path)}")
            if not example.annotation_path.is_file() or not example.annotation_path.read_text(encoding="utf-8").strip():
                missing.append(f"нет ручного описания {relative_path(example.annotation_path)}")
        if missing:
            raise ValueError("Нельзя запустить модель, пока не готов ручной пример:\n- " + "\n- ".join(missing))


def _parse_front_matter(text: str, source: Path) -> tuple[list[FewShotExample], str]:
    if not text.startswith("---\n"):
        raise ValueError(f"Промпт {relative_path(source)} должен начинаться с YAML-шапки между ---")
    end = text.find("\n---", 4)
    if end < 0:
        raise ValueError(f"В промпте {relative_path(source)} не закрыта YAML-шапка")
    metadata = text[4:end].splitlines()
    body = text[end + 4 :].lstrip("\r\n")
    examples: list[FewShotExample] = []
    pending_image: str | None = None
    pending_annotation: str | None = None
    in_examples = False

    def flush() -> None:
        nonlocal pending_image, pending_annotation
        if pending_image is None and pending_annotation is None:
            return
        if not pending_image or not pending_annotation:
            raise ValueError(f"Неполная пара few-shot в {relative_path(source)}")
        examples.append(FewShotExample(project_path(pending_image), project_path(pending_annotation)))
        pending_image = None
        pending_annotation = None

    for raw in metadata:
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped == "few_shot_examples:":
            in_examples = True
            continue
        if not in_examples:
            continue
        if stripped.startswith("- image:"):
            flush()
            pending_image = stripped.split(":", 1)[1].strip().strip("'\"")
            continue
        if stripped.startswith("annotation:"):
            pending_annotation = stripped.split(":", 1)[1].strip().strip("'\"")
            continue
        raise ValueError(f"Неизвестная строка шапки промпта: {raw}")
    flush()
    return examples, body


def load_prompt(path: str | Path) -> PromptTemplate:
    source = project_path(path)
    if not source.is_file():
        raise ValueError(f"Файл промпта не найден: {relative_path(source)}")
    examples, instructions = _parse_front_matter(source.read_text(encoding="utf-8"), source)
    if not instructions.strip():
        raise ValueError(f"В промпте {relative_path(source)} отсутствует текст инструкции")
    return PromptTemplate(source, instructions.strip(), tuple(examples))


def _image_part(path: Path) -> dict[str, Any]:
    mime_type = "image/png" if path.suffix.lower() == ".png" else "application/octet-stream"
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{data}"}}


def build_messages(template: PromptTemplate, image_path: str | Path, feedback: str = "") -> list[dict[str, Any]]:
    """Прикладывает ручные примеры и ответы, не передавая модели их пути."""
    image = project_path(image_path)
    messages: list[dict[str, Any]] = [
        {
            "role": "system",
            "content": "You create precise English descriptions of scientific diagrams. Follow the user's examples and instructions exactly.",
        }
    ]
    for number, example in enumerate(template.examples, start=1):
        annotation = example.annotation_path.read_text(encoding="utf-8").strip()
        messages.append(
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": f"Example {number}: describe this image."},
                    _image_part(example.image_path),
                ],
            }
        )
        messages.append({"role": "assistant", "content": annotation})
    final_text = template.instructions
    if feedback.strip():
        final_text += "\n\nA human reviewer rejected the previous answer. Correct the following issue:\n" + feedback.strip()
    messages.append(
        {
            "role": "user",
            "content": [{"type": "text", "text": final_text}, _image_part(image)],
        }
    )
    return messages


def text_parts(messages: list[dict[str, Any]]) -> list[str]:
    """Тестовый помощник: возвращает только текст, который попадёт в запрос."""
    result: list[str] = []
    for message in messages:
        content = message["content"]
        if isinstance(content, str):
            result.append(content)
        else:
            result.extend(part["text"] for part in content if part["type"] == "text")
    return result
