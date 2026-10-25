"""Loopback-only JSON API and static desktop interface."""

from __future__ import annotations

import json
import logging
import os
import re
import threading
from datetime import date
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from .db import HabitStore, ValidationError
from .reminders import ReminderScheduler


log = logging.getLogger(__name__)
STATIC = Path(__file__).parent / "static"
TASK_RE = re.compile(r"^/api/tasks/(\d+)$")
MONTH_RE = re.compile(r"^/api/tasks/(\d+)/month$")
DAY_RE = re.compile(r"^/api/tasks/(\d+)/days/(\d{4}-\d{2}-\d{2})$")


class HabitHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address: tuple[str, int], store: HabitStore, scheduler: ReminderScheduler | None = None):
        super().__init__(address, HabitHandler)
        self.store = store
        self.scheduler = scheduler


class HabitHandler(BaseHTTPRequestHandler):
    server: HabitHTTPServer

    def log_message(self, format: str, *args: object) -> None:
        log.info("%s %s", self.address_string(), format % args)

    def _json(self, status: int, data: object) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _body(self) -> dict:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise ValidationError("Неверный размер запроса") from exc
        if length <= 0 or length > 16_384:
            raise ValidationError("Пустой или слишком большой запрос")
        try:
            body = json.loads(self.rfile.read(length))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValidationError("Неверный JSON") from exc
        if not isinstance(body, dict):
            raise ValidationError("Ожидался объект JSON")
        return body

    def _run(self, method: str) -> None:
        try:
            self._route(method)
        except ValidationError as exc:
            self._json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
        except KeyError as exc:
            self._json(HTTPStatus.NOT_FOUND, {"error": str(exc.args[0])})
        except (OverflowError, ValueError) as exc:
            self._json(HTTPStatus.BAD_REQUEST, {"error": "Неверная дата или параметр"})
        except Exception:
            log.exception("Ошибка обработки запроса")
            self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "Внутренняя ошибка"})

    def _route(self, method: str) -> None:
        parsed = urlsplit(self.path)
        path = parsed.path
        store = self.server.store
        host = self.headers.get("Host", "")
        if host not in (f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"):
            return self._json(403, {"error": "Недопустимый адрес запроса"})
        if method in ("POST", "PATCH", "PUT"):
            origin = self.headers.get("Origin")
            if origin and origin not in (f"http://127.0.0.1:{self.server.server_port}", f"http://localhost:{self.server.server_port}"):
                return self._json(403, {"error": "Недопустимый источник запроса"})
            if self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower() != "application/json":
                return self._json(415, {"error": "Ожидается application/json"})
        if method == "GET" and path == "/api/health":
            return self._json(200, {"ok": True, "app": "habit-garden", "pid": os.getpid()})
        if path == "/api/tasks":
            if method == "GET":
                return self._json(200, {"tasks": store.list(), "today": date.today().isoformat()})
            if method == "POST":
                result = store.create(self._body())
                self._wake()
                return self._json(201, result)
        match = TASK_RE.fullmatch(path)
        if match:
            task_id = int(match.group(1))
            if method == "GET":
                return self._json(200, store.get(task_id))
            if method == "PATCH":
                result = store.update(task_id, self._body())
                self._wake()
                return self._json(200, result)
        match = MONTH_RE.fullmatch(path)
        if match and method == "GET":
            params = parse_qs(parsed.query)
            try:
                year, month = int(params["year"][0]), int(params["month"][0])
            except (KeyError, IndexError, ValueError) as exc:
                raise ValidationError("Укажите год и месяц") from exc
            return self._json(200, {"days": store.month(int(match.group(1)), year, month)})
        match = DAY_RE.fullmatch(path)
        if match and method == "PUT":
            try:
                day = date.fromisoformat(match.group(2))
            except ValueError as exc:
                raise ValidationError("Неверная дата") from exc
            result = store.set_completion(int(match.group(1)), day, self._body().get("completed"))
            self._wake()
            return self._json(200, result)
        if method == "GET" and path in ("/", "/index.html", "/app.css", "/app.js", "/icon.svg", "/emoji-catalog.json"):
            name = "index.html" if path == "/" else path.lstrip("/")
            source = STATIC / name
            content = source.read_bytes()
            mime = {".html": "text/html", ".css": "text/css", ".js": "text/javascript", ".svg": "image/svg+xml", ".json": "application/json"}[source.suffix]
            self.send_response(200)
            self.send_header("Content-Type", f"{mime}; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; connect-src 'self'")
            self.end_headers()
            self.wfile.write(content)
            return
        self._json(404, {"error": "Страница не найдена"})

    def _wake(self) -> None:
        if self.server.scheduler:
            self.server.scheduler.wake()

    def do_GET(self) -> None:
        self._run("GET")

    def do_POST(self) -> None:
        self._run("POST")

    def do_PATCH(self) -> None:
        self._run("PATCH")

    def do_PUT(self) -> None:
        self._run("PUT")


def serve(store: HabitStore, port: int, ready: threading.Event | None = None) -> None:
    scheduler = ReminderScheduler(store)
    with HabitHTTPServer(("127.0.0.1", port), store, scheduler) as server:
        scheduler.start()
        if ready:
            ready.set()
        try:
            server.serve_forever(poll_interval=5)
        finally:
            scheduler.stop()
