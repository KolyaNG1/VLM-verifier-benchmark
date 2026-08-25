"""Команды проверки промпта, запуска очереди и открытия просмотрщика."""

from __future__ import annotations

import argparse
import sys
import webbrowser
from pathlib import Path

from .config import DEFAULT_ARTIFACTS_ROOT, DEFAULT_DATASET_ROOT, DEFAULT_PROMPT, DEFAULT_STATE, relative_path
from .files import find_images
from .openrouter import OpenRouterClient
from .prompting import load_prompt
from .runner import AnnotationRunner
from .state import ReviewState
from .viewer_server import create_server


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Разметка изображений через OpenRouter с ручной проверкой.")
    parser.add_argument("command", choices=("validate", "run", "serve"))
    parser.add_argument("--dataset-root", default=str(DEFAULT_DATASET_ROOT), help="Относительный путь к набору PNG")
    parser.add_argument("--prompt-file", default=str(DEFAULT_PROMPT), help="Относительный путь к Markdown-промпту")
    parser.add_argument("--state-file", default=str(DEFAULT_STATE), help="Относительный путь к состоянию очереди")
    parser.add_argument("--artifacts-dir", default=str(DEFAULT_ARTIFACTS_ROOT), help="Соседний каталог состояния и журнала просмотрщика")
    parser.add_argument("--model", default="openai/gpt-5.6-sol", help="Идентификатор модели OpenRouter")
    parser.add_argument("--workers", type=int, default=3, help="Число параллельных запросов")
    parser.add_argument("--max-pending-review", type=int, default=6, help="Максимум ответов, ожидающих человека")
    parser.add_argument("--port", type=int, default=8765, help="Порт локального просмотрщика")
    parser.add_argument("--limit", type=int, default=None, help="Ограничить число изображений для пробного запуска")
    parser.add_argument("--offset", type=int, default=0, help="Пропустить столько же подходящих изображений перед --limit")
    parser.add_argument("--dry-run", action="store_true", help="Создать кандидаты без сетевых запросов")
    parser.add_argument("--no-browser", action="store_true", help="Не открывать браузер автоматически")
    return parser


def _load(args: argparse.Namespace):
    template = load_prompt(args.prompt_file)
    images = find_images(args.dataset_root)
    if args.offset < 0:
        raise ValueError("--offset не может быть отрицательным")
    # Ручные примеры передаются модели как контекст, но не должны попасть в
    # тестовый запуск как кандидаты на автоматическую разметку.
    if args.command == "run":
        example_paths = {example.image_path.resolve() for example in template.examples}
        images = [image for image in images if image.resolve() not in example_paths]
    if args.offset:
        images = images[args.offset :]
    if args.limit is not None:
        if args.limit < 1:
            raise ValueError("--limit должен быть положительным")
        images = images[: args.limit]
    return template, images


def _print_validation(template, images) -> None:
    print(f"Картинок найдено: {len(images)}")
    print(f"Ручных примеров: {len(template.examples)}")
    for number, example in enumerate(template.examples, start=1):
        print(f"{number}. {relative_path(example.image_path)} -> {relative_path(example.annotation_path)}")
    template.require_ready_examples()
    print("Промпт и ручной пример готовы к запуску.")


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        template, images = _load(args)
        if args.command == "validate":
            _print_validation(template, images)
            return 0
        if args.command == "run":
            _print_validation(template, images)
        manual_paths = {example.image_path.resolve() for example in template.examples}
        state = ReviewState(args.state_file, args.artifacts_dir)
        state.initialize(images, manual_example_paths=manual_paths)
        server = create_server(state, args.port)
        address = f"http://127.0.0.1:{server.server_port}"
        if args.command == "serve":
            print(f"Просмотрщик открыт: {address}")
            if not args.no_browser:
                webbrowser.open(address)
            server.serve_forever()
            return 0
        if args.workers < 1 or args.max_pending_review < args.workers:
            raise ValueError("Нужно не менее одного исполнителя, а --max-pending-review не меньше --workers")
        runner = AnnotationRunner(
            state,
            template,
            OpenRouterClient(model=args.model),
            workers=args.workers,
            max_pending_review=args.max_pending_review,
            dry_run=args.dry_run,
        )
        runner.start()
        print(f"Очередь и просмотрщик открыты: {address}")
        print("Каждый ответ модели сохраняется рядом с PNG; одобрение записывает figure_N.txt.")
        if not args.no_browser:
            webbrowser.open(address)
        try:
            server.serve_forever()
        finally:
            runner.shutdown()
            server.server_close()
        return 0
    except (ValueError, OSError) as error:
        print(f"Ошибка: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
