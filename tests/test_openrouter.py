from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vlm_bench.config import BenchmarkConfig
from vlm_bench.openrouter import OpenRouterClient, extract_message


class FakeResponse:
    ok = True
    status_code = 200
    text = ""

    def json(self):
        return {
            "id": "gen-test",
            "model": "z-ai/glm-4.6v",
            "choices": [{"finish_reason": "stop", "message": {"content": "{}", "reasoning": "short"}}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2, "cost": 0.001},
        }


class FakeSession:
    def __init__(self) -> None:
        self.calls = []

    def post(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return FakeResponse()


class OpenRouterTests(unittest.TestCase):
    def test_client_builds_json_request_without_network(self) -> None:
        session = FakeSession()
        client = OpenRouterClient(BenchmarkConfig(network_attempts=1), api_key="test-key", session=session)
        result = client.evaluate([{"role": "user", "content": "test"}])
        self.assertTrue(result.ok)
        payload = session.calls[0][1]["json"]
        self.assertEqual(payload["response_format"], {"type": "json_object"})
        self.assertEqual(payload["model"], "z-ai/glm-4.6v")
        content, reasoning, metadata = extract_message(result.raw)
        self.assertEqual(content, "{}")
        self.assertEqual(reasoning, "short")
        self.assertEqual(metadata["usage"]["cost"], 0.001)


if __name__ == "__main__":
    unittest.main()
