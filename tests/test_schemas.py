from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vlm_bench.config import BenchmarkConfig
from vlm_bench.schemas import EvaluationError, parse_and_normalize


def valid_response() -> dict:
    return {
        "schema_version": "1.0",
        "text_entities": [
            {"id": "T1", "entity": "A", "text_evidence": "A"},
            {"id": "T2", "entity": "B", "text_evidence": "B"},
            {"id": "T3", "entity": "C", "text_evidence": "C"},
        ],
        "visual_entities": [{"id": "V1", "entity": "A", "visual_evidence": "shown"}],
        "entity_checks": [
            {"text_entity_id": "T1", "visual_entity_ids": ["V1"], "status": "supported"},
            {"text_entity_id": "T2", "visual_entity_ids": [], "status": "supported"},
            {"text_entity_id": "T3", "visual_entity_ids": [], "status": "missing"},
        ],
        "unsupported_visual_entities": [],
        "counts": {"P": 2, "U": 0, "M": 1},
        "coverage": 2 / 3,
        "scores": {"faithfulness": 3, "clarity": 3, "compactness": 3, "style": 3, "overall": 3.0},
        "audit": {"faithfulness": "ok", "clarity": "ok", "compactness": "ok", "style": "ok", "warnings": []},
    }


class SchemaTests(unittest.TestCase):
    def test_local_score_is_authoritative(self) -> None:
        result = parse_and_normalize(json.dumps(valid_response()), BenchmarkConfig())
        self.assertEqual(result["computed"]["scores"]["faithfulness"], 3)
        self.assertEqual(result["computed"]["scores"]["overall"], 3.0)

    def test_less_than_three_entities_is_invalid(self) -> None:
        value = valid_response()
        value["text_entities"] = value["text_entities"][:2]
        with self.assertRaises(EvaluationError):
            parse_and_normalize(json.dumps(value), BenchmarkConfig())


if __name__ == "__main__":
    unittest.main()
