"""Последовательный исполнитель независимых вызовов orig → fail."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .artifacts import ArtifactStore
from .config import BenchmarkConfig, PROJECT_ROOT
from .dataset import DatasetPair
from .openrouter import OpenRouterClient, OpenRouterError, extract_message
from .prompting import PromptTemplate, build_messages, safe_messages
from .scoring import outcome
from .schemas import EvaluationError, parse_and_normalize


class BenchmarkRunner:
    def __init__(self, config: BenchmarkConfig, template: PromptTemplate, client: OpenRouterClient | None = None):
        self.config = config
        self.template = template
        self.client = client

    def _request_artifact(self, pair: DatasetPair, side: str) -> dict[str, Any]:
        image = pair.orig_pic if side == "orig" else pair.fail_pic
        return {
            "created_at": datetime.now(UTC).isoformat(),
            "side": side,
            "model": self.config.model,
            "parameters": self.config.as_dict(),
            "messages": safe_messages(self.template, pair, image, PROJECT_ROOT),
        }

    def _side(self, store: ArtifactStore, pair: DatasetPair, side: str, dry_run: bool) -> dict[str, Any]:
        previous = store.read_result(pair.pair_id, side)
        if previous and previous.get("status") == "success":
            return previous
        request = self._request_artifact(pair, side)
        if dry_run:
            result = {"status": "dry_run", "side": side, "provider_reasoning": None, "provider_metadata": {}, "computed": None}
            store.write_call(pair.pair_id, side, request, result)
            return result
        if store.total_cost() >= self.config.max_cost_usd:
            result = {"status": "budget_exhausted", "side": side, "provider_reasoning": None, "provider_metadata": {}, "computed": None}
            store.write_call(pair.pair_id, side, request, result)
            return result
        if self.client is None:
            raise RuntimeError("Для реального запуска нужен OpenRouterClient")

        image = pair.orig_pic if side == "orig" else pair.fail_pic
        messages = build_messages(self.template, pair, image)
        validation_errors: list[str] = []
        for model_attempt in range(1, self.config.invalid_response_attempts + 1):
            network = self.client.evaluate(messages)
            store.write_attempt_response(pair.pair_id, side, model_attempt, network.raw)
            if not network.ok:
                result = {
                    "status": "network_error",
                    "side": side,
                    "provider_reasoning": None,
                    "provider_metadata": {"usage": network.raw.get("usage", {}), "network_error": network.error},
                    "validation_errors": validation_errors,
                    "computed": None,
                }
                store.write_call(pair.pair_id, side, request, result)
                return result
            try:
                content, reasoning, metadata = extract_message(network.raw)
                normalized = parse_and_normalize(content, self.config)
            except (OpenRouterError, EvaluationError) as error:
                validation_errors.append(str(error))
                if model_attempt < self.config.invalid_response_attempts:
                    continue
                result = {
                    "status": "invalid_response",
                    "side": side,
                    "provider_reasoning": None,
                    "provider_metadata": network.raw.get("usage", {}),
                    "validation_errors": validation_errors,
                    "computed": None,
                }
                store.write_call(pair.pair_id, side, request, result)
                return result
            result = {
                **normalized,
                "side": side,
                "provider_reasoning": reasoning,
                "provider_metadata": metadata,
                "validation_errors": validation_errors,
            }
            store.write_call(pair.pair_id, side, request, result)
            return result
        raise AssertionError("Цикл ответов должен завершиться возвратом")

    @staticmethod
    def _cost(result: dict[str, Any]) -> float:
        metadata = result.get("provider_metadata") or {}
        usage = metadata.get("usage") or {}
        return float(usage.get("cost") or 0.0) if isinstance(usage, dict) else 0.0

    def _index_record(self, pair: DatasetPair, orig: dict[str, Any], fail: dict[str, Any]) -> dict[str, Any]:
        def side_record(value: dict[str, Any]) -> dict[str, Any]:
            computed = value.get("computed") or {}
            return {"status": value.get("status"), "scores": computed.get("scores"), "cost_usd": self._cost(value)}

        comparison: dict[str, str] | None = None
        status = "partial"
        if orig.get("status") == "success" and fail.get("status") == "success":
            original_scores = orig["computed"]["scores"]
            failed_scores = fail["computed"]["scores"]
            comparison = {name: outcome(original_scores[name], failed_scores[name]) for name in ("faithfulness", "clarity", "compactness", "style", "overall")}
            status = "complete"
        elif orig.get("status") in {"network_error", "invalid_response", "budget_exhausted"} and fail.get("status") in {"network_error", "invalid_response", "budget_exhausted"}:
            status = "failed"
        return {
            "pair_id": pair.pair_id,
            "pair_directory": self._pair_directory(pair),
            "status": status,
            "gold_is_corrupted": pair.gold_is_corrupted,
            "orig": side_record(orig),
            "fail": side_record(fail),
            "comparison": comparison,
        }

    @staticmethod
    def _pair_directory(pair: DatasetPair) -> str:
        return pair.pair_id.replace("/", "__")

    def run_pairs(self, store: ArtifactStore, pairs: list[DatasetPair], *, dry_run: bool = False) -> ArtifactStore:
        for pair in pairs:
            orig = self._side(store, pair, "orig", dry_run)
            fail = self._side(store, pair, "fail", dry_run)
            record = self._index_record(pair, orig, fail)
            store.update_pair(pair.pair_id, run_status=record["status"], comparison=record["comparison"])
            store.upsert_index(record)
            store.refresh_summary()
        final_status = "dry_run" if dry_run else "complete"
        store.refresh_summary(status=final_status)
        return store
