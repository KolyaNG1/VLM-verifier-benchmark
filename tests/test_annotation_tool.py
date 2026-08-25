from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "nikolay_ai_360_annotation"))

from annotation_tool.config import PROJECT_ROOT
from annotation_tool.cli import _load
from annotation_tool.files import annotation_path, item_id
from annotation_tool.openrouter import load_local_env
from annotation_tool.prompting import FewShotExample, PromptTemplate, build_messages, load_prompt, text_parts
from annotation_tool.state import ReviewState
from annotation_tool.viewer_server import make_handler


class AnnotationToolTests(unittest.TestCase):
    def test_env_loader_does_not_override_a_system_value(self) -> None:
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT) as directory:
            source = Path(directory) / ".env"
            source.write_text("TEST_ANNOTATION_KEY=from_file\n", encoding="utf-8")
            old_value = os.environ.get("TEST_ANNOTATION_KEY")
            try:
                os.environ.pop("TEST_ANNOTATION_KEY", None)
                load_local_env(source)
                self.assertEqual(os.environ["TEST_ANNOTATION_KEY"], "from_file")
                os.environ["TEST_ANNOTATION_KEY"] = "from_system"
                load_local_env(source)
                self.assertEqual(os.environ["TEST_ANNOTATION_KEY"], "from_system")
            finally:
                if old_value is None:
                    os.environ.pop("TEST_ANNOTATION_KEY", None)
                else:
                    os.environ["TEST_ANNOTATION_KEY"] = old_value

    def test_run_limit_excludes_few_shot_images(self) -> None:
        class Arguments:
            command = "run"
            prompt_file = "nikolay_ai_360_annotation/prompts/annotation_fewshot.md"
            dataset_root = "nikolay_ai_360_student"
            offset = 0
            limit = 5

        template, images = _load(Arguments())
        example_paths = {example.image_path.resolve() for example in template.examples}
        self.assertEqual(len(template.examples), 1)
        self.assertEqual(len(images), 5)
        self.assertTrue(all(image.resolve() not in example_paths for image in images))

    def test_prompt_attaches_examples_without_textual_paths(self) -> None:
        parsed = load_prompt("nikolay_ai_360_annotation/prompts/annotation_fewshot.md")
        self.assertEqual(len(parsed.examples), 1)
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT) as directory:
            root = Path(directory)
            examples = []
            for number in range(5):
                image = root / f"example_{number}.png"
                label = root / f"example_{number}.txt"
                image.write_bytes(b"png")
                label.write_text(f"Manual description {number}.", encoding="utf-8")
                examples.append(FewShotExample(image, label))
            template = PromptTemplate(root / "prompt.md", "Describe the final image.", tuple(examples))
            messages = build_messages(template, examples[0].image_path)
            joined = "\n".join(text_parts(messages))
            for example in examples:
                self.assertNotIn(example.image_path.as_posix(), joined)
                self.assertNotIn(example.annotation_path.as_posix(), joined)

    def test_approval_writes_a_sidecar_and_rejection_returns_to_queue(self) -> None:
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT) as directory:
            root = Path(directory)
            image = root / "document_1" / "figure_1.png"
            image.parent.mkdir()
            image.write_bytes(b"png")
            state = ReviewState(root / "state.json", root / "candidates")
            state.initialize([image], manual_example_paths=set())
            job = state.acquire_next(1, threading.Event())
            self.assertEqual(job["status"], "generating")
            state.save_candidate(job["id"], "A clear description.", {"test": True})
            first_candidate = state.detail(job["id"])["candidate_path"]
            self.assertEqual(first_candidate, f"{image.parent.relative_to(PROJECT_ROOT).as_posix()}/figure_1.vlm_attempt_001.md")
            state.review(job["id"], "reject", "Mention the arrow direction.")
            retry = state.acquire_next(1, threading.Event())
            self.assertEqual(retry["review_comment"], "Mention the arrow direction.")
            state.save_candidate(retry["id"], "Corrected description.", {"test": True})
            state.review(retry["id"], "approve", "")
            self.assertEqual(annotation_path(image).read_text(encoding="utf-8"), "Corrected description.\n")

    def test_manual_annotation_can_replace_a_model_answer_and_is_recorded(self) -> None:
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT) as directory:
            root = Path(directory)
            image = root / "document_1" / "figure_1.png"
            image.parent.mkdir()
            image.write_bytes(b"png")
            state = ReviewState(root / "state.json", root / "candidates")
            state.initialize([image], manual_example_paths=set())
            job = state.acquire_next(1, threading.Event())
            state.review(item_id(image), "manual", "Checked by a person.", "Manual final description.")
            state.save_candidate(job["id"], "Late model answer.", {})
            state.mark_error(job["id"], "Late network error.")
            detail = state.detail(item_id(image))
            self.assertEqual(detail["status"], "approved")
            self.assertEqual(detail["final_annotation"], "Manual final description.")
            self.assertEqual(detail["last_review"]["decision"], "manual")
            self.assertEqual(annotation_path(image).read_text(encoding="utf-8"), "Manual final description.\n")

    def test_viewer_serves_state_and_accepts_review(self) -> None:
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT) as directory:
            root = Path(directory)
            image = root / "document_1" / "figure_1.png"
            image.parent.mkdir()
            image.write_bytes(b"png")
            state = ReviewState(root / "state.json", root / "candidates")
            state.initialize([image], manual_example_paths=set())
            job = state.acquire_next(1, threading.Event())
            state.save_candidate(job["id"], "Candidate.", {})
            server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(state))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base = f"http://127.0.0.1:{server.server_port}"
                with urlopen(f"{base}/api/state", timeout=5) as response:
                    listing = json.loads(response.read())
                self.assertEqual(listing["counts"]["awaiting_review"], 1)
                request = Request(
                    f"{base}/api/items/{job['id']}/review",
                    data=b'{"decision":"approve","comment":""}',
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urlopen(request, timeout=5) as response:
                    result = json.loads(response.read())
                self.assertEqual(result["status"], "approved")
                self.assertEqual(annotation_path(image).read_text(encoding="utf-8"), "Candidate.\n")
            finally:
                server.shutdown()
                server.server_close()


if __name__ == "__main__":
    unittest.main()
