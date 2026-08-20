from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vlm_bench.artifacts import ArtifactStore
from vlm_bench.config import BenchmarkConfig
from vlm_bench.dataset import load_ml_pairs
from vlm_bench.prompting import load_template
from vlm_bench.runner import BenchmarkRunner


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


if __name__ == "__main__":
    unittest.main()
