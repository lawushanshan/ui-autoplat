from __future__ import annotations

import json
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Any, Callable
from urllib.parse import parse_qs, urlparse

from pydantic import ValidationError

from ui_autoplat.config.settings import Settings


class APIError(Exception):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


class APIRequestHandler(BaseHTTPRequestHandler):
    _routes: dict[tuple[str, str], tuple[Callable, str]] = {}
    _auth_token: str | None = None
    _public_paths = {"/", "/api/health"}

    @classmethod
    def register(cls, path: str, handler: Callable, method: str = "GET") -> None:
        cls._routes[(method, path)] = (handler, method)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        params = parse_qs(parsed.query)

        if not self._is_authorized(path):
            self._send_api_error(APIError(401, "unauthorized", "Missing or invalid bearer token"))
            return

        route = self._match_route("GET", path)
        if route:
            handler, route_params = route
            try:
                flat_params: dict[str, Any] = {k: v[0] if len(v) == 1 else v for k, v in params.items()}
                flat_params.update(route_params)
                response = handler(**flat_params)
                self._send_json(200, response)
            except TypeError as e:
                self._send_api_error(APIError(400, "invalid_parameters", str(e)))
            except APIError as e:
                self._send_api_error(e)
            except Exception as e:
                self._send_api_error(APIError(500, "internal_error", str(e)))
        else:
            self._send_api_error(
                APIError(404, "not_found", f"Route not found: {path}"),
                extra={"available": [p for m, p in self._routes]},
            )

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"

        if not self._is_authorized(path):
            self._send_api_error(APIError(401, "unauthorized", "Missing or invalid bearer token"))
            return

        content_length = int(self.headers.get("Content-Length", 0))
        body = {}
        if content_length > 0:
            raw = self.rfile.read(content_length)
            try:
                body = json.loads(raw.decode("utf-8"))
            except json.JSONDecodeError:
                self._send_api_error(APIError(400, "invalid_json", "Invalid JSON body"))
                return

        route = self._match_route("POST", path)
        if route:
            handler, route_params = route
            try:
                body.update(route_params)
                body = self._validate_body(path, body)
                response = handler(**body)
                self._send_json(200, response)
            except TypeError as e:
                self._send_api_error(APIError(400, "invalid_parameters", str(e)))
            except ValidationError as e:
                self._send_api_error(
                    APIError(400, "validation_error", "Request body validation failed"),
                    extra={"details": _format_validation_errors(e)},
                )
            except APIError as e:
                self._send_api_error(e)
            except Exception as e:
                self._send_api_error(APIError(500, "internal_error", str(e)))
        else:
            self._send_api_error(APIError(404, "not_found", f"Route not found: {path}"))

    def _send_json(self, code: int, data: Any) -> None:
        response_body = json.dumps(data, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(response_body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(response_body)

    def _send_api_error(self, error: APIError, extra: dict[str, Any] | None = None) -> None:
        body: dict[str, Any] = {
            "error": {
                "code": error.code,
                "message": error.message,
            }
        }
        if extra:
            body.update(extra)
        self._send_json(error.status_code, body)

    def _is_authorized(self, path: str) -> bool:
        if self._auth_token is None:
            return True
        if path in self._public_paths:
            return True
        expected = f"Bearer {self._auth_token}"
        return self.headers.get("Authorization") == expected

    def _validate_body(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        if path == "/api/runs":
            from ui_autoplat.actions.schemas import TriggerRunRequest

            return TriggerRunRequest.model_validate(body).model_dump()
        return body

    @classmethod
    def _match_route(cls, method: str, path: str) -> tuple[Callable, dict[str, str]] | None:
        exact_key = (method, path)
        if exact_key in cls._routes:
            handler, _ = cls._routes[exact_key]
            return handler, {}

        path_parts = path.strip("/").split("/") if path != "/" else []
        for (route_method, route_path), (handler, _) in cls._routes.items():
            if route_method != method:
                continue
            route_parts = route_path.strip("/").split("/") if route_path != "/" else []
            if len(route_parts) != len(path_parts):
                continue

            params: dict[str, str] = {}
            matched = True
            for route_part, path_part in zip(route_parts, path_parts):
                if route_part.startswith("{") and route_part.endswith("}"):
                    params[route_part[1:-1]] = path_part
                elif route_part != path_part:
                    matched = False
                    break
            if matched:
                return handler, params
        return None

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def log_message(self, format: str, *args: Any) -> None:
        pass


def _format_validation_errors(exc: ValidationError) -> list[dict[str, str]]:
    details = []
    for error in exc.errors():
        details.append({
            "field": ".".join(str(part) for part in error["loc"]),
            "message": error["msg"],
        })
    return details


def start_server(host: str = "127.0.0.1", port: int = 8080) -> None:
    from ui_autoplat.actions import endpoints as ep
    from ui_autoplat.config.loader import load_settings

    settings = load_settings()
    APIRequestHandler._auth_token = settings.action_server.auth_token

    APIRequestHandler.register("/api/health", ep.get_health)
    APIRequestHandler.register("/api/runs/status", ep.get_run_status)
    APIRequestHandler.register("/api/runs/cancel", ep.cancel_run, method="POST")
    APIRequestHandler.register("/api/runs/latest", ep.get_latest_run)
    APIRequestHandler.register("/api/runs/{run_id}", ep.get_run_results)
    APIRequestHandler.register("/api/runs", ep.trigger_test_run, method="POST")
    APIRequestHandler.register("/api/suites", ep.list_test_suites)
    APIRequestHandler.register("/api/history", ep.get_history)
    APIRequestHandler.register("/api/stats", ep.get_stats)
    APIRequestHandler.register("/api/config", ep.get_config)

    APIRequestHandler.register("/", lambda: {
        "name": "ui-autoplat API",
        "version": "0.1.0",
        "endpoints": [
            {"method": "GET", "path": "/api/runs/latest", "description": "Get latest test run results"},
            {"method": "GET", "path": "/api/health", "description": "Health check"},
            {"method": "GET", "path": "/api/runs/status", "description": "Get current run status"},
            {"method": "POST", "path": "/api/runs/cancel", "description": "Request cancellation for the current run"},
            {"method": "GET", "path": "/api/runs/{run_id}", "description": "Get results by run ID"},
            {"method": "POST", "path": "/api/runs", "description": "Trigger a new test run", "body": {"suite_path": "str", "tags": "str?", "task_name": "str?", "async_run": "bool?"}},
            {"method": "GET", "path": "/api/suites", "description": "List discovered test suites"},
            {"method": "GET", "path": "/api/history", "description": "Get test history trends"},
            {"method": "GET", "path": "/api/stats", "description": "Get platform statistics"},
            {"method": "GET", "path": "/api/config", "description": "Get current configuration"},
        ],
    })

    server = HTTPServer((host, port), APIRequestHandler)
    print(f"\n  ui-autoplat API server running at http://{host}:{port}")
    print(f"  API docs: http://{host}:{port}/")
    if APIRequestHandler._auth_token:
        print("  API auth: bearer token required for non-public endpoints")
    print(f"  Press Ctrl+C to stop\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Server stopped.")
        server.server_close()
