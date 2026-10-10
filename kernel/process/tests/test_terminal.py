"""The Linope terminal runs commands itself and keeps processes it starts."""

from __future__ import annotations

import subprocess

from kernel.command.terminal import (
    Session,
    command_lines,
    offer_env_files,
    resource_href,
    run,
    slip,
)
from kernel.environment.shell import find_env_files
from kernel.process.process_creat.instances import discover_instances
from kernel.services import Member, Ticket


class _Kept:
    """A fake service with one member. The terminal only sees the four methods."""

    def __init__(self, capability: str = "model.openai_chat_model") -> None:
        self.capability = capability
        self.is_alive = True
        self.stopped = False
        self.messages: list[dict] = []
        self._bodies: dict[str, object] = {}

    def members(self):
        return (
            Member(
                role="capability",
                capability=self.capability,
                process_id="p1",
                pid=41,
                alive=self.is_alive,
            ),
        )

    def close(self) -> None:
        self.stopped = True
        self.is_alive = False

    def submit(self, request, *, timeout=10):
        del timeout
        message = request.message()
        self.messages.append(message)
        ticket = Ticket(ticket_id=str(len(self.messages)), process_id="p1")
        self._bodies[ticket.ticket_id] = message.get("body")
        return ticket

    def wait(self, ticket, timeout=10):
        del timeout
        if self._bodies.get(ticket.ticket_id) is None and self.messages[-1].get("operation") == "ping":
            return {"event": "pong"}
        return {"event": "result", "result": self._bodies.get(ticket.ticket_id)}


def test_only_a_whole_line_is_a_command() -> None:
    names = frozenset({"load", "room", "start"})
    text = "\n".join(
        (
            "请单独写一行",
            "load tools.read tool 请读 a.md",
            "这句话里有 load 但不是命令",
            "linope room",
        )
    )
    assert command_lines(text, names) == [
        "load tools.read tool 请读 a.md",
        "room",
    ]


