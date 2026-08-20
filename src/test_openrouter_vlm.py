"""Описание локального изображения моделью GLM-4.6V через OpenRouter.

Запуск:
    py src/test_openrouter_vlm.py путь\\к\\картинке.png
"""

import argparse
import base64
import mimetypes
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

MODEL = "z-ai/glm-4.6v"
ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")


def image_as_data_url(image_path: Path) -> str:
    if not image_path.is_file():
        raise FileNotFoundError(f"Файл не найден: {image_path}")

    media_type, _ = mimetypes.guess_type(image_path.name)
    if media_type not in {"image/jpeg", "image/png", "image/webp", "image/gif"}:
        raise ValueError("Поддерживаются JPG, PNG, WEBP и GIF.")

    encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
    return f"data:{media_type};base64,{encoded}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Запрос к GLM-4.6V с локальной картинкой")
    parser.add_argument("image", type=Path, help="путь к JPG, PNG, WEBP или GIF")
    args = parser.parse_args()

    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        sys.exit("Добавьте OPENROUTER_API_KEY в src/.env и повторите запуск.")

    try:
        data_url = image_as_data_url(args.image)
    except (FileNotFoundError, ValueError) as error:
        sys.exit(str(error))

    payload = {
        "model": MODEL,
        "max_tokens": 500,
        # Для описания картинки рассуждение не требуется: иначе оно может занять
        # весь лимит ответа, не оставив токенов на видимый пользователю текст.
        "reasoning": {"effort": "none"},
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "Подробно и строго на русском языке опиши, что изображено "
                            "на картинке. Не выдумывай детали, которых не видно."
                        ),
                    },
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            }
        ],
    }
    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json=payload,
        timeout=120,
    )
    if not response.ok:
        sys.exit(f"Ошибка OpenRouter ({response.status_code}): {response.text}")

    result = response.json()
    choice = result["choices"][0]
    answer = choice["message"].get("content")
    usage = result.get("usage", {})

    print(f"Модель: {MODEL}")
    print("\nОтвет модели:\n")
    if answer:
        print(answer)
    else:
        print(
            "Модель не вернула текст. Причина остановки: "
            f"{choice.get('finish_reason', 'не указана')}"
        )
    print("\nСтоимость запроса (USD):", usage.get("cost", "не передана сервисом"))
    print("Использование токенов:", usage)


if __name__ == "__main__":
    main()
