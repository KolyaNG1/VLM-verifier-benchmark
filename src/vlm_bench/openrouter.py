"""Минимальный клиент OpenRouter, не содержащий логики набора или метрик."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any

import requests
from dotenv import load_dotenv

from .config import BenchmarkConfig, PROJECT_ROOT


API_URL = "https://openrouter.ai/api/v1/chat/completions"


class OpenRouterError(RuntimeError):
    """Ключ или сетевой вызов OpenRouter недоступен."""


@dataclass
class NetworkResult:
    ok: bool
    raw: dict[str, Any]
    error: str | None = None


class OpenRouterClient:
    def __init__(self, config: BenchmarkConfig, api_key: str | None = None, session: requests.Session | None = None):
        load_dotenv(PROJECT_ROOT / "src" / ".env")
        self.config = config
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        self.session = session or requests.Session()

    def _payload(self, messages: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "model": self.config.model,
            "temperature": self.config.temperature,
            "top_p": self.config.top_p,
            "seed": self.config.seed,
            "max_tokens": self.config.max_tokens,
            "reasoning": {"effort": self.config.reasoning_effort},
            "include_reasoning": True,
            "response_format": {"type": "json_object"},
            "messages": messages,
        }

    def independent_client(self) -> "OpenRouterClient":
        """Создаёт клиент с отдельной HTTP-сессией для параллельного вызова."""
        return OpenRouterClient(self.config, api_key=self.api_key)

    def evaluate(self, messages: list[dict[str, Any]]) -> NetworkResult:
        if not self.api_key:
            raise OpenRouterError("Добавьте OPENROUTER_API_KEY в src/.env перед реальным запуском.")
        payload = self._payload(messages)
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        last_raw: dict[str, Any] = {}
        last_error: str | None = None
        for attempt in range(1, self.config.network_attempts + 1):
            try:
                response = self.session.post(API_URL, headers=headers, json=payload, timeout=self.config.timeout_seconds)
                try:
                    raw = response.json()
                except ValueError:
                    raw = {"response_text": response.text}
                raw["_http_status"] = response.status_code
                raw["_network_attempt"] = attempt
                last_raw = raw
                if response.ok:
                    return NetworkResult(ok=True, raw=raw)
                last_error = f"OpenRouter вернул HTTP {response.status_code}"
                if response.status_code not in {408, 409, 429, 500, 502, 503, 504}:
                    break
            except requests.RequestException as error:
                last_error = f"Сетевая ошибка: {error}"
                last_raw = {"_network_attempt": attempt, "_network_error": str(error)}
            if attempt < self.config.network_attempts:
                time.sleep((1, 3, 9)[min(attempt - 1, 2)])
        return NetworkResult(ok=False, raw=last_raw, error=last_error or "Неизвестная ошибка OpenRouter")


def extract_message(raw: dict[str, Any]) -> tuple[str, Any, dict[str, Any]]:
    """Возвращает текст JSON, доступное рассуждение и метаданные ответа."""
    try:
        choice = raw["choices"][0]
        message = choice["message"]
        content = message.get("content")
    except (KeyError, IndexError, TypeError) as error:
        raise OpenRouterError("В ответе OpenRouter нет choices[0].message.content") from error
    if not isinstance(content, str):
        raise OpenRouterError("OpenRouter не вернул текстовый ответ модели")
    reasoning = message.get("reasoning", message.get("reasoning_details"))
    metadata = {
        "generation_id": raw.get("id"),
        "returned_model": raw.get("model"),
        "created": raw.get("created"),
        "finish_reason": choice.get("finish_reason"),
        "native_finish_reason": choice.get("native_finish_reason"),
        "usage": raw.get("usage", {}),
        "http_status": raw.get("_http_status"),
    }
    return content, reasoning, metadata
