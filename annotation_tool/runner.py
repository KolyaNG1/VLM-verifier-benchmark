"""Несколько исполнителей запросов с ограничением очереди ручной проверки."""

from __future__ import annotations

import threading
from typing import Callable

from .config import project_path
from .openrouter import OpenRouterClient
from .prompting import PromptTemplate, build_messages
from .state import ReviewState


class AnnotationRunner:
    def __init__(
        self,
        state: ReviewState,
        template: PromptTemplate,
        client: OpenRouterClient,
        *,
        workers: int,
        max_pending_review: int,
        dry_run: bool = False,
    ) -> None:
        self.state = state
        self.template = template
        self.client = client
        self.workers = workers
        self.max_pending_review = max_pending_review
        self.dry_run = dry_run
        self.stop = threading.Event()
        self.threads: list[threading.Thread] = []

    def start(self) -> None:
        for number in range(self.workers):
            thread = threading.Thread(target=self._worker, name=f"annotation-worker-{number + 1}", daemon=True)
            thread.start()
            self.threads.append(thread)

    def shutdown(self) -> None:
        self.stop.set()
        with self.state.changed:
            self.state.changed.notify_all()
        for thread in self.threads:
            thread.join(timeout=2)

    def _worker(self) -> None:
        while True:
            item = self.state.acquire_next(self.max_pending_review, self.stop)
            if item is None:
                return
            try:
                image = project_path(item["image_path"])
                if self.dry_run:
                    text = "Dry-run candidate. No request was sent to OpenRouter."
                    metadata = {"dry_run": True}
                else:
                    messages = build_messages(self.template, image, item.get("review_comment", ""))
                    text, metadata = self.client.generate(messages)
                self.state.save_candidate(item["id"], text, metadata)
            except Exception as error:  # Сохраняем ошибку на карточке, не теряя очередь.
                self.state.mark_error(item["id"], str(error))
