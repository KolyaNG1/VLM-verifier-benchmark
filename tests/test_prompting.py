from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vlm_bench.dataset import load_ml_pairs
from vlm_bench.prompting import build_messages, load_template, safe_messages


class PromptingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.pair = load_ml_pairs(ROOT / "data")[0]

    def test_repeatable_text_markers_and_image_marker(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "template.md"
            path.write_text("A <caption> B <text> C <caption> D <image> E <text>", encoding="utf-8")
            template = load_template(path)
            messages = build_messages(template, self.pair, self.pair.orig_pic)
            user = messages[1]["content"]
            self.assertEqual(sum(part["type"] == "image_url" for part in user), 1)
            self.assertEqual(sum(part.get("text") == self.pair.caption for part in user), 2)
            self.assertEqual(sum(part.get("text") == self.pair.text_block for part in user), 2)

    def test_safe_request_never_contains_base64(self) -> None:
        template = load_template(ROOT / "prompts" / "vlm_judge" / "v001_baseline.md")
        value = safe_messages(template, self.pair, self.pair.fail_pic, ROOT)
        serialized = str(value)
        self.assertNotIn("base64,", serialized)
        self.assertIn("sha256", serialized)


if __name__ == "__main__":
    unittest.main()
