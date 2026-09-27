from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

from .governance import GovernanceService, QueryFilters


class GovernanceRequestHandler(BaseHTTPRequestHandler):
    service: GovernanceService
    server_version = "InvestEval/0.1"

    def log_message(self, format: str, *args: object) -> None:
        return

    def _json_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        value = json.loads(raw.decode("utf-8"))
        if not isinstance(value, dict):
            raise ValueError("JSON body must be an object")
        return value

    def _send(self, status: HTTPStatus, payload: object) -> None:
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status.value)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _error(self, status: HTTPStatus, code: str, message: str) -> None:
        self._send(status, {"error": {"code": code, "message": message}})

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        segments = [unquote(item) for item in parsed.path.split("/") if item]
        try:
            if segments == ["api", "health"]:
                self._send(HTTPStatus.OK, {"status": "ok", "service": "investeval"})
                return
            if segments == ["api", "summary"]:
                self._send(HTTPStatus.OK, self.service.summary())
                return
            if segments == ["api", "cases"]:
                query = parse_qs(parsed.query)
                filters = QueryFilters(
                    intent=query.get("intent", [None])[0],
                    error_code=query.get("error_code", [None])[0],
                    review_status=query.get("review_status", [None])[0],
                    outcome=query.get("outcome", [None])[0],
                )
                items = self.service.list_cases(filters)
                self._send(HTTPStatus.OK, {"count": len(items), "items": items})
                return
            if len(segments) == 3 and segments[:2] == ["api", "cases"]:
                self._send(HTTPStatus.OK, self.service.get_case(segments[2]))
                return
            self._error(HTTPStatus.NOT_FOUND, "NOT_FOUND", "Route not found")
        except KeyError as exc:
            self._error(HTTPStatus.NOT_FOUND, "CASE_NOT_FOUND", str(exc.args[0]))
        except ValueError as exc:
            self._error(HTTPStatus.BAD_REQUEST, "INVALID_REQUEST", str(exc))

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        segments = [unquote(item) for item in parsed.path.split("/") if item]
        try:
            if segments == ["api", "evaluate"]:
                self._send(HTTPStatus.OK, self.service.reload())
                return
            if segments == ["api", "cases", "import"]:
                self._send(HTTPStatus.CREATED, self.service.import_cases(self._json_body()))
                return
            if len(segments) == 4 and segments[:2] == ["api", "cases"] and segments[3] == "review":
                body = self._json_body()
                review = self.service.review_case(
                    segments[2],
                    str(body.get("status", "")),
                    str(body.get("reviewer", "")),
                    str(body.get("note", "")),
                )
                self._send(HTTPStatus.OK, review)
                return
            self._error(HTTPStatus.NOT_FOUND, "NOT_FOUND", "Route not found")
        except KeyError as exc:
            self._error(HTTPStatus.NOT_FOUND, "CASE_NOT_FOUND", str(exc.args[0]))
        except (ValueError, json.JSONDecodeError) as exc:
            self._error(HTTPStatus.BAD_REQUEST, "INVALID_REQUEST", str(exc))


def serve(service: GovernanceService, host: str, port: int) -> None:
    handler = type("BoundGovernanceRequestHandler", (GovernanceRequestHandler,), {"service": service})
    server = ThreadingHTTPServer((host, port), handler)
    print(f"InvestEval API listening on http://{host}:{port}")
    server.serve_forever()

