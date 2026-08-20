"""Небольшой сервер только для чтения артефактов и картинок набора."""

from __future__ import annotations

import json
import mimetypes
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from .config import DEFAULT_DATA_ROOT, DEFAULT_RUNS_ROOT, PROJECT_ROOT


def _inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _json(path: Path) -> dict | list:
    return json.loads(path.read_text(encoding="utf-8"))


class ViewerHandler(BaseHTTPRequestHandler):
    runs_root: Path = DEFAULT_RUNS_ROOT
    project_root: Path = PROJECT_ROOT
    viewer_root: Path = PROJECT_ROOT / "viewer"

    def log_message(self, _format: str, *_args: object) -> None:
        return

    def _send_json(self, value: object, status: int = HTTPStatus.OK) -> None:
        body = json.dumps(value, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path: Path) -> None:
        if not path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        media_type, _ = mimetypes.guess_type(path.name)
        data = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", media_type or "application/octet-stream")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _list_runs(self) -> list[dict]:
        if not self.runs_root.is_dir():
            return []
        records = []
        for run_path in sorted(self.runs_root.glob("*/run.json"), reverse=True):
            try:
                run = _json(run_path)
                records.append({"run_id": run.get("run_id"), "display_name": run.get("display_name") or run.get("run_id"), "status": run.get("status"), "created_at": run.get("created_at"), "model": run.get("config", {}).get("model"), "summary": run.get("summary", {})})
            except (OSError, json.JSONDecodeError):
                continue
        return records

    def _run_directory(self, run_id: str) -> Path | None:
        candidate = (self.runs_root / run_id).resolve()
        if not _inside(candidate, self.runs_root) or not (candidate / "run.json").is_file():
            return None
        return candidate

    def _run_detail(self, run_dir: Path) -> dict:
        index_path = run_dir / "samples.jsonl"
        samples = []
        if index_path.is_file():
            for line in index_path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    samples.append(json.loads(line))
        return {"run": _json(run_dir / "run.json"), "samples": samples}

    def _sample_detail(self, run_dir: Path, pair_directory: str) -> dict | None:
        path = (run_dir / "samples" / pair_directory).resolve()
        if not _inside(path, run_dir) or not (path / "pair.json").is_file():
            return None
        result: dict[str, object] = {"pair": _json(path / "pair.json")}
        for side in ("orig", "fail"):
            side_dir = path / side
            result[side] = {
                "request": _json(side_dir / "request.json") if (side_dir / "request.json").is_file() else None,
                "result": _json(side_dir / "result.json") if (side_dir / "result.json").is_file() else None,
                "raw_response": _json(side_dir / "response.raw.json") if (side_dir / "response.raw.json").is_file() else None,
            }
        return result

    def do_GET(self) -> None:  # noqa: N802 - метод HTTP-сервера
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        if path == "/api/runs":
            self._send_json(self._list_runs())
            return
        if path.startswith("/api/runs/"):
            segments = [part for part in path.split("/") if part]
            if len(segments) < 3:
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            run_dir = self._run_directory(segments[2])
            if run_dir is None:
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            if len(segments) == 3:
                self._send_json(self._run_detail(run_dir))
                return
            if len(segments) == 5 and segments[3] == "samples":
                detail = self._sample_detail(run_dir, segments[4])
                if detail is None:
                    self.send_error(HTTPStatus.NOT_FOUND)
                else:
                    self._send_json(detail)
                return
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        if path == "/asset":
            values = parse_qs(parsed.query)
            raw_path = values.get("path", [""])[0]
            candidate = (self.project_root / raw_path).resolve()
            if not _inside(candidate, DEFAULT_DATA_ROOT) and not _inside(candidate, self.runs_root):
                self.send_error(HTTPStatus.FORBIDDEN)
                return
            self._send_file(candidate)
            return
        if path in {"/", "/index.html"}:
            self._send_file(self.viewer_root / "index.html")
            return
        if path in {"/styles.css", "/app.js"}:
            self._send_file(self.viewer_root / path.lstrip("/"))
            return
        self.send_error(HTTPStatus.NOT_FOUND)


def serve(*, port: int = 8080, runs_root: Path = DEFAULT_RUNS_ROOT) -> None:
    ViewerHandler.runs_root = runs_root.resolve()
    address = ("127.0.0.1", port)
    server = ThreadingHTTPServer(address, ViewerHandler)
    print(f"Просмотрщик открыт: http://127.0.0.1:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nПросмотрщик остановлен.")
    finally:
        server.server_close()
