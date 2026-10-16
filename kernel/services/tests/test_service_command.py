"""A service is created empty, then existing processes are bound to it."""

import os

from kernel.command import main
from kernel.command.service import run
from kernel.process.ledger import FileResourceStore


def test_service_create_does_not_save_a_launch_recipe(tmp_path, capsys) -> None:
    path = tmp_path / "resources.json"
    locator = f"file:{path}"
    assert main(["service", "create", "planner", "--resource-store", locator]) == 0
    assert capsys.readouterr().out.strip() == "planner"
    store = FileResourceStore(path)
    try:
        assert store.service_record("planner") == {"name": "planner"}
        assert store.service_members("planner") == ()
    finally:
        store.close()


def test_the_same_service_accepts_processes_one_after_another(tmp_path, capsys) -> None:
    path = tmp_path / "resources.json"
    locator = f"file:{path}"
    assert run(["create", "coder", "--resource-store", locator]) == 0
    capsys.readouterr()
    store = FileResourceStore(path, reap=False)
    try:
        store.register_process("proc-a", "model.a", os.getpid(), "running")
        store.register_process("proc-b", "tools.bash", os.getpid(), "running")
    finally:
        store.close()
    assert run(
        ["bind", "coder", "--process", "proc-a", "--role", "model", "--resource-store", locator]
    ) == 0
    assert run(
        ["bind", "coder", "--process", "proc-b", "--role", "tool", "--resource-store", locator]
    ) == 0
    assert run(
        ["bind", "coder", "--process", "proc-a", "--role", "model", "--resource-store", locator]
    ) == 0
    store = FileResourceStore(path, reap=False)
    try:
        members = {row["process_id"]: row["role"] for row in store.service_members("coder")}
        assert members == {"proc-a": "model", "proc-b": "tool"}
        assert store.services_for_process("proc-a") == ("coder",)
    finally:
        store.close()
    assert run(
        ["unbind", "coder", "--process", "proc-a", "--resource-store", locator]
    ) == 0
    store = FileResourceStore(path, reap=False)
    try:
        row = store.get_process("proc-a")
        assert row is not None
        assert row["status"] == "running"
        assert store.services_for_process("proc-a") == ()
        assert [item["process_id"] for item in store.service_members("coder")] == ["proc-b"]
    finally:
        store.close()


def test_one_process_can_belong_to_more_than_one_service(tmp_path) -> None:
    path = tmp_path / "resources.json"
    locator = f"file:{path}"
    store = FileResourceStore(path, reap=False)
    try:
        store.create_service("left")
        store.create_service("right")
        store.register_process("proc-a", "model.a", os.getpid(), "running")
        store.bind_service("left", "proc-a", "model")
        store.bind_service("right", "proc-a", "model")
        assert store.services_for_process("proc-a") == ("left", "right")
        store.delete_service("left")
        assert store.get_process("proc-a")["status"] == "running"
        assert store.services_for_process("proc-a") == ("right",)
    finally:
        store.close()


def test_an_old_service_recipe_is_refused(tmp_path) -> None:
    path = tmp_path / "resources.json"
    path.write_text(
        """
        {
          "version": 2,
          "sections": {
            "process": {
              "processes": {},
              "layout": [null, {}],
              "shares": [],
              "failures": [],
              "names": {"coder": {"model": "proc-a"}},
              "specs": {"coder": {"kind": "agent", "members": ["model.a"]}}
            }
          }
        }
        """,
        encoding="utf-8",
    )
    try:
        FileResourceStore(path, reap=False)
    except ValueError as exc:
        assert "旧的服务配方" in str(exc)
    else:
        raise AssertionError("旧配方不应该被静默读入")


def test_service_list_can_be_empty(tmp_path, capsys) -> None:
    locator = f"file:{tmp_path / 'resources.json'}"
    assert run(["list", "--resource-store", locator]) == 0
    assert capsys.readouterr().out == ""


def test_bind_requires_an_existing_service(tmp_path, capsys) -> None:
    locator = f"file:{tmp_path / 'resources.json'}"
    assert run(
        ["bind", "missing", "--process", "proc-a", "--role", "model", "--resource-store", locator]
    ) == 1
    assert "没有这个服务" in capsys.readouterr().err
