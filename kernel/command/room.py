"""Show the room already stored for a running process."""

from __future__ import annotations

import sys

from kernel.command.parser import USAGE, resource_store_path
from kernel.command.protocol import CommandSpec
from kernel.process.ledger import open_store


def run(argv: list[str]) -> int:
    rest, store_path = resource_store_path(argv)
    if len(rest) > 1:
        raise SystemExit(USAGE)
    store = open_store(store_path)
    try:
        if not rest:
            rows = store.live_processes()
            for row in sorted(rows, key=lambda item: str(item.get("process_id", ""))):
                print(f"{row.get('process_id', '')} {row.get('capability_id', '')}")
            return 0
        process_id = rest[0]
        try:
            activation = store.activation_for(process_id)
        except KeyError:
            print("没有这个进程", file=sys.stderr)
            return 1
        room = activation.get("room") if isinstance(activation.get("room"), dict) else {}
        print(format_room(room))
        return 0
    finally:
        store.close()


def format_room(room: dict) -> str:
    """Plain lines from a room payload. Variable values are never included."""
    shell = _mapping(room.get("shell"))
    filesystem = _mapping(room.get("filesystem"))
    memory = _mapping(room.get("memory"))
    communication = _mapping(room.get("communication"))
    policy = _mapping(room.get("policy")) or _mapping(room.get("lifecycle"))
    compute = _mapping(room.get("compute"))
    names: list[str] = []
    for key in _mapping(shell.get("env")):
        if key not in names:
            names.append(str(key))
    for key in shell.get("env_file_keys") or ():
        if str(key) not in names:
            names.append(str(key))
    roots = [
        f"{item.get('name')}={item.get('path')}"
        for item in filesystem.get("roots") or ()
        if isinstance(item, dict)
    ]
    pages = [
        str(item.get("address", ""))
        for item in memory.get("pages") or ()
        if isinstance(item, dict) and item.get("address")
    ]
    hosts = [str(host) for host in communication.get("outbound_hosts") or ()]
    runtime = policy.get("max_runtime_seconds")
    return "\n".join(
        (
            f"工作目录: {shell.get('cwd', '')}",
            f"环境文件: {shell.get('env_file', '') or '无'}",
            f"环境变量: {', '.join(names) or '无'}",
            f"允许的目录: {', '.join(roots) or '无'}",
            f"读写档位: {filesystem.get('access_mode', '')}",
            f"内存页: {', '.join(pages) or '无'}",
            f"外网名单: {', '.join(hosts) or '未限制'}",
            f"墙钟: {'不限' if runtime is None else runtime}",
            f"启动等待: {policy.get('startup_timeout_seconds', '')}",
            f"同时接单: {compute.get('max_concurrent_tasks', '')}",
            f"同步工人: {compute.get('max_sync_workers', '')}",
        )
    )


def _mapping(value: object) -> dict:
    return dict(value) if isinstance(value, dict) else {}


SPEC = CommandSpec(name="room", run=run)
