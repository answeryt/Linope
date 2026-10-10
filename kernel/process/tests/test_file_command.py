"""Create a file with linope file and record its long-term page."""

from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path

import pytest

from kernel.process.hypermedia.file_link import representation_for_file
from kernel.process.hypermedia.follow import follow_selected
from kernel.process.hypermedia.uri import parse_resource_uri
from kernel.resource.definition import ResourceKind
from kernel.resource.memory.page import PageState, page_for_target
from kernel.resource.memory.page_table import PageTable
from kernel.process.ledger import FileResourceStore
from kernel.services import ServiceHost

ROOT = Path(__file__).resolve().parents[3]
LINOPE = ROOT / "linope.cmd"


@contextmanager
def _server(tmp_path: Path):
    store = tmp_path / "resources.json"
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "kernel.command",
            "resources",
            "serve",
            "--host",
            "127.0.0.1",
            "--port",
            "0",
            "--resource-store",
            str(store),
        ],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    state_path = tmp_path / "http-server.json"
    try:
        for _ in range(100):
            if state_path.is_file():
                try:
                    state = json.loads(state_path.read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    state = {}
                if state.get("port"):
                    yield store, state
                    return
            if process.poll() is not None:
                raise RuntimeError(process.stderr.read())
            time.sleep(0.05)
        raise TimeoutError("resource server did not start")
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=10)
        state_path.unlink(missing_ok=True)


