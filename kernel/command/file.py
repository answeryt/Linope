"""Write a file and publish it as a resource."""

from __future__ import annotations

import json
import secrets
import sys

from kernel.command.parser import resource_store_path
from kernel.command.protocol import CommandSpec
from kernel.process.hypermedia.file_link import representation_for_file
from kernel.process.hypermedia.uri import resource_uri
from kernel.process.profile import ProfileUnavailable
from kernel.process.hypermedia.http_server import running_server_base
from kernel.process.ledger import open_store
from kernel.resource.memory.file_page import page_for_written_file
from kernel.resource.memory.task_kind import TaskKind
from kernel.services import LaunchOptions, ServiceRequest, ServiceSpec, open_service


def parse_file(argv: list[str]) -> tuple[str, str, str, str]:
    rest, store_path = resource_store_path(list(argv))
    usage = "file 的写法是：file once|lasting 路径 -- 全文"
    if "--" not in rest:
        raise SystemExit(usage)
    separator = rest.index("--")
    head = rest[:separator]
    if len(head) != 2 or head[0] not in {"once", "lasting"} or not head[1]:
        raise SystemExit(usage)
    mode, path = head
    return mode, path, " ".join(rest[separator + 1 :]), store_path


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


def run(argv: list[str]) -> int:
    mode, path, content, store_path = parse_file(argv)
    base_url = running_server_base(store_path)
    if base_url is None:
        print(
            "资源 HTTP 服务没有运行，请先执行 "
            "linope resources serve --port 0",
            file=sys.stderr,
        )
        return 1
    try:
        service = open_service(
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


SPEC = CommandSpec(name="file", run=run)
