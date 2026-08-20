from __future__ import annotations

import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vlm_bench.artifacts import ArtifactStore
from vlm_bench.config import BenchmarkConfig
from vlm_bench.dataset import load_ml_pairs
from vlm_bench.openrouter import NetworkResult
from vlm_bench.prompting import load_template
from vlm_bench.runner import BenchmarkRunner


class InvalidJsonClient:
    def evaluate(self, _messages: list[dict]) -> NetworkResult:
        return NetworkResult(
            ok=True,
            raw={
                "_http_status": 200,
                "choices": [{"message": {"content": ""}, "finish_reason": "length"}],
                "usage": {"cost": 0.01},
            },
        )


class BarrierClient:
    def __init__(self) -> None:
        self.barrier = threading.Barrier(2)
        self.calls = 0
        self.lock = threading.Lock()

    def evaluate(self, _messages: list[dict]) -> NetworkResult:
        self.barrier.wait(timeout=2)
        with self.lock:
            self.calls += 1
        answer = {
            "text_entities": [
                {"id": "T1", "entity": "A", "text_evidence": "A"},
                {"id": "T2", "entity": "B", "text_evidence": "B"},
                {"id": "T3", "entity": "C", "text_evidence": "C"},
            ],
            "visual_entities": [],
            "entity_checks": [
                {"text_entity_id": "T1", "status": "missing"},
                {"text_entity_id": "T2", "status": "missing"},
                {"text_entity_id": "T3", "status": "missing"},
            ],
            "unsupported_visual_entities": [],
            "scores": {"faithfulness": 1, "clarity": 3, "compactness": 3, "style": 3},
            "audit": {"faithfulness": "ok", "clarity": "ok", "compactness": "ok", "style": "ok"},
        }
        return NetworkResult(ok=True, raw={"_http_status": 200, "choices": [{"message": {"content": json.dumps(answer)}}], "usage": {"cost": 0.01}})


class RunnerTests(unittest.TestCase):
    def test_dry_run_creates_auditable_pair_without_network(self) -> None:
        pair = load_ml_pairs(ROOT / "data")[0]
        template = load_template(ROOT / "prompts" / "vlm_judge" / "v001_baseline.md")
        with tempfile.TemporaryDirectory() as directory:
            store = ArtifactStore.create([pair], template, BenchmarkConfig(), Path(directory))
            BenchmarkRunner(BenchmarkConfig(), template).run_pairs(store, [pair], dry_run=True)
            self.assertEqual(store.read_run()["status"], "dry_run")
            self.assertTrue(store.result_path(pair.pair_id, "orig").is_file())
            self.assertTrue(store.result_path(pair.pair_id, "fail").is_file())
            request = (store.side_dir(pair.pair_id, "orig") / "request.json").read_text(encoding="utf-8")
            self.assertNotIn("base64,", request)

    def test_invalid_responses_count_cost_and_fail_run(self) -> None:
        pair = load_ml_pairs(ROOT / "data")[0]
        template = load_template(ROOT / "prompts" / "vlm_judge" / "v001_baseline.md")
        config = BenchmarkConfig(invalid_response_attempts=2)
        with tempfile.TemporaryDirectory() as directory:
            store = ArtifactStore.create([pair], template, config, Path(directory))
            BenchmarkRunner(config, template, InvalidJsonClient()).run_pairs(store, [pair])
            run = store.read_run()
            self.assertEqual(run["status"], "failed")
            self.assertEqual(run["summary"]["failed"], 1)
            self.assertAlmostEqual(run["summary"]["cost_usd"], 0.04)

    def test_pair_sides_are_sent_in_parallel_and_stored_separately(self) -> None:
        pair = load_ml_pairs(ROOT / "data")[0]
        template = load_template(ROOT / "prompts" / "vlm_judge" / "v001_baseline.md")
        client = BarrierClient()
        config = BenchmarkConfig(invalid_response_attempts=1)
        with tempfile.TemporaryDirectory() as directory:
            store = ArtifactStore.create([pair], template, config, Path(directory))
            BenchmarkRunner(config, template, client).run_pairs(store, [pair])
            self.assertEqual(client.calls, 2)
            self.assertEqual(store.read_run()["status"], "complete")
            self.assertTrue(store.result_path(pair.pair_id, "orig").is_file())
            self.assertTrue(store.result_path(pair.pair_id, "fail").is_file())


if __name__ == "__main__":
    unittest.main()
