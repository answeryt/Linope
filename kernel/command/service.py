"""Create a service, then bind existing processes to it."""

from __future__ import annotations

import sys

from kernel.command.convention import UsageError, emit, guard, parse
from kernel.process.ledger import open_store
from kernel.services import LaunchOptions, ServiceRequest, open_service

USAGE = "用法: linope service create|status|bind|unbind|delete|call ..."
CREATE = "用法: linope service create <名字>"
BIND = "用法: linope service bind <名字> --process <进程号> --role <关系>"
UNBIND = "用法: linope service unbind <名字> --process <进程号>"
DELETE = "用法: linope service delete <名字>"
STATUS = "用法: linope service status <名字>"
CALL = "用法: linope service call <名字> [--role <关系>] [--kind <种类>] [--operation <操作>] [-- <正文>]"


@guard(USAGE)
def run(argv: list[str]) -> int:
    if not argv:
        raise UsageError(USAGE)
    action, rest = argv[0], argv[1:]
    if action == "create":
        return _create(rest)
    if action == "status":
        return _status(rest)
    if action == "bind":
        return _bind(rest)
    if action == "unbind":
        return _unbind(rest)
    if action == "delete":
        return _delete(rest)
    if action == "call":
        return _call(rest)
    raise UsageError(USAGE)


def _create(argv: list[str]) -> int:
    invocation = parse(argv, flags={}, usage=CREATE)
    if len(invocation.position) != 1:
        raise UsageError(CREATE)
    name = invocation.position[0]
    store = open_store(invocation.store)
    try:
        try:
            store.create_service(name)
        except ValueError as exc:
            print(exc, file=sys.stderr)
            return 1
    finally:
        store.close()
    emit({"name": name}, as_json=invocation.json, text=name)
    return 0

def _status(argv: list[str]) -> int:
    invocation = parse(argv, flags={}, usage=STATUS)
    if len(invocation.position) != 1:
        raise UsageError(STATUS)
    name = invocation.position[0]
    store = open_store(invocation.store)
    try:
        record = store.service_record(name)
        members = store.service_members(name) if record is not None else ()
    finally:
        store.close()
    if record is None:
        print(f"没有这个服务: {name}", file=sys.stderr)
        return 1
    payload = {"name": name, "processes": list(members)}
    if invocation.json:
        emit(payload, as_json=True)
        return 0
    print(name)
    for member in members:
        print(f"{member['process_id']} {member['role']} {member['capability_id']} {member['status']}")
    return 0


def _bind(argv: list[str]) -> int:
    invocation = parse(argv, flags={"process": "str", "role": "str"}, usage=BIND)
    if len(invocation.position) != 1 or not invocation.options.get("process") or not invocation.options.get("role"):
        raise UsageError(BIND)
    name = invocation.position[0]
    process_id = str(invocation.options["process"])
    role = str(invocation.options["role"])
    store = open_store(invocation.store)
    try:
        try:
            result = store.bind_service(name, process_id, role)
        except KeyError as exc:
            print(_missing(name, exc), file=sys.stderr)
            return 1
        except ValueError as exc:
            print(exc, file=sys.stderr)
            return 1
    finally:
        store.close()
    emit(
        {"name": name, "process_id": process_id, "role": role, "changed": result["changed"]},
        as_json=invocation.json,
        text=f"{name} {process_id} {role}",
    )
    return 0


def _unbind(argv: list[str]) -> int:
    invocation = parse(argv, flags={"process": "str"}, usage=UNBIND)
    if len(invocation.position) != 1 or not invocation.options.get("process"):
        raise UsageError(UNBIND)
    name = invocation.position[0]
    process_id = str(invocation.options["process"])
    store = open_store(invocation.store)
    try:
        try:
            store.unbind_service(name, process_id)
        except KeyError as exc:
            print(_missing(name, exc), file=sys.stderr)
            return 1
    finally:
        store.close()
    emit({"name": name, "process_id": process_id}, as_json=invocation.json, text=f"{name} {process_id}")
    return 0


def _delete(argv: list[str]) -> int:
    invocation = parse(argv, flags={}, usage=DELETE)
    if len(invocation.position) != 1:
        raise UsageError(DELETE)
    name = invocation.position[0]
    store = open_store(invocation.store)
    try:
        try:
            store.delete_service(name)
        except KeyError:
            print(f"没有这个服务: {name}", file=sys.stderr)
            return 1
    finally:
        store.close()
    emit({"name": name}, as_json=invocation.json, text=name)
    return 0


def _call(argv: list[str]) -> int:
    invocation = parse(
        argv,
        flags={"role": "str", "kind": "str", "operation": "str"},
        usage=CALL,
    )
    if len(invocation.position) != 1:
        raise UsageError(CALL)
    name = invocation.position[0]
    try:
        service = open_service(name, LaunchOptions(store_locator=invocation.store))
    except KeyError:
        print(f"没有这个服务: {name}", file=sys.stderr)
        return 1
    except (ValueError, RuntimeError) as exc:
        print(exc, file=sys.stderr)
        return 1
    try:
        ticket = service.submit(
            ServiceRequest(
                kind=str(invocation.options.get("kind") or ""),
                body=invocation.body,
                role=str(invocation.options.get("role") or ""),
                operation=str(invocation.options.get("operation") or "load"),
            )
        )
        reply = service.wait(ticket)
    except (KeyError, RuntimeError, TimeoutError) as exc:
        print(exc, file=sys.stderr)
        return 1
    finally:
        service.close()
    if invocation.json:
        emit(reply, as_json=True)
        return 0
    print(reply)
    return 0


def _missing(name: str, exc: KeyError) -> str:
    missing = str(exc).strip("'")
    if missing == name:
        return f"没有这个服务: {name}"
    return f"没有这个进程: {missing}"
