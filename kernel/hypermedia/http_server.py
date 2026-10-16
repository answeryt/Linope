"""Loopback HTTP access to Linope resources."""

from __future__ import annotations

import json
import hashlib
import os
import secrets
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
from kernel.hypermedia.tool_effect import (
    ToolEffect,
    compression_leased,
    effect_for,
    leased_tool_names,
    summary_text,
)
from kernel.hypermedia.uri import (
    parse_action_uri,
    parse_content_uri,
    parse_resource_uri,
    parse_tool_uri,
)
from kernel.process.ledger import open_store
from kernel.resource.store.locator import local_path, normalize_locator
from kernel.resource.store.network import (
    LOCAL,
    access_token,
    plan_serve,
    trust_host,
    untrust_host,
)
from kernel.resource.memory.page import Page, PageState
from kernel.resource.account import require_room, workspace_room

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 0


def server_state_path(store_path: str | Path) -> Path:
    """Return the runtime state file beside the resource store."""
    locator = normalize_locator(store_path)
    if locator.startswith(("file:", "local:")):
        return local_path(locator).resolve().parent / "http-server.json"
    digest = hashlib.sha256(locator.encode("utf-8")).hexdigest()[:16]
    return Path(".linope").resolve() / f"http-server-{digest}.json"


def running_server_base(store_path: str | Path) -> str | None:
    """Return the base URL of a live server for this resource store."""
    state_path = server_state_path(store_path)
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if normalize_locator(str(state.get("resource_store", ""))) != normalize_locator(
        store_path
    ):
        return None
    bind_host = str(state.get("bind_host") or state.get("host") or "")
    port = state.get("port")
    public = str(state.get("public_base_url") or "").rstrip("/")
    if not isinstance(port, int) or port <= 0:
        return None
    probe = bind_host if bind_host not in {"", "0.0.0.0", "::"} else ""
    if not probe and public:
        probe = str(urlsplit(public).hostname or "")
    if not probe:
        return None
    if not public and probe not in {DEFAULT_HOST, "localhost", "::1"}:
        return None
    try:
        with socket.create_connection((probe, port), timeout=0.5):
            return public or f"http://{probe}:{port}"
    except OSError:
        return None


class _ResourceServer(ThreadingHTTPServer):
    allow_reuse_address = True

    def __init__(
        self,
        address: tuple[str, int],
        store_locator: str,
        public_base: str = "",
        allow: tuple[str, ...] = (),
    ) -> None:
        self.store_locator = store_locator
        self.public_base = public_base.rstrip("/")
        self.allow_clients = allow
        super().__init__(address, _ResourceHandler)


