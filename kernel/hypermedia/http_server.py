"""Local HTTP access to the resource pages kept by the ledger."""

from __future__ import annotations

import json
import os
import socket
import tempfile
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from kernel.hypermedia.link import Link
from kernel.hypermedia.representation_json import (
    content_payload,
    file_resource_payload,
)
from kernel.hypermedia.uri import (
    parse_action_uri,
    parse_content_uri,
    parse_resource_uri,
)
from kernel.process.ledger import open_store
from kernel.resource.memory.page import Page, PageState
from kernel.resource.store.locator import local_path, normalize_locator

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 0
_LOOPBACK = {"127.0.0.1", "localhost", "::1"}


def server_state_path(store_path: str | Path) -> Path:
    locator = normalize_locator(store_path)
    if locator.startswith(("file:", "local:")):
        return local_path(locator).resolve().parent / "http-server.json"
    return Path(".linope").resolve() / "http-server.json"


def running_server_base(store_path: str | Path) -> str | None:
    path = server_state_path(store_path)
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if normalize_locator(str(state.get("resource_store", ""))) != normalize_locator(
        store_path
    ):
        return None
    port = state.get("port")
    if not isinstance(port, int) or port <= 0:
        return None
    try:
        with socket.create_connection((DEFAULT_HOST, port), timeout=0.5):
            return f"http://{DEFAULT_HOST}:{port}"
    except OSError:
        return None


class _ResourceServer(ThreadingHTTPServer):
    allow_reuse_address = True

    def __init__(self, address: tuple[str, int], store_locator: str) -> None:
        self.store_locator = store_locator
        super().__init__(address, _ResourceHandler)


class _ResourceHandler(BaseHTTPRequestHandler):
    server: _ResourceServer

    def do_GET(self) -> None:
        base_url = self._base_url()
        parsed = urlsplit(self.path)
        if parsed.query or parsed.fragment:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "query not allowed"})
            return
        full_url = f"{base_url}{parsed.path}"
        try:
            if parsed.path.endswith("/content"):
                self._serve_content(parse_content_uri(full_url), base_url)
            else:
                self._serve_resource(parse_resource_uri(full_url), base_url)
        except ValueError as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})

    def do_POST(self) -> None:
        base_url = self._base_url()
        parsed = urlsplit(self.path)
        if parsed.query or parsed.fragment:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "query not allowed"})
            return
        try:
            handle, action = parse_action_uri(f"{base_url}{parsed.path}")
        except ValueError as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return
        self._serve_action(handle, action, base_url)

    def _serve_resource(self, handle: str, base_url: str) -> None:
        store = open_store(self.server.store_locator)
        try:
            found = store.link_at(handle)
            if found is None:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "resource not found"})
                return
            page, _link = found
            self._send_json(HTTPStatus.OK, _menu(page, handle, base_url))
        finally:
            store.close()

    def _serve_content(self, handle: str, base_url: str) -> None:
        store = open_store(self.server.store_locator)
        try:
            found = store.link_at(handle)
            if found is None:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "resource not found"})
                return
            page, _link = found
            menu = _menu(page, handle, base_url)
            if "content" not in menu["_links"]:
                self._send_json(HTTPStatus.CONFLICT, {"error": "relation not offered"})
                return
            try:
                text = _body_path(page).read_text(encoding="utf-8")
            except (OSError, UnicodeError) as exc:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": str(exc)})
                return
            if "application/json" in self.headers.get("Accept", ""):
                self._send_json(
                    HTTPStatus.OK,
                    content_payload(
                        path=page.address,
                        handle=handle,
                        state=page.state.value,
                        content=text,
                        base_url=base_url,
                    ),
                )
                return
            encoded = text.encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)
        finally:
            store.close()

    def _serve_action(self, handle: str, action: str, base_url: str) -> None:
        store = open_store(self.server.store_locator)
        try:
            found = store.link_at(handle)
            if found is None:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "resource not found"})
                return
            page, link = found
            menu = _menu(page, handle, base_url)
            if action not in menu["_links"]:
                self._send_json(
                    HTTPStatus.CONFLICT,
                    {"error": "relation not offered", "rel": action},
                )
                return
            updated = page.with_state(
                {"pin": PageState.PINNED, "swap": PageState.SWAPPED, "admit": PageState.RESIDENT}[
                    action
                ]
            )
            store.save_page(updated, link)
            self._send_json(HTTPStatus.OK, _menu(updated, handle, base_url))
        finally:
            store.close()

    def _base_url(self) -> str:
        host, port = self.server.server_address[:2]
        return f"http://{DEFAULT_HOST if host in _LOOPBACK else host}:{port}"

    def _send_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, format: str, *args: object) -> None:
        return None


def serve_resources(
    store_path: str | Path,
    *,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
) -> None:
    """Serve one local resource store on a loopback address."""
    if host not in _LOOPBACK:
        raise ValueError("资源服务只能监听本机回环地址")
    locator = normalize_locator(store_path)
    if locator.startswith("memory:"):
        raise ValueError("内存存储不能启动独立 HTTP 服务")
    state_path = server_state_path(locator)
    if running_server_base(locator) is not None:
        raise RuntimeError("resource server already running")
    server = _ResourceServer((host, port), locator)
    actual_port = int(server.server_address[1])
    _write_state(
        state_path,
        {
            "host": host,
            "port": actual_port,
            "pid": os.getpid(),
            "resource_store": locator,
        },
    )
    print(f"资源服务监听 {host}:{actual_port}", flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()
        _remove_state(state_path)


def _menu(page: Page, handle: str, base_url: str) -> dict[str, Any]:
    return file_resource_payload(
        path=page.address,
        handle=handle,
        state=page.state.value,
        base_url=base_url,
    )


def _body_path(page: Page) -> Path:
    sidecar = Path(f"{page.address}.summary")
    if page.state is PageState.PINNED and sidecar.is_file():
        return sidecar
    return Path(page.address)


def _write_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=path.name, dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(state, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def _remove_state(path: Path) -> None:
    try:
        path.unlink()
    except OSError:
        pass
