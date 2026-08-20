"""Чтение и точный выбор валидных пар ML-поднабора."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .config import DEFAULT_DATA_ROOT


class DatasetError(ValueError):
    """Набор не соответствует зафиксированному контракту."""


@dataclass(frozen=True)
class DatasetPair:
    pair_id: str
    fail_sample_id: str
    orig_sample_id: str
    fail_pic: Path
    orig_pic: Path
    caption: str
    text_block: str
    text_block_source: str
    pdf_id: str
    arxiv_id: str
    figure_id: str
    gold_is_corrupted: bool
    gold_lies: tuple[str, ...]
    gold_objects: tuple[str, ...]

    def image_descriptor(self, side: str, project_root: Path | None = None) -> dict[str, object]:
        path = self.orig_pic if side == "orig" else self.fail_pic
        descriptor: dict[str, object] = {
            "side": side,
            "path": str(path),
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
        if project_root is not None:
            try:
                descriptor["project_relative_path"] = str(path.relative_to(project_root))
            except ValueError:
                pass
        return descriptor


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    try:
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except FileNotFoundError as error:
        raise DatasetError(f"Не найден манифест: {path}") from error
    except json.JSONDecodeError as error:
        raise DatasetError(f"Некорректный JSONL в {path}: {error}") from error


def normalize_pair_id(sample_id: str) -> str:
    """Удаляет только префикс разбиения из sample_id."""
    parts = sample_id.replace("\\", "/").split("/", 1)
    if len(parts) != 2 or not parts[1]:
        raise DatasetError(f"Некорректный sample_id: {sample_id!r}")
    return parts[1]


def _resolve_image_path(data_root: Path, raw_path: str) -> Path:
    path = Path(raw_path.replace("/", "\\"))
    if path.is_absolute():
        return path.resolve()
    # Поле содержит data/verifier_v0/..., а база намеренно равна data/.
    return (data_root / path).resolve()


def load_ml_pairs(
    data_root: Path = DEFAULT_DATA_ROOT,
    *,
    include_clean: bool = False,
    verify_expected_count: bool = True,
) -> list[DatasetPair]:
    """Возвращает только пары, у которых существуют обе картинки.

    По умолчанию это ровно 243 контролируемо искажённые пары. Поле gold не
    используется для создания входа VLM и хранится только в объекте пары.
    """
    data_root = data_root.resolve()
    manifest_root = data_root / "data" / "verifier_v0"
    fail_rows = _read_jsonl(manifest_root / "manifest_ml_l2_fail.jsonl")
    orig_rows = _read_jsonl(manifest_root / "manifest_ml_orig.jsonl")
    orig_by_id = {normalize_pair_id(str(row["sample_id"])): row for row in orig_rows}
    pairs: list[DatasetPair] = []

    for row in fail_rows:
        gold = row.get("gold")
        if not isinstance(gold, dict):
            raise DatasetError(f"У {row.get('sample_id')} нет объекта gold")
        corrupted = gold.get("is_corrupted")
        if not isinstance(corrupted, bool):
            raise DatasetError(f"У {row.get('sample_id')} некорректный gold.is_corrupted")
        if not include_clean and not corrupted:
            continue

        pair_id = normalize_pair_id(str(row["sample_id"]))
        origin = orig_by_id.get(pair_id)
        if origin is None:
            raise DatasetError(f"Для {pair_id} не найдена исходная строка")
        fail_path = _resolve_image_path(data_root, str(row["image_path"]))
        orig_path = _resolve_image_path(data_root, str(origin["image_path"]))
        if not fail_path.is_file() or not orig_path.is_file():
            raise DatasetError(
                f"У пары {pair_id} отсутствует файл: fail={fail_path.is_file()}, orig={orig_path.is_file()}"
            )
        pairs.append(
            DatasetPair(
                pair_id=pair_id,
                fail_sample_id=str(row["sample_id"]),
                orig_sample_id=str(origin["sample_id"]),
                fail_pic=fail_path,
                orig_pic=orig_path,
                caption=str(row["caption"]),
                text_block=str(row["text_block"]),
                text_block_source=str(row["text_block_source"]),
                pdf_id=str(row["pdf_id"]),
                arxiv_id=str(row["arxiv_id"]),
                figure_id=str(row["figure_id"]),
                gold_is_corrupted=corrupted,
                gold_lies=tuple(str(item) for item in gold.get("lies", [])),
                gold_objects=tuple(str(item) for item in gold.get("objects", [])),
            )
        )

    if len({pair.pair_id for pair in pairs}) != len(pairs):
        raise DatasetError("В наборе обнаружены повторяющиеся pair_id")
    if verify_expected_count and not include_clean and len(pairs) != 243:
        raise DatasetError(f"Ожидалось 243 искажённые пары, найдено {len(pairs)}")
    return pairs


def _read_ids_file(path: Path) -> list[str]:
    if not path.is_file():
        raise DatasetError(f"Не найден файл идентификаторов: {path}")
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip() and not line.lstrip().startswith("#")]


def _canonical_selector(value: str) -> str:
    clean = value.strip().replace("\\", "/")
    if clean.startswith(("ml_l2_fail/", "ml_orig/")):
        return normalize_pair_id(clean)
    return clean


def select_pairs(
    pairs: Iterable[DatasetPair],
    *,
    ids: Iterable[str] = (),
    ids_file: Path | None = None,
    image_paths: Iterable[Path] = (),
    offset: int = 0,
    limit: int | None = None,
    shuffle: bool = False,
    seed: int = 42,
) -> list[DatasetPair]:
    """Выбирает пары до сетевого вызова и сохраняет порядок явного списка."""
    all_pairs = list(pairs)
    by_id = {pair.pair_id: pair for pair in all_pairs}
    by_image = {path.resolve(): pair for pair in all_pairs for path in (pair.orig_pic, pair.fail_pic)}
    requested = list(ids)
    if ids_file is not None:
        requested.extend(_read_ids_file(ids_file))
    requested_paths = [path.resolve() for path in image_paths]

    if requested or requested_paths:
        selected: list[DatasetPair] = []
        seen: set[str] = set()
        for value in requested:
            canonical = _canonical_selector(value)
            pair = by_id.get(canonical)
            if pair is None:
                raise DatasetError(f"Неизвестный идентификатор пары: {value}")
            if pair.pair_id not in seen:
                selected.append(pair)
                seen.add(pair.pair_id)
        for path in requested_paths:
            pair = by_image.get(path)
            if pair is None:
                raise DatasetError(f"Путь не принадлежит выбранной паре: {path}")
            if pair.pair_id not in seen:
                selected.append(pair)
                seen.add(pair.pair_id)
    else:
        selected = list(all_pairs)
        if shuffle:
            import random

            random.Random(seed).shuffle(selected)

    if offset < 0:
        raise DatasetError("--offset не может быть отрицательным")
    if limit is not None and limit < 1:
        raise DatasetError("--limit должен быть положительным")
    selected = selected[offset:]
    return selected if limit is None else selected[:limit]
