"""Local HTTP access to the resource pages kept by the ledger."""

from __future__ import annotations

import json
import os
import re
import socket
import tempfile
from dataclasses import dataclass
from enum import StrEnum
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

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 0
_LOOPBACK = {"127.0.0.1", "localhost", "::1"}
_DEFAULT_STORE = "file:.linope/resources.json"


class PageState(StrEnum):
    RESIDENT = "resident"
    PINNED = "pinned"
    SWAPPED = "swapped"


@dataclass(frozen=True)
class Page:
    """One file page recorded in the local resource ledger."""

    address: str
    size: int = 0
    state: PageState = PageState.RESIDENT

    def __post_init__(self) -> None:
        if not self.address:
            raise ValueError("representation address is required")
        if self.size < 0:
            raise ValueError("representation size cannot be negative")

    def with_state(self, state: PageState) -> Page:
        return Page(address=self.address, size=self.size, state=state)


def server_state_path(store_path: str | Path) -> Path:
    locator = _normalize_locator(store_path)
    if locator.startswith(("file:", "local:")):
        return _local_path(locator).resolve().parent / "http-server.json"
    return Path(".linope").resolve() / "http-server.json"


def running_server_base(store_path: str | Path) -> str | None:
    path = server_state_path(store_path)
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if _normalize_locator(str(state.get("resource_store", ""))) != _normalize_locator(
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
        store = _open_store(self.server.store_locator)
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
        store = _open_store(self.server.store_locator)
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
        store = _open_store(self.server.store_locator)
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
        raise ValueError("The resource service can only listen on the loopback address")
    locator = _normalize_locator(store_path)
    if locator.startswith("memory:"):
        raise ValueError("The memory store cannot start a standalone HTTP service")
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
    print(f"Resource service listening on {host}:{actual_port}", flush=True)
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


def _normalize_locator(value: str | Path | None) -> str:
    """A file locator. An empty value uses the project ledger."""
    raw = "" if value is None else str(value).strip()
    if not raw:
        raw = os.environ.get("LINOPE_RESOURCE_STORE", "").strip()
    if not raw:
        raw = str(_project_config().get("resource_store") or "").strip()
    if not raw:
        raw = _DEFAULT_STORE
    if re.match(r"^[A-Za-z][A-Za-z0-9+._-]*:", raw) is not None and not (
        len(raw) >= 2 and raw[1] == ":"
    ):
        return raw
    return f"file:{raw}"


def _local_path(locator: str | Path) -> Path:
    from kernel.process.process_creat.instances import repo_root

    raw = str(locator)
    if raw.startswith(("file:", "local:")):
        raw = raw.split(":", 1)[1]
    if raw.startswith("//"):
        raw = raw[2:]
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = repo_root() / path
    return path


def _project_config() -> dict[str, Any]:
    from kernel.process.process_creat.instances import repo_root

    path = repo_root() / ".linope" / "config.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


class _PageStore:
    """The page slice of one local resource ledger."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def close(self) -> None:
        return None

    def link_at(self, handle: str) -> tuple[Page, Link] | None:
        if not handle:
            return None
        for page, link in _read_pages(self.path):
            if link.handle == handle:
                return page, link
        return None

    def save_page(self, page: Page, link: Link) -> None:
        payload = _read_ledger(self.path)
        pages = _ensure_pages(payload)
        key = _page_key(pages, page, link)
        current = pages.get(key)
        raw_page: dict[str, Any] = {}
        raw_link: dict[str, Any] = {}
        if isinstance(current, dict):
            if isinstance(current.get("page"), dict):
                raw_page = dict(current["page"])
            if isinstance(current.get("link"), dict):
                raw_link = dict(current["link"])
        raw_page["address"] = page.address
        raw_page["size"] = page.size
        raw_page["state"] = page.state.value
        raw_link["relation"] = link.relation
        raw_link["resource_id"] = link.resource_id
        raw_link["handle"] = link.handle
        pages[key] = {"page": raw_page, "link": raw_link}
        _write_state(self.path, payload)


def _open_store(locator: str) -> _PageStore:
    normalized = _normalize_locator(locator)
    if not normalized.startswith(("file:", "local:")):
        raise ValueError("The resource service only reads the local ledger")
    return _PageStore(_local_path(normalized))


def _read_ledger(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Cannot read local storage {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"Cannot read local storage {path}: the ledger is not an object")
    return payload


def _ensure_pages(payload: dict[str, Any]) -> dict[str, Any]:
    sections = payload.get("sections")
    if not isinstance(sections, dict):
        sections = {}
        payload["sections"] = sections
    resource = sections.get("resource")
    if not isinstance(resource, dict):
        resource = {}
        sections["resource"] = resource
    pages = resource.get("pages")
    if not isinstance(pages, dict):
        pages = {}
        resource["pages"] = pages
    return pages


def _read_pages(path: Path) -> list[tuple[Page, Link]]:
    payload = _read_ledger(path)
    sections = payload.get("sections")
    resource = sections.get("resource") if isinstance(sections, dict) else None
    found = resource.get("pages") if isinstance(resource, dict) else None
    if not isinstance(found, dict):
        return []
    rows: list[tuple[Page, Link]] = []
    for item in found.values():
        parsed = _parse_page(item)
        if parsed is not None:
            rows.append(parsed)
    return rows


def _parse_page(item: object) -> tuple[Page, Link] | None:
    if not isinstance(item, dict):
        return None
    raw_page = item.get("page")
    raw_link = item.get("link")
    if not isinstance(raw_page, dict) or not isinstance(raw_link, dict):
        return None
    address = str(raw_page.get("address") or "")
    relation = str(raw_link.get("relation") or "")
    resource_id = str(raw_link.get("resource_id") or "")
    if not address or not relation or not resource_id:
        return None
    try:
        state = PageState(str(raw_page.get("state") or PageState.RESIDENT.value))
        size = int(raw_page.get("size") or 0)
        page = Page(address=address, size=size, state=state)
        link = Link(
            relation=relation,
            resource_id=resource_id,
            handle=str(raw_link.get("handle") or ""),
        )
    except (TypeError, ValueError):
        return None
    return page, link


def _page_key(pages: dict[str, Any], page: Page, link: Link) -> str:
    if link.handle:
        for key, item in pages.items():
            raw_link = item.get("link") if isinstance(item, dict) else None
            if isinstance(raw_link, dict) and str(raw_link.get("handle") or "") == link.handle:
                return str(key)
    for key, item in pages.items():
        raw_page = item.get("page") if isinstance(item, dict) else None
        address = raw_page.get("address") if isinstance(raw_page, dict) else ""
        if str(address or "") == page.address or str(key) == page.address:
            return str(key)
    return page.address
