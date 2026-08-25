"""Локальный HTML-просмотрщик и API ручной проверки разметки."""

from __future__ import annotations

import json
import mimetypes
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

from .config import TOOL_ROOT
from .state import ReviewState


def make_handler(state: ReviewState) -> type[BaseHTTPRequestHandler]:
    viewer_root = TOOL_ROOT / "viewer"

    class ViewerHandler(BaseHTTPRequestHandler):
        def log_message(self, _format: str, *_args: object) -> None:
            return

        def _send_json(self, value: object, status: int = HTTPStatus.OK) -> None:
            data = json.dumps(value, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _send_file(self, path: Path) -> None:
            if not path.is_file():
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            data = path.read_bytes()
            mime, _ = mimetypes.guess_type(path.name)
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", mime or "application/octet-stream")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _segments(self) -> list[str]:
            return [part for part in unquote(urlparse(self.path).path).split("/") if part]

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            path = unquote(parsed.path)
            segments = self._segments()
            if path == "/api/state":
                self._send_json(state.snapshot())
                return
            if len(segments) == 3 and segments[:2] == ["api", "items"]:
                item = state.detail(segments[2])
                if item is None:
                    self.send_error(HTTPStatus.NOT_FOUND)
                else:
                    self._send_json(item)
                return
            if len(segments) == 3 and segments[:2] == ["api", "image"]:
                image = state.image_for_item(segments[2])
                if image is None:
                    self.send_error(HTTPStatus.NOT_FOUND)
                else:
                    self._send_file(image)
                return
            if path in {"/", "/index.html"}:
                self._send_file(viewer_root / "index.html")
                return
            if path in {"/styles.css", "/app.js"}:
                self._send_file(viewer_root / path.lstrip("/"))
                return
            self.send_error(HTTPStatus.NOT_FOUND)

        def do_POST(self) -> None:  # noqa: N802
            segments = self._segments()
            if len(segments) != 4 or segments[:2] != ["api", "items"] or segments[3] != "review":
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            try:
                content_length = int(self.headers.get("Content-Length", "0"))
                if content_length > 100_000:
                    raise ValueError("Слишком большой запрос")
                payload = json.loads(self.rfile.read(content_length).decode("utf-8"))
                result = state.review(
                    segments[2],
                    str(payload.get("decision", "")),
                    str(payload.get("comment", "")),
                    str(payload.get("annotation", "")),
                )
                self._send_json(result)
            except (ValueError, KeyError, json.JSONDecodeError) as error:
                self._send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)

    return ViewerHandler


def create_server(state: ReviewState, port: int) -> ThreadingHTTPServer:
    return ThreadingHTTPServer(("127.0.0.1", port), make_handler(state))