class _ResourceHandler(BaseHTTPRequestHandler):
    server: _ResourceServer

    def do_GET(self) -> None:
        if not self._admit():
            return
        base_url = self._base_url()
        parsed = urlsplit(self.path)
        if parsed.query or parsed.fragment:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "query not allowed"})
            return
        full_url = f"{base_url}{parsed.path}"
        try:
            if parsed.path.endswith("/content"):
                handle = parse_content_uri(full_url)
                self._serve_content(handle, base_url)
                return
            handle = parse_resource_uri(full_url)
            self._serve_resource(handle, base_url)
        except ValueError as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})

    def do_POST(self) -> None:
        if not self._admit():
            return
        body = self._read_body()
        base_url = self._base_url()
        parsed = urlsplit(self.path)
        if parsed.query or parsed.fragment:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "query not allowed"})
            return
        full_url = f"{base_url}{parsed.path}"
        try:
            handle, action = parse_action_uri(full_url)
            tool_name = ""
        except ValueError:
            try:
                handle, tool_name = parse_tool_uri(full_url)
                action = ""
            except ValueError as exc:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
                return
        if tool_name:
            self._serve_tool(handle, tool_name, base_url, body)
        else:
            self._serve_action(handle, action, base_url)

    def _base_url(self) -> str:
        public = getattr(self.server, "public_base", "")
        if public:
            return public
        host, port = self.server.server_address[:2]
        if host in {"0.0.0.0", "::"}:
            host = DEFAULT_HOST
        return f"http://{host}:{port}"

    def _admit(self) -> bool:
        allow = getattr(self.server, "allow_clients", ())
        if allow and self.client_address[0] not in allow:
            self._send_json(HTTPStatus.FORBIDDEN, {"error": "这个地址不在允许的私网名单里"})
            return False
        expected = access_token()
        if not expected:
            return True
        if self.headers.get("Authorization", "") == f"Bearer {expected}":
            return True
        self._send_json(HTTPStatus.UNAUTHORIZED, {"error": "需要访问令牌"})
        return False

    def _serve_resource(self, handle: str, base_url: str) -> None:
        store = open_store(self.server.store_locator)
        try:
            found = store.link_at(handle)
            if found is None:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "resource not found"})
                return
            page, _link = found
            self._send_json(HTTPStatus.OK, self._menu(page, handle, base_url, store))
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
            menu = self._menu(page, handle, base_url, store)
            if "content" not in menu["_links"]:
                self._refuse("content")
                return
            try:
                content = _body_path(page).read_text(encoding="utf-8")
            except (OSError, UnicodeError) as exc:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": str(exc)})
                return
            if "application/json" in self.headers.get("Accept", ""):
                payload = content_payload(
                    path=page.address,
                    handle=handle,
                    state=page.state.value,
                    content=content,
                    base_url=base_url,
                    compress="compress" in menu["_links"],
                    tool_names=_tool_names(menu),
                )
                self._send_json(HTTPStatus.OK, payload)
                return
            encoded = content.encode("utf-8")
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
            menu = self._menu(page, handle, base_url, store)
            if action not in menu["_links"]:
                self._refuse(action)
                return
            if action == "compress":
                self._compress(page, link, handle, base_url, store)
                return
            updated = page.with_state(_NEXT_STATE[action])
            store.save_page(updated, link)
            self._send_json(
                HTTPStatus.OK,
                self._menu(updated, handle, base_url, store),
            )
        finally:
            store.close()

    def _serve_tool(
        self,
        handle: str,
        tool_name: str,
        base_url: str,
        body: bytes,
    ) -> None:
        store = open_store(self.server.store_locator)
        try:
            found = store.link_at(handle)
            if found is None:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "resource not found"})
                return
            page, _link = found
            menu = self._menu(page, handle, base_url, store)
            if tool_name not in menu["_links"]:
                self._refuse(tool_name)
                return
            effect = effect_for(tool_name)
            if effect is ToolEffect.OCCUPY:
                kept = _keep_tool_result(store, self.server.store_locator, body)
                if kept is not None:
                    kept_page, kept_handle = kept
                    payload = self._menu(kept_page, kept_handle, base_url, store)
                    payload["tool"] = tool_name
                    payload["effect"] = effect.value
                    self._send_json(HTTPStatus.OK, payload)
                    return
            payload = dict(menu)
            payload["tool"] = tool_name
            payload["effect"] = effect.value
            self._send_json(HTTPStatus.OK, payload)
        finally:
            store.close()

    def _compress(
        self,
        page: Page,
        link: Link,
        handle: str,
        base_url: str,
        store: Any,
    ) -> None:
        try:
            text = Path(page.address).read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            self._send_json(HTTPStatus.NOT_FOUND, {"error": str(exc)})
            return
        summary = summary_text(text)
        summary_size = len(summary.encode("utf-8"))
        if page.state is PageState.PINNED:
            if summary_size < page.size:
                if not self._room_for(store, page.address, summary_size):
                    return
                sidecar = Path(f"{page.address}.summary")
                sidecar.write_text(summary, encoding="utf-8")
                page = Page(
                    address=page.address,
                    size=summary_size,
                    state=PageState.PINNED,
                )
                store.save_page(page, link)
            self._send_json(HTTPStatus.OK, self._menu(page, handle, base_url, store))
            return
        if summary_size < page.size:
            if not self._room_for(store, page.address, summary_size):
                return
            path = _summary_file(self.server.store_locator, handle, summary)
            swapped = page.with_state(PageState.SWAPPED)
            store.save_page(swapped, link)
            summary_handle = secrets.token_hex(16)
            summary_page = Page(
                address=str(path),
                size=summary_size,
                state=PageState.RESIDENT,
            )
            store.save_page(
                summary_page,
                Link(relation="self", resource_id=str(path), handle=summary_handle),
            )
            self._send_json(
                HTTPStatus.OK,
                self._menu(summary_page, summary_handle, base_url, store),
            )
            return
        swapped = page.with_state(PageState.SWAPPED)
        store.save_page(swapped, link)
        self._send_json(HTTPStatus.OK, self._menu(swapped, handle, base_url, store))

    def _menu(self, page: Page, handle: str, base_url: str, store: Any) -> dict[str, Any]:
        return file_resource_payload(
            path=page.address,
            handle=handle,
            state=page.state.value,
            base_url=base_url,
            compress=compression_leased(store) and page.embedded(),
            tool_names=leased_tool_names(store),
        )

    def _room_for(self, store: Any, address: str, incoming: int) -> bool:
        """False when this embedded body does not fit. The reply is already sent."""
        used, ceiling, counted = workspace_room(store, address)
        try:
            require_room(max(0, used - counted), incoming, ceiling)
        except PermissionError as exc:
            self._send_json(HTTPStatus.FORBIDDEN, {"error": str(exc)})
            return False
        return True

    def _refuse(self, relation: str) -> None:
        self._send_json(
            HTTPStatus.CONFLICT,
            {"error": "relation not offered", "rel": relation},
        )

    def _read_body(self) -> bytes:
        length = self.headers.get("Content-Length")
        if not length:
            return b""
        try:
            size = int(length)
        except ValueError:
            return b""
        if size <= 0:
            return b""
        return self.rfile.read(size)

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
    mode: str = LOCAL,
    public_base_url: str = "",
    allow: tuple[str, ...] = (),
) -> None:
    """Serve one resource store. ``local`` stays on loopback; ``private`` is explicit."""
    plan = plan_serve(
        str(store_path),
        mode=mode,
        host=host,
        port=port,
        public_base_url=public_base_url,
        allow=allow,
    )
    if plan.locator.startswith("memory:"):
        raise ValueError("内存存储不能启动独立 HTTP 服务")
    trusted = ""
    if plan.mode != LOCAL:
        trusted = str(urlsplit(plan.public_base).hostname or "")
        trust_host(trusted)
    state_path = server_state_path(plan.locator)
    try:
        _serve_planned(plan, state_path)
    finally:
        if trusted:
            untrust_host(trusted)


