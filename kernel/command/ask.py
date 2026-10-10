"""Follow a resource link and ask a capability model."""

from __future__ import annotations

import sys
from collections.abc import Callable
from typing import Any
from urllib.request import urlopen

from kernel.command.parser import resource_store_path, take_env_flags
from kernel.command.protocol import CommandSpec
from kernel.process.hypermedia.file_link import messages_for_followed_file
from kernel.process.hypermedia.observation import fetch_representation, offered_href
from kernel.process.hypermedia.uri import parse_resource_uri, resource_base_url
from kernel.process.profile import ProfileUnavailable
from kernel.process.hypermedia.http_server import running_server_base
from kernel.process.ledger import open_store
from kernel.services import LaunchOptions, ServiceHost, ServiceRequest, ServiceSpec, open_service


def parse_ask(
    argv: list[str],
) -> tuple[str, str, str, str, str, tuple[str, ...]]:
    argv, env_file, env_keys = take_env_flags(list(argv))
    rest, store_path = resource_store_path(argv)
    usage = "ask 的写法是：ask 模型名 HTTP链接 -- 要说的话"
    if "--" not in rest:
        raise SystemExit(usage)
    separator = rest.index("--")
    head = rest[:separator]
    if len(head) != 2 or not head[0] or not head[1]:
        raise SystemExit(usage)
    capability, resource_link = head
    return (
        capability,
        resource_link,
        " ".join(rest[separator + 1 :]),
        store_path,
        env_file,
        env_keys,
    )


def run(
    argv: list[str],
    *,
    host: ServiceHost | None = None,
    open_service_fn: Callable[..., Any] | None = None,
    open_store_fn: Callable[..., Any] | None = None,
) -> int:
    if open_service_fn is None:
        open_service_fn = open_service
    if open_store_fn is None:
        open_store_fn = open_store
    capability, resource_link, words, store_path, env_file, env_keys = parse_ask(argv)
    store = open_store_fn(store_path)
    service: Any = None
    try:
        try:
            handle = parse_resource_uri(resource_link)
            base_url = resource_base_url(resource_link)
        except ValueError as exc:
            print(f"HTTP资源链接无效: {exc}", file=sys.stderr)
            return 1
        active_base_url = running_server_base(store_path)
        if active_base_url != base_url:
            print("HTTP资源链接不是当前 Linope 资源服务的地址", file=sys.stderr)
            return 1
        found = store.link_at(handle)
        if found is None:
            print("没有这条链接", file=sys.stderr)
            return 1
        try:
            menu = fetch_representation(resource_link)
        except (OSError, UnicodeError, ValueError) as exc:
            print(exc, file=sys.stderr)
            return 1
        content_href = offered_href(menu, "content")
        if content_href is None:
            print("当前菜单没有 content", file=sys.stderr)
            return 1
        try:
            with urlopen(content_href, timeout=10) as response:
                file_text = response.read().decode("utf-8")
        except (OSError, UnicodeError) as exc:
            print(exc, file=sys.stderr)
            return 1
        try:
            service = open_service_fn(
                ServiceSpec(kind="capability", members=(capability,)),
                LaunchOptions(
                    store_locator=store_path,
                    env_file=env_file,
                    env_file_keys=env_keys,
                ),
                host,
            )
        except (ProfileUnavailable, KeyError) as exc:
            print(exc, file=sys.stderr)
            return 1
        ticket = service.submit(
            ServiceRequest(
                kind="prompt",
                body=messages_for_followed_file(file_text, words),
            )
        )
        print(service.wait(ticket, timeout=180))
        return 0
    finally:
        if service is not None:
            service.close()
        store.close()


SPEC = CommandSpec(name="ask", run=run)
