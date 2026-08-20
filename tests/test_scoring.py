from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vlm_bench.config import BenchmarkConfig
from vlm_bench.scoring import faithfulness, overall, outcome


class ScoringTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = BenchmarkConfig()

    def test_faithfulness_boundaries(self) -> None:
        self.assertEqual(faithfulness(4, 0, 1, self.config), 5)  # 0.80 включительно
        self.assertEqual(faithfulness(3, 0, 2, self.config), 3)  # 0.60 включительно
        self.assertEqual(faithfulness(2, 0, 3, self.config), 1)
        self.assertEqual(faithfulness(5, 1, 0, self.config), 3)
        self.assertEqual(faithfulness(5, 1, 1, self.config), 1)
        self.assertEqual(faithfulness(5, 2, 0, self.config), 1)

    def test_overall_and_pairwise_outcome(self) -> None:
        score = overall({"faithfulness": 5, "clarity": 3, "compactness": 1, "style": 5}, self.config)
        self.assertEqual(score, 3.9)
        self.assertEqual(outcome(5, 3), "win")
        self.assertEqual(outcome(3, 3), "tie")
        self.assertEqual(outcome(1, 3), "lose")


if __name__ == "__main__":
    unittest.main()
