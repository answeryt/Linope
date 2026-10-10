"""HTTP resource representations and loopback server behavior."""

from __future__ import annotations

import ast
import json
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path
import os
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from kernel.process.communication.channel import ChannelOpen
from kernel.process.communication.ledger.mailbox import LedgerChannel
from kernel.process.hypermedia.observation import act_if_offered, deliver_observation
from kernel.process.hypermedia.uri import parse_resource_uri
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


def _create_file(tmp_path: Path, store: Path, target: Path, text: str = "hello") -> dict:
    command = [
        sys.executable,
        "-m",
        "kernel.command",
        "file",
        "once",
        str(target),
        "--",
        text,
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
    assert result.returncode == 0, result.stderr or result.stdout
    return ast.literal_eval(result.stdout.strip())


def test_http_resource_and_content_are_hateoas_links(tmp_path: Path) -> None:
    target = tmp_path / "identity.md"
    with _server(tmp_path) as (store, state):
        payload = _create_file(tmp_path, store, target)
        href = payload["href"]
        assert f":{state['port']}/resources/" in href

        with urlopen(href, timeout=10) as response:
            representation = json.loads(response.read().decode("utf-8"))
        assert representation["type"] == "file"
        assert representation["state"] == "resident"
        assert representation["_links"]["self"]["rel"] == "self"
        assert representation["_links"]["self"]["href"] == href
        content_link = representation["_links"]["content"]
        assert content_link["rel"] == "content"
        assert content_link["method"] == "GET"
        assert content_link["type"].startswith("text/plain")

        with urlopen(content_link["href"], timeout=10) as response:
            assert response.read().decode("utf-8") == "hello"

        assert parse_resource_uri(href)


def test_http_json_content_is_available_to_rag_clients(tmp_path: Path) -> None:
    target = tmp_path / "identity.md"
    with _server(tmp_path) as (store, _state):
        payload = _create_file(tmp_path, store, target)
        request = Request(
            payload["href"] + "/content",
            headers={"Accept": "application/json"},
        )
        with urlopen(request, timeout=10) as response:
            content = json.loads(response.read().decode("utf-8"))
        assert content["content"] == "hello"
        assert content["_links"]["self"]["rel"] == "self"


def test_http_server_does_not_expose_unknown_resources_or_database(
    tmp_path: Path,
) -> None:
    with _server(tmp_path) as (store, state):
        unknown = f"http://127.0.0.1:{state['port']}/resources/deadbeef"
        try:
            urlopen(unknown, timeout=10)
        except HTTPError as exc:
            assert exc.code == 404
        else:
            raise AssertionError("unknown resource unexpectedly returned 200")

        database = f"http://127.0.0.1:{state['port']}/resources.json"
        try:
            urlopen(database, timeout=10)
        except HTTPError as exc:
            assert exc.code in {400, 404}
        else:
            raise AssertionError("database path unexpectedly returned 200")


def test_page_menu_accepts_only_the_offered_transition(tmp_path: Path) -> None:
    target = tmp_path / "identity.md"
    with _server(tmp_path) as (store, _state):
        payload = _create_file(tmp_path, store, target)
        href = payload["href"]
        pinned = _post(href + "/pin")
        assert pinned["state"] == "pinned"
        assert "pin" not in pinned["_links"]
        assert "swap" not in pinned["_links"]
        assert "content" in pinned["_links"]
        refused = _post(href + "/swap")
        assert refused["status"] == 409
        assert _get(href)["state"] == "pinned"

        admitted = _post(_get(href)["_links"]["self"]["href"] + "/admit")
        assert admitted["status"] == 409

        resident = _create_file(tmp_path, store, tmp_path / "other.md")
        swapped = _post(resident["href"] + "/swap")
        assert swapped["state"] == "swapped"
        assert set(swapped["_links"]) >= {"self", "admit"}
        assert "content" not in swapped["_links"]
        blocked = _open(swapped["_links"]["self"]["href"] + "/content")
        assert blocked == 409
        restored = _post(swapped["_links"]["admit"]["href"])
        assert restored["state"] == "resident"
        with urlopen(restored["_links"]["content"]["href"], timeout=10) as response:
            assert response.read().decode("utf-8") == "hello"


def test_stale_observation_does_not_swap_a_pinned_page(tmp_path: Path) -> None:
    target = tmp_path / "identity.md"
    with _server(tmp_path) as (store, _state):
        payload = _create_file(tmp_path, store, target)
        href = payload["href"]
        queued = _get(href)
        assert "swap" in queued["_links"]
        ledger = FileResourceStore(store, reap=False)
        try:
            channel = LedgerChannel(ChannelOpen(store=ledger, store_path=str(store)))
            deliver_observation(channel, "reader-a", queued)
            deliver_observation(channel, "reader-b", queued)
            assert channel.take("reader-a")["body"]["operation"] == "observe"
            assert channel.take("reader-b")["body"]["operation"] == "observe"
            assert _get(href)["state"] == "resident"
        finally:
            ledger.close()
        pinned = act_if_offered(href, "pin")
        assert pinned is not None
        assert pinned["state"] == "pinned"
        assert act_if_offered(href, "swap") is None
        assert _get(href)["state"] == "pinned"


def test_unleased_tool_is_absent_and_a_link_tool_does_not_occupy(
    tmp_path: Path,
) -> None:
    target = tmp_path / "identity.md"
    with _server(tmp_path) as (store, _state):
        payload = _create_file(tmp_path, store, target)
        href = payload["href"]
        assert "web_search" not in _get(href)["_links"]
        missing = _post(href + "/tools/web_search")
        assert missing["status"] == 409
        ledger = FileResourceStore(store, reap=False)
        try:
            ledger.register_process(
                "searcher",
                "tools.web_search",
                os.getpid(),
                "running",
            )
            ledger.register_process(
                "reader",
                "tools.read",
                os.getpid(),
                "running",
            )
        finally:
            ledger.close()
        menu = _get(href)
        assert menu["_links"]["web_search"]["rel"] == "web_search"
        followed = _post(menu["_links"]["web_search"]["href"], {"keep": True, "text": "hit"})
        assert followed["effect"] == "link"
        assert followed["state"] == "resident"
        assert _get(href)["state"] == "resident"
        kept = _post(menu["_links"]["read"]["href"], {"keep": True, "text": "kept"})
        assert kept["effect"] == "occupy"
        assert kept["id"] != menu["id"]
        assert _get(href)["state"] == "resident"


def test_compress_is_absent_until_leased_and_then_frees_the_page(tmp_path: Path) -> None:
    target = tmp_path / "long.md"
    text = "alpha " * 400
    with _server(tmp_path) as (store, _state):
        payload = _create_file(tmp_path, store, target, text)
        href = payload["href"]
        assert "compress" not in _get(href)["_links"]
        ledger = FileResourceStore(store, reap=False)
        try:
            ledger.register_process(
                "compressor",
                "context.sliding_window",
                os.getpid(),
                "running",
            )
        finally:
            ledger.close()
        menu = _get(href)
        assert menu["_links"]["compress"]["method"] == "POST"
        compressed = _post(menu["_links"]["compress"]["href"])
        assert compressed["state"] == "resident"
        assert compressed["id"] != menu["id"]
        assert _get(href)["state"] == "swapped"
        assert "content" not in _get(href)["_links"]
        with urlopen(compressed["_links"]["content"]["href"], timeout=10) as response:
            assert len(response.read()) < len(text.encode("utf-8"))


def _get(url: str) -> dict:
    with urlopen(Request(url, headers={"Accept": "application/json"}), timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def _post(url: str, body: dict | None = None) -> dict:
    data = json.dumps(body or {}).encode("utf-8")
    request = Request(
        url,
        data=data,
        method="POST",
        headers={"Accept": "application/json", "Content-Type": "application/json"},
    )
    try:
        with urlopen(request, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        payload = json.loads(exc.read().decode("utf-8"))
        payload["status"] = exc.code
        return payload


def _open(url: str) -> int:
    try:
        with urlopen(url, timeout=10) as response:
            response.read()
            return response.status
    except HTTPError as exc:
        return exc.code
