# -*- coding: utf-8 -*-
"""HTTP route carrier. Knows no frontend; the static plugin owns dist files."""

from __future__ import annotations

import threading
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import unquote, urlparse


PLUGIN_NAME = "ui_server"
PLUGIN_VERSION = "1.0"

Handler = Callable[[dict[str, str]], dict[str, Any]]


class UiWebServer:
    """Named routes plus one fallback seat. Listen starts accepting requests."""

    def __init__(self, *, host: str = "127.0.0.1", port: int = 3080) -> None:
        self.host = host
        self.port = int(port)
        self.listened_port: int | None = None
        self._exact: dict[str, Handler] = {}
        self._prefixes: dict[str, Handler] = {}
        self._fallback: Handler | None = None
        self._index_taps: list[Callable[[str], str]] = []
        self._httpd: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    def register(self, kind: str, path: str, handler: Handler) -> None:
        table = self._exact if kind == "exact" else self._prefixes
        if kind not in ("exact", "prefix"):
            raise ValueError(f"unknown route kind: {kind!r}")
        if path in table:
            raise ValueError(f"webserver: duplicate {kind} route {path!r}")
        table[path] = handler

    def register_fallback(self, handler: Handler) -> None:
        if self._fallback is not None:
            raise ValueError("webserver: fallback already registered")
        self._fallback = handler

    def tap_index(self, transform: Callable[[str], str]) -> None:
        self._index_taps.append(transform)

    def apply_index_taps(self, html: str) -> str:
        out = html
        for transform in self._index_taps:
            out = transform(out)
        return out

    def match(self, pathname: str) -> Handler | None:
        exact = self._exact.get(pathname)
        if exact is not None:
            return exact
        best_path = ""
        best: Handler | None = None
        for prefix, handler in self._prefixes.items():
            if pathname != prefix and not pathname.startswith(prefix + "/"):
                continue
            if len(prefix) > len(best_path):
                best_path = prefix
                best = handler
        return best

    def listen(self) -> int:
        if self._httpd is not None:
            if self.listened_port is None:
                raise RuntimeError("webserver: listen already started without a port")
            return self.listened_port
        handler = _make_handler(self)
        httpd = ThreadingHTTPServer((self.host, self.port), handler)
        self._httpd = httpd
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        self._thread = thread
        listened = int(httpd.server_address[1])
        self.listened_port = listened
        return listened

    def wait(self) -> None:
        thread = self._thread
        if thread is None:
            raise RuntimeError("webserver: listen before wait")
        thread.join()

    def close(self) -> None:
        httpd = self._httpd
        if httpd is None:
            return
        httpd.shutdown()
        httpd.server_close()
        thread = self._thread
        if thread is not None:
            thread.join(timeout=2)
        self._httpd = None
        self._thread = None
        self.listened_port = None


def create_server(*, host: str = "127.0.0.1", port: int = 3080) -> UiWebServer:
    return UiWebServer(host=host, port=port)


def _make_handler(owner: UiWebServer) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, format: str, *args: Any) -> None:
            return

        def do_GET(self) -> None:
            self._dispatch()

        def do_HEAD(self) -> None:
            self._dispatch()

        def do_POST(self) -> None:
            self._dispatch()

        def do_PUT(self) -> None:
            self._dispatch()

        def do_DELETE(self) -> None:
            self._dispatch()

        def do_PATCH(self) -> None:
            self._dispatch()

        def do_OPTIONS(self) -> None:
            self._dispatch()

        def _dispatch(self) -> None:
            try:
                pathname = unquote(urlparse(self.path).path or "/")
                handler = owner.match(pathname)
                if handler is None:
                    handler = owner._fallback
                if handler is None:
                    self._write({"status": 404, "headers": {}, "body": b""})
                    return
                response = handler({"method": self.command, "path": pathname})
                self._write(response)
            except Exception:
                try:
                    self._write({"status": 400, "headers": {}, "body": b""})
                except Exception:
                    self.close_connection = True

        def _write(self, response: dict[str, Any]) -> None:
            status = int(response.get("status") or 200)
            headers = dict(response.get("headers") or {})
            body = response.get("body") or b""
            if isinstance(body, str):
                body = body.encode("utf-8")
            length = len(body)
            if self.command == "HEAD":
                body = b""
            self.send_response(status)
            for name, value in headers.items():
                self.send_header(str(name), str(value))
            self.send_header("Content-Length", str(length))
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

    return Handler
