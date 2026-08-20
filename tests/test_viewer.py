from __future__ import annotations

import json
import sys
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vlm_bench.artifacts import ArtifactStore
from vlm_bench.config import BenchmarkConfig
from vlm_bench.dataset import load_ml_pairs
from vlm_bench.prompting import load_template
from vlm_bench.runner import BenchmarkRunner
from vlm_bench.viewer_server import ViewerHandler


class ViewerTests(unittest.TestCase):
    def test_server_lists_dry_run_and_serves_interface(self) -> None:
        pair = load_ml_pairs(ROOT / "data")[0]
        template = load_template(ROOT / "prompts" / "vlm_judge" / "v001_baseline.md")
        with tempfile.TemporaryDirectory() as directory:
            store = ArtifactStore.create([pair], template, BenchmarkConfig(), Path(directory))
            BenchmarkRunner(BenchmarkConfig(), template).run_pairs(store, [pair], dry_run=True)
            old_root = ViewerHandler.runs_root
            try:
                ViewerHandler.runs_root = Path(directory)
                server = ThreadingHTTPServer(("127.0.0.1", 0), ViewerHandler)
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                base = f"http://127.0.0.1:{server.server_port}"
                with urlopen(f"{base}/api/runs", timeout=5) as response:
                    runs = json.loads(response.read())
                self.assertEqual(runs[0]["run_id"], store.run_dir.name)
                with urlopen(f"{base}/", timeout=5) as response:
                    html = response.read().decode("utf-8")
                self.assertIn("Результаты запусков", html)
            finally:
                server.shutdown()
                server.server_close()
                ViewerHandler.runs_root = old_root


if __name__ == "__main__":
    unittest.main()
