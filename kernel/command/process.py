"""One capability process: start, list, stop, scale, share, and workers."""

from __future__ import annotations

import sys

from kernel.command.convention import UsageError, guard, parse
from kernel.command.room import list_processes, show_process
from kernel.command.start import run as start_process
from kernel.command.thread import run as workers
from kernel.process.ledger import open_store
from kernel.process.profile import ProfileUnavailable, load_declaration
from kernel.process.reconcile import ProcessReconciler
from kernel.resource.pool import ResourcePool

USAGE = "用法: linope process start|list|status|stop|scale|share|workers ..."


@guard(USAGE)
def run(argv: list[str]) -> int:
    if not argv:
        raise UsageError(USAGE)
    action, rest = argv[0], argv[1:]
    if action == "start":
        return start_process(rest)
    if action == "list":
        return list_processes(rest)
    if action == "status":
        return show_process(rest)
    if action == "stop":
        return _stop(rest)
    if action == "scale":
        return _scale(rest)
    if action == "share":
        return _share(rest)
    if action == "workers":
        return workers(rest)
    raise UsageError(USAGE)


def _stop(argv: list[str]) -> int:
    invocation = parse(argv, flags={}, usage="用法: linope process stop <进程号>")
    if len(invocation.position) != 1:
        raise UsageError("用法: linope process stop <进程号>")
    process_id = invocation.position[0]
    store = open_store(invocation.store)
    try:
        if store.get_process(process_id) is None:
            print("没有这个进程", file=sys.stderr)
            return 1
        store.set_desired(process_id, "stop")
    finally:
        store.close()
    print(process_id)
    return 0


def _scale(argv: list[str]) -> int:
    invocation = parse(argv, flags={"count": "int"}, usage="用法: linope process scale <能力> --count <份数>")
    if len(invocation.position) != 1 or invocation.options.get("count") is None:
        raise UsageError("用法: linope process scale <能力> --count <份数>")
    capability = invocation.position[0]
    count = int(invocation.options["count"])
    if count < 1:
        raise UsageError("份数至少为 1")
    store = open_store(invocation.store)
    try:
        selected, settings = store.selected_layout()
        if selected is None:
            print("还没选择布局，一次只能启动一份。先执行 linope layout use", file=sys.stderr)
            return 1
        updated = dict(settings)
        updated["count"] = count
        store.select_layout(selected, updated)
        try:
            declaration, definition = load_declaration(capability, ())
            ProcessReconciler(ResourcePool(store)).launch(
                declaration,
                definition=definition,
                replica_count=count,
            )
        except (ProfileUnavailable, ValueError, KeyError, RuntimeError, OSError) as exc:
            print(exc, file=sys.stderr)
            return 1
    finally:
        store.close()
    print(f"process scale {capability} {count}")
    return 0


def _share(argv: list[str]) -> int:
    invocation = parse(argv, flags={}, usage="用法: linope process share <能力>... | linope process share off")
    store = open_store(invocation.store)
    try:
        if invocation.position == ("off",):
            store.clear_share()
            print("share off")
            return 0
        if not invocation.position:
            raise UsageError("用法: linope process share <能力>... | linope process share off")
        store.share_capabilities(invocation.position)
        print("share " + " ".join(invocation.position))
        return 0
    finally:
        store.close()
