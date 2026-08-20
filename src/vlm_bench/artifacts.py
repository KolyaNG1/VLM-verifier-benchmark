"""Самодостаточные и атомарно записываемые артефакты запусков."""

from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .config import BenchmarkConfig, DEFAULT_RUNS_ROOT, PROJECT_ROOT
from .dataset import DatasetPair
from .prompting import PromptTemplate


def _json_default(value: object) -> object:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, tuple):
        return list(value)
    raise TypeError(f"Нельзя записать в JSON: {type(value).__name__}")


def atomic_write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, default=_json_default) + "\n"
    handle, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent, text=True)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as target:
            target.write(payload)
            target.flush()
            os.fsync(target.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _slug(value: str) -> str:
    return re.sub(r"[^\w.-]+", "_", value, flags=re.UNICODE).strip("_") or "run"


def _display_name(value: str | None, *, config: BenchmarkConfig, template: PromptTemplate) -> str:
    if value is None:
        return f"{template.path.stem} · {config.model}"
    name = value.strip()
    if not name:
        raise ValueError("Название запуска не может быть пустым")
    if len(name) > 120:
        raise ValueError("Название запуска не должно быть длиннее 120 символов")
    if any(ord(character) < 32 for character in name):
        raise ValueError("Название запуска содержит недопустимый управляющий символ")
    return name


def pair_directory_name(pair_id: str) -> str:
    return pair_id.replace("/", "__").replace("\\", "__")


def pair_payload(pair: DatasetPair) -> dict[str, Any]:
    return {
        "pair_id": pair.pair_id,
        "sample_ids": {"fail": pair.fail_sample_id, "orig": pair.orig_sample_id},
        "article": {"pdf_id": pair.pdf_id, "arxiv_id": pair.arxiv_id, "figure_id": pair.figure_id},
        "caption": pair.caption,
        "text_block": pair.text_block,
        "text_block_source": pair.text_block_source,
        "images": {
            "orig": pair.image_descriptor("orig", PROJECT_ROOT),
            "fail": pair.image_descriptor("fail", PROJECT_ROOT),
        },
        "gold": {
            "is_corrupted": pair.gold_is_corrupted,
            "lies": list(pair.gold_lies),
            "objects": list(pair.gold_objects),
        },
    }


class ArtifactStore:
    """Работает как с новым, так и с возобновляемым запуском."""

    def __init__(self, run_dir: Path):
        self.run_dir = run_dir.resolve()

    @property
    def run_path(self) -> Path:
        return self.run_dir / "run.json"

    @property
    def index_path(self) -> Path:
        return self.run_dir / "samples.jsonl"

    @classmethod
    def create(
        cls,
        pairs: list[DatasetPair],
        template: PromptTemplate,
        config: BenchmarkConfig,
        runs_root: Path = DEFAULT_RUNS_ROOT,
        display_name: str | None = None,
    ) -> "ArtifactStore":
        runs_root = runs_root.resolve()
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        display_name = _display_name(display_name, config=config, template=template)
        run_id = f"{timestamp}__{_slug(display_name)}__{_slug(config.model)}__{template.sha256[:8]}"
        run_dir = runs_root / run_id
        suffix = 1
        while run_dir.exists():
            suffix += 1
            run_dir = runs_root / f"{run_id}_{suffix}"
        run_dir.mkdir(parents=True)
        store = cls(run_dir)
        prompt_dir = run_dir / "prompt"
        prompt_dir.mkdir()
        shutil.copy2(template.path, prompt_dir / template.path.name)
        manifest = {
            "run_id": run_dir.name,
            "display_name": display_name,
            "status": "running",
            "created_at": datetime.now(UTC).isoformat(),
            "updated_at": datetime.now(UTC).isoformat(),
            "protocol": config.protocol,
            "config": config.as_dict(),
            "prompt": {
                "source_path": str(template.path),
                "copied_path": str((prompt_dir / template.path.name).relative_to(run_dir)),
                "name": template.name,
                "sha256": template.sha256,
                "marker_counts": template.marker_counts(),
            },
            "pair_ids": [pair.pair_id for pair in pairs],
            "summary": {"pairs": len(pairs), "complete": 0, "partial": 0, "failed": 0, "cost_usd": 0.0, "calls": 0},
        }
        atomic_write_json(store.run_path, manifest)
        store.index_path.touch()
        for pair in pairs:
            store.write_pair(pair)
        return store

    @classmethod
    def open(cls, run_dir: Path) -> "ArtifactStore":
        store = cls(run_dir)
        if not store.run_path.is_file():
            raise FileNotFoundError(f"Не найден run.json: {store.run_path}")
        return store

    def read_run(self) -> dict[str, Any]:
        return read_json(self.run_path)

    def pair_dir(self, pair_id: str) -> Path:
        return self.run_dir / "samples" / pair_directory_name(pair_id)

    def write_pair(self, pair: DatasetPair) -> None:
        atomic_write_json(self.pair_dir(pair.pair_id) / "pair.json", pair_payload(pair))

    def read_pair(self, pair_id: str) -> dict[str, Any]:
        return read_json(self.pair_dir(pair_id) / "pair.json")

    def update_pair(self, pair_id: str, **updates: Any) -> dict[str, Any]:
        value = self.read_pair(pair_id)
        value.update(updates)
        atomic_write_json(self.pair_dir(pair_id) / "pair.json", value)
        return value

    def side_dir(self, pair_id: str, side: str) -> Path:
        if side not in {"orig", "fail"}:
            raise ValueError(f"Неизвестная сторона пары: {side}")
        return self.pair_dir(pair_id) / side

    def result_path(self, pair_id: str, side: str) -> Path:
        return self.side_dir(pair_id, side) / "result.json"

    def read_result(self, pair_id: str, side: str) -> dict[str, Any] | None:
        path = self.result_path(pair_id, side)
        return read_json(path) if path.is_file() else None

    def write_attempt_response(self, pair_id: str, side: str, attempt: int, raw: dict[str, Any]) -> Path:
        path = self.side_dir(pair_id, side) / f"response.attempt_{attempt:02d}.raw.json"
        atomic_write_json(path, raw)
        atomic_write_json(self.side_dir(pair_id, side) / "response.raw.json", raw)
        return path

    def write_call(self, pair_id: str, side: str, request: dict[str, Any], result: dict[str, Any]) -> None:
        side_dir = self.side_dir(pair_id, side)
        atomic_write_json(side_dir / "request.json", request)
        atomic_write_json(side_dir / "result.json", result)

    def _index_records(self) -> list[dict[str, Any]]:
        if not self.index_path.is_file():
            return []
        return [json.loads(line) for line in self.index_path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def upsert_index(self, record: dict[str, Any]) -> None:
        records = [item for item in self._index_records() if item.get("pair_id") != record.get("pair_id")]
        records.append(record)
        lines = "".join(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n" for item in records)
        path = self.index_path
        handle, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent, text=True)
        try:
            with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as target:
                target.write(lines)
                target.flush()
                os.fsync(target.fileno())
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def refresh_summary(self, status: str | None = None) -> dict[str, Any]:
        manifest = self.read_run()
        records = self._index_records()
        summary = {"pairs": len(manifest["pair_ids"]), "complete": 0, "partial": 0, "failed": 0, "cost_usd": 0.0, "calls": 0}
        for record in records:
            state = record.get("status")
            if state in {"complete", "partial", "failed"}:
                summary[state] += 1
            for side in ("orig", "fail"):
                item = record.get(side, {})
                if item:
                    summary["calls"] += 1
                    summary["cost_usd"] += float(item.get("cost_usd") or 0.0)
        manifest["summary"] = summary
        manifest["updated_at"] = datetime.now(UTC).isoformat()
        if status is not None:
            manifest["status"] = status
        atomic_write_json(self.run_path, manifest)
        return manifest

    def total_cost(self) -> float:
        return float(self.read_run().get("summary", {}).get("cost_usd") or 0.0)
