"""Потокобезопасное состояние очереди и атомарная запись принятых описаний."""

from __future__ import annotations

import copy
import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import project_path, relative_path
from .files import annotation_path, item_id


TERMINAL_STATUSES = {"approved", "failed"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class ReviewState:
    def __init__(self, path: str | Path, artifacts_root: str | Path) -> None:
        self.path = project_path(path)
        self.artifacts_root = project_path(artifacts_root)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.artifacts_root.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.changed = threading.Condition(self.lock)
        if self.path.is_file():
            self.data = json.loads(self.path.read_text(encoding="utf-8"))
        else:
            self.data: dict[str, Any] = {"version": 1, "created_at": _now(), "items": {}}
            self._write()

    def _write(self) -> None:
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(self.data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(self.path)

    def initialize(self, images: list[Path], *, manual_example_paths: set[Path]) -> None:
        with self.changed:
            items = self.data["items"]
            for image in images:
                identifier = item_id(image)
                output = annotation_path(image)
                if identifier in items:
                    continue
                if output.is_file() and output.read_text(encoding="utf-8").strip():
                    status = "approved"
                elif image.resolve() in manual_example_paths:
                    status = "manual_required"
                else:
                    status = "queued"
                items[identifier] = {
                    "id": identifier,
                    "image_path": relative_path(image),
                    "output_path": relative_path(output),
                    "status": status,
                    "attempts": 0,
                    "review_comment": "",
                    "candidate_path": None,
                    "candidate_metadata": None,
                    "final_annotation": None,
                    "last_review": None,
                    "error": None,
                    "updated_at": _now(),
                }
            self._write()
            self.changed.notify_all()

    def _review_backlog(self) -> int:
        return sum(item["status"] in {"generating", "awaiting_review"} for item in self.data["items"].values())

    def acquire_next(self, max_pending_review: int, stop: threading.Event) -> dict[str, Any] | None:
        with self.changed:
            while not stop.is_set():
                queued = [item for item in self.data["items"].values() if item["status"] == "queued"]
                if queued and self._review_backlog() < max_pending_review:
                    item = min(queued, key=lambda value: (value["updated_at"], value["image_path"]))
                    item["status"] = "generating"
                    item["attempts"] += 1
                    item["error"] = None
                    item["updated_at"] = _now()
                    self._write()
                    return copy.deepcopy(item)
                active = any(item["status"] in {"queued", "generating", "awaiting_review"} for item in self.data["items"].values())
                if not active:
                    return None
                self.changed.wait(timeout=1)
            return None

    def save_candidate(self, identifier: str, text: str, metadata: dict[str, Any]) -> None:
        with self.changed:
            item = self.data["items"][identifier]
            # Пока запрос шёл, человек мог сохранить собственный вариант.
            # Поздний ответ модели нельзя возвращать в очередь на проверку.
            if item["status"] != "generating":
                return
            image = project_path(item["image_path"])
            attempt = int(item["attempts"])
            candidate = image.with_name(f"{image.stem}.vlm_attempt_{attempt:03d}.md")
            revision = 2
            while candidate.exists():
                candidate = image.with_name(f"{image.stem}.vlm_attempt_{attempt:03d}_{revision}.md")
                revision += 1
            candidate.write_text(text.rstrip() + "\n", encoding="utf-8")
            item["candidate_path"] = relative_path(candidate)
            item["candidate_metadata"] = metadata
            item["status"] = "awaiting_review"
            item["updated_at"] = _now()
            self._write()
            self.changed.notify_all()

    def mark_error(self, identifier: str, error: str) -> None:
        with self.changed:
            item = self.data["items"][identifier]
            # Ручное сохранение могло опередить завершение сетевого запроса.
            if item["status"] != "generating":
                return
            item["status"] = "failed"
            item["error"] = error
            item["updated_at"] = _now()
            self._write()
            self.changed.notify_all()

    def _save_final_annotation(self, item: dict[str, Any], text: str, *, source: str, comment: str) -> None:
        clean_text = text.strip()
        if not clean_text:
            raise ValueError("Нельзя сохранить пустое описание")
        output = project_path(item["output_path"])
        output.write_text(clean_text + "\n", encoding="utf-8")
        item["status"] = "approved"
        item["final_annotation"] = clean_text
        item["last_review"] = {"decision": source, "comment": comment.strip(), "at": _now()}
        item["error"] = None

    def review(self, identifier: str, decision: str, comment: str, annotation: str = "") -> dict[str, Any]:
        with self.changed:
            item = self.data["items"].get(identifier)
            if item is None:
                raise KeyError("Изображение не найдено в очереди")
            if decision == "approve":
                if item["status"] != "awaiting_review" or not item["candidate_path"]:
                    raise ValueError("Одобрить можно только готовый ответ модели")
                candidate = project_path(item["candidate_path"])
                final_text = annotation.strip() or candidate.read_text(encoding="utf-8")
                self._save_final_annotation(item, final_text, source="approved_vlm", comment=comment)
                item["review_comment"] = comment.strip()
            elif decision in {"reject", "retry"}:
                if decision == "reject" and not comment.strip():
                    raise ValueError("Для отклонения нужен комментарий, что надо исправить")
                item["status"] = "queued"
                item["review_comment"] = comment.strip()
                item["error"] = None
                item["last_review"] = {"decision": decision, "comment": comment.strip(), "at": _now()}
            elif decision == "manual":
                self._save_final_annotation(item, annotation, source="manual", comment=comment)
            else:
                raise ValueError("Допустимы решения approve, reject, retry или manual")
            item["updated_at"] = _now()
            self._write()
            self.changed.notify_all()
            return copy.deepcopy(item)

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            items = sorted(self.data["items"].values(), key=lambda item: (item["status"], item["image_path"]))
            counts: dict[str, int] = {}
            for item in items:
                counts[item["status"]] = counts.get(item["status"], 0) + 1
            return {"counts": counts, "items": copy.deepcopy(items)}

    def detail(self, identifier: str) -> dict[str, Any] | None:
        with self.lock:
            item = self.data["items"].get(identifier)
            if item is None:
                return None
            detail = copy.deepcopy(item)
            if detail["candidate_path"]:
                candidate = project_path(detail["candidate_path"])
                detail["candidate_text"] = candidate.read_text(encoding="utf-8") if candidate.is_file() else ""
            else:
                detail["candidate_text"] = ""
            final_annotation = detail.get("final_annotation")
            if final_annotation is None:
                output = project_path(detail["output_path"])
                final_annotation = output.read_text(encoding="utf-8").strip() if output.is_file() else ""
            detail["final_annotation"] = final_annotation
            return detail

    def image_for_item(self, identifier: str) -> Path | None:
        with self.lock:
            item = self.data["items"].get(identifier)
            return project_path(item["image_path"]) if item else None
