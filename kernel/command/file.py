"""Write a file and publish it as a resource."""

from __future__ import annotations

import json
import secrets
import sys

from kernel.command.convention import UsageError, guard, parse
from kernel.hypermedia.file_link import representation_for_file
from kernel.hypermedia.uri import resource_uri
from kernel.process.profile import ProfileUnavailable
from kernel.hypermedia.http_server import running_server_base
from kernel.process.ledger import open_store
from kernel.resource.memory.file_page import page_for_written_file
from kernel.resource.memory.task_kind import TaskKind
from kernel.resource.account import require_room, workspace_room
from kernel.services import LaunchOptions, ServiceRequest, ServiceSpec, launch_session

USAGE = "用法: linope resource file once|lasting <路径> -- <全文>"


@guard(USAGE)
def run(argv: list[str]) -> int:
    invocation = parse(argv, flags={}, usage=USAGE)
    if invocation.body is None:
        if len(invocation.position) < 3:
            raise UsageError(USAGE)
        mode, path, *rest = invocation.position
        content = " ".join(rest)
    else:
        if len(invocation.position) != 2:
            raise UsageError(USAGE)
        mode, path = invocation.position
        content = invocation.body
    if mode not in {"once", "lasting"}:
        raise UsageError(USAGE)
    return _write(mode, path, content, invocation.store)


def _write(mode: str, path: str, content: str, store_path: str) -> int:
    base_url = running_server_base(store_path)
    if base_url is None:
        print("资源 HTTP 服务没有运行，请先执行 linope resource serve --port 0", file=sys.stderr)
        return 1
    try:
        service = launch_session(
            ServiceSpec(kind="capability", members=("tools.write",)),
            LaunchOptions(store_locator=store_path),
        )
    except (ProfileUnavailable, KeyError) as exc:
        print(exc, file=sys.stderr)
        return 1
    store = open_store(store_path)
    try:
        ticket = service.submit(
            ServiceRequest(kind="tool", body={"file_path": path, "content": content})
        )
        reply = service.wait(ticket, timeout=180)
        written = written_file(reply)
        if written is None:
            print(reply, file=sys.stderr)
            return 1
        page = page_for_written_file(
            str(written["path"]),
            int(written["bytes"]),
            mode == "lasting",
        )
        if page.embedded():
            used, ceiling, counted = workspace_room(store, page.address)
            try:
                require_room(max(0, used - counted), page.size, ceiling)
            except PermissionError as exc:
                print(exc, file=sys.stderr)
                return 1
        document = representation_for_file(page.address, secrets.token_hex(16))
        link = document.links[0]
        store.save_page(page, link)
        print(
            {
                "path": page.address,
                "bytes": page.size,
                "task": TaskKind.OCCUPY.value,
                "state": page.state.value,
                "href": resource_uri(link, base_url),
            }
        )
        return 0
    finally:
        service.close()
        store.close()


def written_file(reply: dict) -> dict[str, str | int] | None:
    if reply.get("event") != "result":
        return None
    raw = reply.get("result")
    if isinstance(raw, str):
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return None
    elif isinstance(raw, dict):
        payload = raw
    else:
        return None
    if payload.get("success") is not True:
        return None
    path = payload.get("path")
    size = payload.get("bytes")
    if not isinstance(path, str) or not path:
        return None
    if isinstance(size, bool) or not isinstance(size, int) or size < 0:
        return None
    return {"path": path, "bytes": size}
