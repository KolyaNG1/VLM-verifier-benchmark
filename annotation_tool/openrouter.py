"""Небольшой клиент OpenRouter для одного запроса на описание."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .config import TOOL_ROOT


API_URL = "https://openrouter.ai/api/v1/chat/completions"


def load_local_env(path: Path | None = None) -> None:
    """Загружает непустые значения из локального .env без внешних пакетов.

    Переменная, уже заданная системой, имеет приоритет над файлом. Это позволяет
    безопасно заменить ключ в CI и не записывать его в исходный код.
    """
    source = path or TOOL_ROOT / ".env"
    if not source.is_file():
        return
    for raw_line in source.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip().removeprefix("export ").strip()
        value = value.strip().strip("'\"")
        if key and value:
            os.environ.setdefault(key, value)


class OpenRouterError(RuntimeError):
    """Ошибка ключа, сети либо ответа OpenRouter."""


class OpenRouterClient:
    def __init__(self, *, model: str, api_key: str | None = None, timeout_seconds: int = 180, attempts: int = 3) -> None:
        load_local_env()
        self.model = model
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        self.timeout_seconds = timeout_seconds
        self.attempts = attempts

    def generate(self, messages: list[dict[str, Any]]) -> tuple[str, dict[str, Any]]:
        if not self.api_key:
            raise OpenRouterError("Не задана переменная окружения OPENROUTER_API_KEY.")
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.2,
            "max_tokens": 4096,
        }
        encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = Request(
            API_URL,
            data=encoded,
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        last_error: Exception | None = None
        for attempt in range(1, self.attempts + 1):
            try:
                with urlopen(request, timeout=self.timeout_seconds) as response:
                    raw = json.loads(response.read().decode("utf-8"))
                choice = raw["choices"][0]
                if choice.get("error"):
                    raise OpenRouterError(str(choice["error"]))
                content = choice.get("message", {}).get("content")
                if not isinstance(content, str) or not content.strip():
                    raise OpenRouterError("OpenRouter не вернул непустой текст описания.")
                metadata = {
                    "generation_id": raw.get("id"),
                    "returned_model": raw.get("model"),
                    "usage": raw.get("usage", {}),
                    "attempt": attempt,
                }
                return content.strip(), metadata
            except (HTTPError, URLError, TimeoutError, ValueError, KeyError, OpenRouterError) as error:
                last_error = error
                if attempt < self.attempts:
                    time.sleep(2 ** (attempt - 1))
        raise OpenRouterError(f"Не удалось получить описание после {self.attempts} попыток: {last_error}")
