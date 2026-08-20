from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vlm_bench.dataset import DatasetError, load_ml_pairs, select_pairs


class DatasetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.pairs = load_ml_pairs(ROOT / "data")

    def test_default_dataset_contains_243_corrupted_pairs(self) -> None:
        self.assertEqual(len(self.pairs), 243)
        self.assertTrue(all(pair.gold_is_corrupted for pair in self.pairs))
        self.assertTrue(all(pair.orig_pic.is_file() and pair.fail_pic.is_file() for pair in self.pairs))

    def test_select_by_id_and_image_path(self) -> None:
        pair = self.pairs[0]
        by_id = select_pairs(self.pairs, ids=[pair.pair_id])
        by_image = select_pairs(self.pairs, image_paths=[pair.fail_pic])
        self.assertEqual([item.pair_id for item in by_id], [pair.pair_id])
        self.assertEqual([item.pair_id for item in by_image], [pair.pair_id])

    def test_unknown_id_fails_before_network(self) -> None:
        with self.assertRaises(DatasetError):
            select_pairs(self.pairs, ids=["document_999/figure_999"])


if __name__ == "__main__":
    unittest.main()