def _serve_planned(plan, state_path: Path) -> None:
    existing = running_server_base(plan.locator)
    if existing is not None:
        raise RuntimeError(f"resource server already running at {existing}")
    server = _ResourceServer(
        (plan.bind_host, plan.port),
        plan.locator,
        public_base=plan.public_base,
        allow=plan.allow,
    )
    _actual_host, actual_port = server.server_address[:2]
    public = plan.public_base or f"http://{DEFAULT_HOST}:{actual_port}"
    server.public_base = public
    state = {
        "host": DEFAULT_HOST if plan.mode == LOCAL else plan.bind_host,
        "bind_host": plan.bind_host,
        "port": actual_port,
        "pid": os.getpid(),
        "resource_store": plan.locator,
        "mode": plan.mode,
        "public_base_url": public,
    }
    _write_state(state_path, state)
    print(f"资源服务 {plan.mode} 监听 {plan.bind_host}:{actual_port}，链接 {public}", flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()
        _remove_owned_state(state_path, os.getpid())


def _write_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, raw = tempfile.mkstemp(prefix=path.name, dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(state, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        os.replace(raw, path)
    except BaseException:
        try:
            os.unlink(raw)
        except OSError:
            pass
        raise


_NEXT_STATE = {
    "pin": PageState.PINNED,
    "swap": PageState.SWAPPED,
    "admit": PageState.RESIDENT,
}


def _tool_names(menu: dict[str, Any]) -> tuple[str, ...]:
    names = []
    for relation, link in menu.get("_links", {}).items():
        if isinstance(link, dict) and link.get("method") == "POST" and relation not in {
            "pin",
            "swap",
            "admit",
            "compress",
        }:
            names.append(relation)
    return tuple(names)


def _body_path(page: Page) -> Path:
    sidecar = Path(f"{page.address}.summary")
    if page.state is PageState.PINNED and sidecar.is_file():
        return sidecar
    return Path(page.address)


def _summary_file(store_locator: str, handle: str, summary: str) -> Path:
    locator = normalize_locator(store_locator)
    if locator.startswith(("file:", "local:")):
        directory = local_path(locator).resolve().parent / "summaries"
    else:
        directory = Path(".linope").resolve() / "summaries"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{handle}.txt"
    path.write_text(summary, encoding="utf-8")
    return path


def _keep_tool_result(
    store: Any,
    store_locator: str,
    body: bytes,
) -> tuple[Page, str] | None:
    """Occupy a new page only when a followed tool result asks to be kept."""
    if not body:
        return None
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict) or payload.get("keep") is not True:
        return None
    text = payload.get("text")
    if not isinstance(text, str) or not text:
        return None
    handle = secrets.token_hex(16)
    path = _summary_file(store_locator, handle, text)
    page = Page(address=str(path), size=len(text.encode("utf-8")), state=PageState.RESIDENT)
    store.save_page(
        page,
        Link(relation="self", resource_id=str(path), handle=handle),
    )
    return page, handle


def _remove_owned_state(path: Path, pid: int) -> None:
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
        if state.get("pid") == pid:
            path.unlink()
    except (OSError, json.JSONDecodeError):
        return