def _run(tmp_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    store = tmp_path / "resources.json"
    command = [
        sys.executable,
        "-m",
        "kernel.command",
        "file",
        *args,
        "--resource-store",
        str(store),
    ]
    with _server(tmp_path):
        return subprocess.run(
            subprocess.list2cmdline(command),
            cwd=tmp_path,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            shell=True,
            check=False,
            timeout=120,
            env={**os.environ, "PYTHONPATH": str(ROOT), "PYTHONUTF8": "1"},
        )


def _create_file_for_server(
    tmp_path: Path,
    store: Path,
    target: Path,
    content: str,
) -> dict:
    command = [
        sys.executable,
        "-m",
        "kernel.command",
        "file",
        "once",
        str(target),
        "--",
        content,
        "--resource-store",
        str(store),
    ]
    result = subprocess.run(
        subprocess.list2cmdline(command),
        cwd=tmp_path,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        shell=True,
        check=False,
        timeout=120,
        env={**os.environ, "PYTHONPATH": str(ROOT), "PYTHONUTF8": "1"},
    )
    return _payload(result)


def _payload(result: subprocess.CompletedProcess[str]) -> dict:
    assert result.returncode == 0, result.stderr or result.stdout
    return ast.literal_eval(result.stdout.strip())


def test_put_replaces_the_same_address() -> None:
    table = PageTable().place(page_for_target("notes.md", 1))
    updated = table.put(page_for_target("notes.md", 4).with_state(PageState.PINNED))
    assert [page.address for page in updated.pages] == ["notes.md"]
    assert updated.pages[0].size == 4
    assert updated.pages[0].state is PageState.PINNED
    with pytest.raises(ValueError):
        table.place(page_for_target("notes.md", 2))


def test_once_writes_a_resident_page(tmp_path: Path) -> None:
    target = tmp_path / "notes.md"
    result = _run(tmp_path, "once", str(target), "--", "hello")
    payload = _payload(result)

    assert target.read_text(encoding="utf-8") == "hello"
    assert payload["path"] == str(target.resolve())
    assert payload["bytes"] == len("hello".encode("utf-8"))
    assert payload["task"] == "occupy"
    assert payload["state"] == "resident"
    assert payload["href"].startswith("http://127.0.0.1:")

    store = FileResourceStore(tmp_path / "resources.json")
    try:
        page = store.page_at(payload["path"])
        found = store.link_at(parse_resource_uri(payload["href"]))
    finally:
        store.close()
    assert page is not None
    assert page.state is PageState.RESIDENT
    assert page.size == payload["bytes"]
    assert found is not None
    stored_page, link = found
    assert stored_page.address == payload["path"]
    assert link.relation == "self"
    assert link.handle == parse_resource_uri(payload["href"])
    followed = follow_selected(
        representation_for_file(link.resource_id, link.handle),
        {link.resource_id},
    )
    assert [item.resource_id for item in followed.followed] == [payload["path"]]


def test_lasting_page_cannot_be_swapped_out(tmp_path: Path) -> None:
    target = tmp_path / "scripts" / "main.py"
    result = _run(tmp_path, "lasting", str(target), "--", 'print("hi")')
    payload = _payload(result)

    assert target.read_text(encoding="utf-8") == 'print("hi")'
    assert payload["state"] == "pinned"
    assert payload["task"] == "occupy"
    assert payload["href"].startswith("http://127.0.0.1:")

    store = FileResourceStore(tmp_path / "resources.json")
    try:
        page = store.page_at(payload["path"])
    finally:
        store.close()
    assert page is not None
    assert page.state is PageState.PINNED
    with pytest.raises(ValueError, match="pinned page cannot be swapped out"):
        PageTable().put(page).swap_out(page.address)


def test_same_path_keeps_one_page(tmp_path: Path) -> None:
    target = tmp_path / "notes.md"
    first = _payload(_run(tmp_path, "once", str(target), "--", "hello"))
    second = _payload(_run(tmp_path, "lasting", str(target), "--", "hello!"))

    assert target.read_text(encoding="utf-8") == "hello!"
    assert second["path"] == first["path"]
    assert second["bytes"] == len("hello!".encode("utf-8"))
    assert second["state"] == "pinned"
    assert second["href"]
    assert second["href"] != first["href"]

    store = FileResourceStore(tmp_path / "resources.json")
    try:
        page = store.page_at(second["path"])
    finally:
        store.close()
    assert page is not None
    assert page.size == second["bytes"]
    assert page.state is PageState.PINNED
    store = FileResourceStore(tmp_path / "resources.json")
    try:
        assert store.link_at(parse_resource_uri(first["href"])) is None
        assert store.link_at(parse_resource_uri(second["href"])) is not None
    finally:
        store.close()


def test_resource_kinds_stay_the_same() -> None:
    assert [kind.value for kind in ResourceKind] == [
        "context",
        "model",
        "memory",
        "workspace",
        "tool",
        "network",
        "identity",
        "persistence",
        "lifecycle",
        "communication",
        "prompt",
    ]


def test_ask_with_an_unknown_handle_stops_before_the_model(tmp_path: Path) -> None:
    store = tmp_path / "resources.json"
    command = [
        str(LINOPE),
        "ask",
        "model.anthropic_model",
        "http://127.0.0.1:1/resources/deadbeef",
        "--",
        "请问你是谁",
        "--resource-store",
        str(store),
    ]
    result = subprocess.run(
        subprocess.list2cmdline(command),
        cwd=tmp_path,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        shell=True,
        check=False,
        timeout=30,
        env={**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"},
    )
    assert result.returncode == 1
    assert result.stdout.strip() == ""
    assert result.stderr.strip()


def test_ask_follows_http_href_and_sends_file_before_question(tmp_path: Path) -> None:
    from kernel.command import ask as ask_command

    target = tmp_path / "identity.md"
    captured: dict[str, object] = {}

    class FakeProcess:
        def submit(self, message: dict, **kwargs: object) -> dict:
            del kwargs
            captured["message"] = message
            return message

        def wait(self, receipt: dict, timeout: float = 10) -> dict:
            del receipt, timeout
            return {"event": "result", "result": "ok"}

        def stop(self) -> None:
            return None

    class FakeReconciler:
        def __init__(self, pool: object) -> None:
            del pool

        def launch(self, declaration: object, **kwargs: object) -> tuple[FakeProcess, ...]:
            del declaration, kwargs
            return (FakeProcess(),)

    host = ServiceHost(
        reconciler=FakeReconciler,
        load_declaration=lambda _capability, _changes: (object(), object()),
    )
    with _server(tmp_path) as (store, _state):
        payload = _create_file_for_server(tmp_path, store, target, "identity")
        result = ask_command.run(
            [
                "model.anthropic_model",
                payload["href"],
                "--",
                "请问你是谁",
                "--resource-store",
                str(store),
            ],
            host=host,
        )
    assert result == 0
    message = captured["message"]
    assert message["kind"] == "prompt"
    assert message["body"] == [
        {"role": "user", "content": "identity"},
        {"role": "user", "content": "请问你是谁"},
    ]


def test_ask_stops_when_the_menu_has_no_content(tmp_path: Path, capsys) -> None:
    from urllib.request import Request, urlopen

    from kernel.command import ask as ask_command

    target = tmp_path / "identity.md"
    with _server(tmp_path) as (store, _state):
        payload = _create_file_for_server(tmp_path, store, target, "identity")
        request = Request(
            payload["href"] + "/swap",
            data=b"{}",
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        with urlopen(request, timeout=10) as response:
            assert json.loads(response.read().decode("utf-8"))["state"] == "swapped"
        result = ask_command.run(
            [
                "model.anthropic_model",
                payload["href"],
                "--",
                "请问你是谁",
                "--resource-store",
                str(store),
            ]
        )
    assert result == 1
    assert "当前菜单没有 content" in capsys.readouterr().err
