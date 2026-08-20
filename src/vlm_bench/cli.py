"""Командная строка фреймворка VLM."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .artifacts import ArtifactStore
from .config import BenchmarkConfig, DEFAULT_DATA_ROOT, DEFAULT_PROMPT_PATH, DEFAULT_RUNS_ROOT, PROJECT_ROOT
from .dataset import DatasetError, load_ml_pairs, select_pairs
from .openrouter import OpenRouterClient
from .prompting import PromptError, load_template, preview_text
from .runner import BenchmarkRunner
from .viewer_server import serve


def _path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else (PROJECT_ROOT / path)


def _config(args: argparse.Namespace) -> BenchmarkConfig:
    return BenchmarkConfig(
        model=args.model,
        temperature=args.temperature,
        top_p=args.top_p,
        seed=args.seed,
        max_tokens=args.max_tokens,
        reasoning_effort=args.reasoning_effort,
        timeout_seconds=args.timeout,
        network_attempts=args.network_attempts,
        invalid_response_attempts=args.invalid_response_attempts,
        workers=1,
        max_cost_usd=args.max_cost_usd,
        faithfulness_mid=args.faithfulness_mid,
        faithfulness_max=args.faithfulness_max,
    )


def _selection(args: argparse.Namespace, pairs: list) -> list:
    ids_file = _path(args.ids_file) if args.ids_file else None
    images = [_path(value) for value in args.image_path]
    return select_pairs(
        pairs,
        ids=args.ids,
        ids_file=ids_file,
        image_paths=images,
        offset=args.offset,
        limit=args.limit,
        shuffle=args.shuffle,
        seed=args.seed,
    )


def command_validate_dataset(args: argparse.Namespace) -> int:
    pairs = load_ml_pairs(_path(args.data_root), include_clean=args.include_clean)
    print(f"Корректных пар: {len(pairs)}")
    print(f"Первая пара: {pairs[0].pair_id}")
    return 0


def command_render_prompt(args: argparse.Namespace) -> int:
    pairs = load_ml_pairs(_path(args.data_root), include_clean=args.include_clean)
    selected = _selection(args, pairs)
    if not selected:
        raise DatasetError("Выборка пуста")
    pair = selected[0]
    template = load_template(_path(args.prompt))
    print(preview_text(template, pair, pair.orig_pic))
    return 0


def command_run(args: argparse.Namespace) -> int:
    pairs = load_ml_pairs(_path(args.data_root), include_clean=args.include_clean)
    selected = _selection(args, pairs)
    if not selected:
        raise DatasetError("Выборка пуста")
    config = _config(args)
    template = load_template(_path(args.prompt))
    store = ArtifactStore.create(selected, template, config, _path(args.runs_root))
    client = None if args.dry_run else OpenRouterClient(config)
    BenchmarkRunner(config, template, client).run_pairs(store, selected, dry_run=args.dry_run)
    print(f"Каталог запуска: {store.run_dir}")
    print(json.dumps(store.read_run()["summary"], ensure_ascii=False))
    return 0


def command_resume(args: argparse.Namespace) -> int:
    store = ArtifactStore.open(_path(args.run_dir))
    manifest = store.read_run()
    config = BenchmarkConfig.from_dict(manifest["config"])
    prompt = store.run_dir / manifest["prompt"]["copied_path"]
    template = load_template(prompt)
    pairs = load_ml_pairs(_path(args.data_root), include_clean=True, verify_expected_count=False)
    selected = select_pairs(pairs, ids=manifest["pair_ids"])
    BenchmarkRunner(config, template, OpenRouterClient(config)).run_pairs(store, selected)
    print(f"Возобновлён запуск: {store.run_dir}")
    print(json.dumps(store.read_run()["summary"], ensure_ascii=False))
    return 0


def command_viewer(args: argparse.Namespace) -> int:
    serve(port=args.port, runs_root=_path(args.runs_root))
    return 0


def _add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--data-root", default=str(DEFAULT_DATA_ROOT), help="база путей data/")
    parser.add_argument("--prompt", default=str(DEFAULT_PROMPT_PATH), help="Markdown-файл шаблона")
    parser.add_argument("--include-clean", action="store_true", help="включить неизменённые пары")
    parser.add_argument("--id", dest="ids", action="append", default=[], help="pair_id, можно повторять")
    parser.add_argument("--ids-file", help="файл pair_id, по одному на строку")
    parser.add_argument("--image-path", action="append", default=[], help="путь к orig или fail картинке")
    parser.add_argument("--limit", type=int, help="ограничить число пар")
    parser.add_argument("--offset", type=int, default=0, help="пропустить первые пары")
    parser.add_argument("--shuffle", action="store_true", help="перемешать неявно выбранные пары")
    parser.add_argument("--seed", type=int, default=42)


def _add_config(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--model", default="z-ai/glm-4.6v")
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--top-p", type=float, default=1.0)
    parser.add_argument("--max-tokens", type=int, default=4096)
    parser.add_argument("--reasoning-effort", default="medium")
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--network-attempts", type=int, default=3)
    parser.add_argument("--invalid-response-attempts", type=int, default=2)
    parser.add_argument("--max-cost-usd", type=float, default=5.0)
    parser.add_argument("--faithfulness-mid", type=float, default=0.60)
    parser.add_argument("--faithfulness-max", type=float, default=0.80)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Слепой бенчмарк VLM для пар orig/fail")
    commands = parser.add_subparsers(dest="command", required=True)

    validate = commands.add_parser("validate-dataset", help="проверить целостность 243 пар")
    validate.add_argument("--data-root", default=str(DEFAULT_DATA_ROOT))
    validate.add_argument("--include-clean", action="store_true")
    validate.set_defaults(handler=command_validate_dataset)

    render = commands.add_parser("render-prompt", help="показать промпт без сети")
    _add_common(render)
    render.set_defaults(handler=command_render_prompt)

    run = commands.add_parser("run", help="создать новый запуск")
    _add_common(run)
    _add_config(run)
    run.add_argument("--runs-root", default=str(DEFAULT_RUNS_ROOT))
    run.add_argument("--dry-run", action="store_true", help="создать артефакты без OpenRouter")
    run.set_defaults(handler=command_run)

    resume = commands.add_parser("resume", help="продолжить существующий запуск")
    resume.add_argument("run_dir")
    resume.add_argument("--data-root", default=str(DEFAULT_DATA_ROOT))
    resume.set_defaults(handler=command_resume)

    viewer = commands.add_parser("viewer", help="открыть локальный HTML-просмотрщик")
    viewer.add_argument("--runs-root", default=str(DEFAULT_RUNS_ROOT))
    viewer.add_argument("--port", type=int, default=8080)
    viewer.set_defaults(handler=command_viewer)
    return parser


def main(argv: list[str] | None = None) -> int:
    # В текстовых блоках статей встречаются символы вне cp1251; PowerShell на
    # Windows иначе может оборвать даже безопасный render-prompt.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")
    args = build_parser().parse_args(argv)
    try:
        return int(args.handler(args))
    except (DatasetError, PromptError, FileNotFoundError, ValueError) as error:
        print(f"Ошибка: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
