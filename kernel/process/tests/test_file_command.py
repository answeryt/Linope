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

from kernel.hypermedia.file_link import representation_for_file
from kernel.hypermedia.follow import follow_selected
from kernel.hypermedia.uri import parse_resource_uri
from kernel.resource.definition import ResourceKind
from kernel.resource.memory.page import PageState
from kernel.process.ledger import FileResourceStore

ROOT = Path(__file__).resolve().parents[3]


@contextmanager
def _server(tmp_path: Path):
    store = tmp_path / "resources.json"
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "kernel.command",
            "resource",
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
    if "--" in args:
        index = args.index("--")
        head = args[:index]
        body = args[index + 1 :]
        command = [
            sys.executable,
            "-m",
            "kernel.command",
            "resource",
            "file",
            *head,
            "--resource-store",
            str(store),
            "--",
            *body,
        ]
    else:
        command = [
            sys.executable,
            "-m",
            "kernel.command",
            "resource",
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


def _payload(result: subprocess.CompletedProcess[str]) -> dict:
    assert result.returncode == 0, result.stderr or result.stdout
    return ast.literal_eval(result.stdout.strip())


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


def test_lasting_writes_a_pinned_page(tmp_path: Path) -> None:
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
        "memory",
        "workspace",
        "tool",
        "network",
        "communication",
    ]