def test_slip_carries_the_address_and_not_a_secret(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-secret")
    body = "请看 http://127.0.0.1:9/resources/abc"
    message = slip("prompt", body)
    assert message == {
        "operation": "load",
        "kind": "prompt",
        "body": body,
        "href": "http://127.0.0.1:9/resources/abc",
    }
    assert resource_href("没有地址") is None
    assert "sk-test-secret" not in str(message)


def test_start_keeps_the_process_until_the_session_closes(tmp_path) -> None:
    kept = _Kept()

    class Holding(Session):
        def open_started(self, options):
            assert options[0] == "model.openai_chat_model"
            return [kept]

    locator = f"file:{tmp_path / 'resources.json'}"
    session = Holding()
    session.turn(f"start model.openai_chat_model --resource-store {locator}")
    assert kept.stopped is False
    session.close()
    assert kept.stopped is True


def test_load_sends_a_slip_to_the_living_process(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-secret")
    kept = _Kept()

    class Holding(Session):
        def __init__(self) -> None:
            super().__init__()
            self.opened = 0

        def open_started(self, options):
            self.opened += 1
            return [kept]

    locator = f"file:{tmp_path / 'resources.json'}"
    session = Holding()
    session.turn(f"start model.openai_chat_model --resource-store {locator}")
    session.turn(
        "load model.openai_chat_model prompt 请看 "
        f"http://127.0.0.1:9/resources/abc --resource-store {locator}"
    )
    assert session.opened == 1
    assert session._last_model == (locator, "model.openai_chat_model")
    assert kept.stopped is False
    message = kept.messages[-1]
    assert message["operation"] == "load"
    assert message["kind"] == "prompt"
    assert message["href"] == "http://127.0.0.1:9/resources/abc"
    assert message["body"] == "请看 http://127.0.0.1:9/resources/abc"
    assert "sk-test-secret" not in str(message)
    returned = session._prompt_last("文件内容")
    assert kept.messages[-1] == slip("prompt", "文件内容")
    assert "sk-test-secret" not in returned
    session.close()


def test_bare_address_stays_on_the_slip_and_the_model_reads_the_file(
    tmp_path, monkeypatch
) -> None:
    prompt = "你是调度。任务写在这里。"
    target = tmp_path / "调度.txt"
    target.write_text(prompt, encoding="utf-8")
    href = "http://127.0.0.1:9/resources/ab"
    message = slip("prompt", href)
    assert message["body"] == href
    assert message["href"] == href
    assert prompt not in message["body"]

    store_path = tmp_path / "resources.json"
    monkeypatch.setenv("LINOPE_RESOURCE_STORE", f"file:{store_path}")
    monkeypatch.chdir(tmp_path)
    from kernel.process.hypermedia.link import Link
    from kernel.process.ledger import FileResourceStore
    from kernel.resource.memory.page import Page

    store = FileResourceStore(store_path, reap=False)
    try:
        store.save_page(
            Page(address=str(target.resolve()), size=len(prompt.encode("utf-8"))),
            Link(relation="self", resource_id=str(target.resolve()), handle="ab"),
        )
    finally:
        store.close()
    from capability.model.model_runtime.model_main import _prompt_text

    assert _prompt_text(href) == prompt
    assert _prompt_text(f"请看 {href}") == f"请看 {href}"


def test_follow_stops_and_shows_the_rest(capsys) -> None:
    class Scripted(Session):
        def __init__(self) -> None:
            super().__init__()
            self.follow_limit = 2
            self._last_model = ("store", "model.openai_chat_model")
            self.calls: list[str] = []

        def execute(self, line: str) -> str:
            self.calls.append(line)
            if "tools.read" in line:
                return "文件内容"
            return "load tools.read tool 请读 a.md"

        def _prompt_last(self, text: str) -> str:
            self.calls.append("back:" + text)
            return "load tools.read tool 再读"

    session = Scripted()
    session.turn("load model.openai_chat_model prompt hi")
    shown = capsys.readouterr().out
    assert "还有没跑的命令" in shown
    assert "再读" in shown
    assert session.calls.count("back:文件内容") == 1
    assert sum("tools.read" in item for item in session.calls) == 1


def test_room_does_not_start_powershell(monkeypatch, tmp_path) -> None:
    def explode(*_args, **_kwargs):
        raise AssertionError("终端不应启动外部程序")

    monkeypatch.setattr(subprocess, "Popen", explode)
    monkeypatch.setattr(subprocess, "run", explode)
    locator = f"file:{tmp_path / 'resources.json'}"
    Session().turn(f"room --resource-store {locator}")


def test_run_leaves_on_exit(monkeypatch) -> None:
    answers = iter(["n", "exit"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))
    assert run([]) == 0


def test_find_env_files_lists_names_and_skips_vendor_trees(tmp_path) -> None:
    secret = tmp_path / "capability"
    secret.mkdir()
    (secret / ".env").write_text("OPENAI_API_KEY=sk-test-secret\n", encoding="utf-8")
    vendor = tmp_path / "Agent-libOS-main" / "fixtures"
    vendor.mkdir(parents=True)
    (vendor / ".env").write_text("OTHER=hidden\n", encoding="utf-8")
    found = find_env_files(tmp_path)
    assert found == ((str((secret / ".env").resolve()), ("OPENAI_API_KEY",)),)
    assert "sk-test-secret" not in str(found)


def test_offer_records_the_accepted_file(monkeypatch, tmp_path) -> None:
    config = tmp_path / "project" / ".linope" / "config.json"
    monkeypatch.setattr(
        "kernel.resource.store.locator.project_config_path",
        lambda: config,
    )
    folder = tmp_path / "tree" / "capability"
    folder.mkdir(parents=True)
    env = folder / ".env"
    env.write_text("ANTHROPIC_API_KEY=sk-test-secret\n", encoding="utf-8")
    lines: list[str] = []
    recorded = offer_env_files(
        str(tmp_path / "tree"),
        lambda _prompt="": "y",
        lines.append,
    )
    shown = "".join(lines)
    assert recorded == str(env.resolve())
    assert "sk-test-secret" not in shown
    assert "ANTHROPIC_API_KEY" in shown
    assert "已记下" in shown


def test_offer_without_a_file_asks_the_person_to_create_one(tmp_path) -> None:
    lines: list[str] = []

    def refuse(_prompt: str = "") -> str:
        raise AssertionError("没有文件时不应询问")

    assert offer_env_files(str(tmp_path), refuse, lines.append) is None
    assert "env init" in "".join(lines)


def test_offer_decline_does_not_record(monkeypatch, tmp_path) -> None:
    config = tmp_path / "project" / ".linope" / "config.json"
    monkeypatch.setattr(
        "kernel.resource.store.locator.project_config_path",
        lambda: config,
    )
    folder = tmp_path / "tree"
    folder.mkdir()
    (folder / ".env").write_text("OPENAI_API_KEY=sk-test-secret\n", encoding="utf-8")
    lines: list[str] = []
    assert offer_env_files(str(folder), lambda _prompt="": "n", lines.append) is None
    assert not config.exists()
    assert "sk-test-secret" not in "".join(lines)
    assert "env init" in "".join(lines)


def test_terminal_is_registered_and_pwsh_is_gone() -> None:
    from kernel.command.dispatch import command_table

    assert "terminal" in command_table()
    assert "tools.pwsh" not in discover_instances()
