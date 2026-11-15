"""HTTP server exposing the agent and the static frontend."""

from __future__ import annotations

import json
import mimetypes
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from backend.app.ai.agent import EconomicAgent
from backend.app.config.settings import ROOT, Settings


FRONTEND_ROOT = ROOT / "frontend"


class RequestHandler(BaseHTTPRequestHandler):
    agent = EconomicAgent()

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/api/health":
            self._json({"status": "ok", "service": "economic-analysis-agent"})
            return
        request_path = self.path.split("?", 1)[0]
        if request_path == "/":
            request_path = "/index.html"
        self._serve_static(request_path)

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/api/query":
            self._json({"error": "Not found"}, HTTPStatus.NOT_FOUND)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length > 20_000:
                raise ValueError("Query is too large")
            body = json.loads(self.rfile.read(length).decode("utf-8"))
            if not isinstance(body, dict):
                raise ValueError("Request body must be a JSON object")
            query = str(body.get("query", "")).strip()
            if not query:
                raise ValueError("Please enter a question")
            result = self.agent.answer(query)
            self._json(result.as_dict())
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as error:
            self._json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
        except Exception as error:  # keep the API response useful for local debugging
            self._json({"error": f"Unable to answer query: {error}"}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def log_message(self, format: str, *args: object) -> None:
        return

    def _serve_static(self, request_path: str) -> None:
        relative = request_path.lstrip("/") or "index.html"
        path = (FRONTEND_ROOT / relative).resolve()
        if FRONTEND_ROOT not in path.parents and path != FRONTEND_ROOT:
            self._json({"error": "Not found"}, HTTPStatus.NOT_FOUND)
            return
        if not path.is_file():
            self._json({"error": "Not found"}, HTTPStatus.NOT_FOUND)
            return
        content = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", mimetypes.guess_type(path.name)[0] or "application/octet-stream")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _json(self, payload: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
        content = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)


def run() -> None:
    settings = Settings()
    server = ThreadingHTTPServer((settings.host, settings.port), RequestHandler)
    print(f"Economic analysis app running at http://{settings.host}:{settings.port}")
    print("Set FRED_LIVE_DATA=false to use only the saved grounding snapshots.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
