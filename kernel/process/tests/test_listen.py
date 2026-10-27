"""Lines typed after start reach the waiting process."""

from __future__ import annotations

import json
from pathlib import Path

from kernel.command.process.listen import _parse_line, ask_ping, hold
from kernel.command.screen.live_stream import publish_text
from kernel.process.declaration import ProcessDeclaration, ResourceClaim
from kernel.process.ledger import ProcessLedger
from kernel.process.process_creat.instances import CapabilityDefinition
from kernel.process.process_runtime.runtime import close_adapter, open_adapter
from kernel.process.reconcile import ProcessReconciler
from kernel.process.resource_record import ProcessResourceBook
from kernel.resource.lease import ResourceLeaseManager
from kernel.resource.pool import ResourcePool


class _Echo:
    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.shut = False

    async def handle_async(self, request: dict) -> str:
        self.calls.append(request)
        return f"seen:{request.get('body')}"

    def shutdown(self) -> None:
        self.shut = True


class _Service:
    def __init__(self, *processes: object) -> None:
        self._processes = {"capability": processes}
        self.closed = False

    def processes(self) -> tuple:
        return tuple(self._processes["capability"])

    def close(self) -> None:
        self.closed = True
        for process in self._processes["capability"]:
            process.stop()


def _process(
    tmp_path: Path,
    *,
    plugin: Path | None = None,
    resources: tuple[ResourceClaim, ...] | None = None,
    pid: int | None = None,
):
    ledger = ProcessLedger(tmp_path / "ledger.json")
    book = ProcessResourceBook(ledger)
    pool = ResourcePool(ResourceLeaseManager())
    paths: tuple[str, ...] = ()
    if plugin is not None:
        adapter = Path(__file__).resolve().parents[3] / "capability" / "process_adapter.py"
        paths = (str(plugin), str(adapter))
    definition = CapabilityDefinition(instance_id="sample.capability", module_paths=paths)
    claims = resources or (ResourceClaim(kind="network", identity={"channel": "ledger"}),)
    process = ProcessReconciler(pool, book).start(
        ProcessDeclaration(capability="sample.capability", resources=claims),
        definition=definition,
        pid=pid,
    )
    return book, process


def _recording_plugin(tmp_path: Path) -> Path:
    log = tmp_path / "calls.jsonl"
    plugin = tmp_path / "record_plugin.py"
    plugin.write_text(
        "import json\n"
        "from pathlib import Path\n"
        f"LOG = Path({str(log)!r})\n"
        "def load(kind, body, call_params=None):\n"
        "    with LOG.open('a', encoding='utf-8') as handle:\n"
        "        handle.write(json.dumps({'kind': kind, 'body': body}, ensure_ascii=False) + '\\n')\n"
        "    if kind == 'tool':\n"
        "        return 'tool done'\n"
        "    return 'model answered'\n"
        "async def load_async(kind, body, call_params=None):\n"
        "    return load(kind, body, call_params)\n",
        encoding="utf-8",
    )
    return plugin


def _calls(tmp_path: Path) -> list[dict]:
    path = tmp_path / "calls.jsonl"
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _contents(body: object) -> list[str]:
    assert isinstance(body, list)
    return [str(item["content"]) for item in body]


def _page(body: object) -> dict:
    assert isinstance(body, list)
    return json.loads(_contents(body)[-1])


def _system_text(body: object) -> str:
    assert isinstance(body, list)
    assert body[0]["role"] == "system"
    return str(body[0]["content"])


def _pair(tmp_path: Path, plugin: Path, *, shared: tuple[str, ...] = ()):
    ledger = ProcessLedger(tmp_path / "ledger.json")
    book = ProcessResourceBook(ledger)
    pool = ResourcePool(ResourceLeaseManager())
    adapter = Path(__file__).resolve().parents[3] / "capability" / "process_adapter.py"
    definition = CapabilityDefinition(
        instance_id="sample.capability",
        module_paths=(str(plugin), str(adapter)),
    )
    declaration = ProcessDeclaration(
        capability="sample.capability",
        resources=(ResourceClaim(kind="memory", identity={"scope": "chat"}),),
    )
    return ProcessReconciler(pool, book).launch(
        declaration,
        definition=definition,
        shared=shared,
        replica_count=2,
    )


def _activity_rows(tmp_path: Path, pid: int) -> list[dict]:
    path = tmp_path / "activity.jsonl"
    return [
        item
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
        for item in [json.loads(line)]
        if int(item.get("pid") or 0) == pid
    ]


def _assert_task_then_sleep(rows: list[dict], counterpart: str) -> None:
    activities = [str(row.get("activity") or "") for row in rows]
    with_at = activities.index("with")
    assert "sleeping" in activities[with_at + 1 :]
    matched = rows[with_at]
    assert matched["way"] == "task"
    assert str(matched["with"]) == str(counterpart)


def _echo(tmp_path: Path) -> Path:
    plugin = tmp_path / "echo_plugin.py"
    plugin.write_text(
        "import json\n"
        "def load(kind, body, call_params=None):\n"
        "    if isinstance(body, dict):\n"
        "        return json.dumps({'kind': kind, 'body': body}, ensure_ascii=False)\n"
        "    return f'seen:{body}'\n"
        "async def load_async(kind, body, call_params=None):\n"
        "    return load(kind, body, call_params)\n",
        encoding="utf-8",
    )
    return plugin


def test_load_reaches_the_waiting_adapter(tmp_path: Path, capsys) -> None:
    _book, process = _process(tmp_path, plugin=_echo(tmp_path))
    service = _Service(process)
    pid = process.pid
    assert hold(service, lines=[f"load message {pid} -- hello"], timeout=5)
    assert service.closed
    output = capsys.readouterr().out
    assert "seen:hello" in output
    assert '"type": "done"' in output


def test_tool_body_stays_a_mapping(tmp_path: Path, capsys) -> None:
    _book, process = _process(tmp_path, plugin=_echo(tmp_path))
    pid = process.pid
    hold(_Service(process), lines=[f'load tool {pid} -- {{"query": "distributed"}}'], timeout=5)
    output = capsys.readouterr().out
    assert '"kind": "tool"' in output
    assert "distributed" in output


def test_ping_comes_from_the_process_and_adds_no_lease(tmp_path: Path, capsys) -> None:
    book, process = _process(tmp_path)
    process.adapter = _Echo()
    before = len(book.get(process.pid).leases)
    reply = ask_ping(_Service(process), process.pid, timeout=1)
    assert reply is not None
    assert reply["event"] == "pong"
    assert reply["pid"] == process.pid
    assert reply["channel"] == "ledger"
    assert len(book.get(process.pid).leases) == before
    capsys.readouterr()


def test_wrong_sequence_is_not_an_answer(tmp_path: Path) -> None:
    _book, process = _process(tmp_path, pid=51001)
    process.adapter = _Echo()

    def wrong(message, timeout=1.0):
        reply = type(process).answer_ping(process, message, timeout=timeout)
        if reply is not None:
            reply["seq"] = -1
        return reply

    process.answer_ping = wrong
    assert ask_ping(_Service(process), process.pid, timeout=0.05) is None


def test_a_dead_process_does_not_answer(tmp_path: Path) -> None:
    _book, process = _process(tmp_path)
    process.stop()
    process.adapter = _Echo()
    assert hold(_Service(process), ping=True, once=True, timeout=0.05) is False


def test_adapter_stays_open_until_the_process_closes(tmp_path: Path, capsys) -> None:
    plugin = tmp_path / "echo_plugin.py"
    plugin.write_text(
        "def load(kind, body, call_params=None):\n"
        "    return f'echo:{body}'\n"
        "async def load_async(kind, body, call_params=None):\n"
        "    return load(kind, body, call_params)\n",
        encoding="utf-8",
    )
    _book, process = _process(tmp_path, plugin=plugin)
    adapter = open_adapter(process.activation.payload())
    try:
        assert adapter is not None
        import asyncio

        result = asyncio.run(
            adapter.handle_async({"operation": "load", "kind": "message", "body": "hi"})
        )
        assert result == "echo:hi"
    finally:
        close_adapter(adapter)
        process.stop()
    capsys.readouterr()


def test_load_without_an_id_is_refused(tmp_path: Path, capsys) -> None:
    _book, process = _process(tmp_path)
    hold(_Service(process), lines=["load message -- hello"], timeout=5)
    assert "full pid" in capsys.readouterr().err


def test_a_short_id_is_refused(tmp_path: Path, capsys) -> None:
    _book, process = _process(tmp_path)
    pid = str(process.pid)
    hold(_Service(process), lines=[f"load message {pid[:-1]} -- hello"], timeout=5)
    assert pid in capsys.readouterr().err


def test_full_id_reaches_only_that_process(tmp_path: Path, capsys) -> None:
    _book, first = _process(tmp_path, plugin=_echo(tmp_path))
    _other, second = _process(tmp_path, plugin=_echo(tmp_path))
    hold(
        _Service(first, second),
        lines=[f"load message {first.pid} -- hello"],
        timeout=5,
    )
    output = capsys.readouterr().out
    assert "seen:hello" in output
    assert output.count("seen:") == 1


def test_a_wrong_id_lists_the_living_ones(tmp_path: Path, capsys) -> None:
    _book, first = _process(tmp_path)
    _other, second = _process(tmp_path)
    hold(_Service(first, second), lines=["ping missing"], timeout=5)
    error = capsys.readouterr().err
    assert str(first.pid) in error
    assert str(second.pid) in error


def test_once_closes_after_one_delivered_load(tmp_path: Path, capsys) -> None:
    _book, process = _process(tmp_path, plugin=_echo(tmp_path))
    pid = process.pid
    hold(
        _Service(process),
        once=True,
        lines=[
            f'load tool {pid} -- {{"query": "distributed"}}',
            f'load tool {pid} -- {{"query": "the second"}}',
        ],
        timeout=5,
    )
    output = capsys.readouterr().out
    assert "distributed" in output
    assert "the second" not in output


def test_ping_does_not_finish_a_once_process(tmp_path: Path, capsys) -> None:
    _book, process = _process(tmp_path, plugin=_echo(tmp_path))
    pid = process.pid
    hold(
        _Service(process),
        once=True,
        lines=[
            f"ping {pid}",
            f"load message {pid} -- hello",
            f"load message {pid} -- the second",
        ],
        timeout=5,
    )
    output = capsys.readouterr().out
    assert "seen:hello" in output
    assert "the second" not in output


def test_a_wrong_id_does_not_finish_a_once_process(tmp_path: Path, capsys) -> None:
    _book, process = _process(tmp_path, plugin=_echo(tmp_path))
    pid = process.pid
    hold(
        _Service(process),
        once=True,
        lines=[
            "load message missing -- hello",
            f"load message {pid} -- hello",
        ],
        timeout=5,
    )
    captured = capsys.readouterr()
    assert "seen:hello" in captured.out
    assert str(pid) in captured.err


def test_publish_text_uses_the_terminal_event(capsys) -> None:
    publish_text("hello")
    assert json.loads(capsys.readouterr().out) == {"type": "text-delta", "text": "hello"}


def test_same_window_can_list_show_and_trace(tmp_path: Path, capsys) -> None:
    _book, process = _process(tmp_path, plugin=_echo(tmp_path))
    pid = process.pid
    hold(
        _Service(process),
        lines=[
            "list",
            f"show {pid}",
            f"load message {pid} -- hello",
            f"trace {pid}",
        ],
        timeout=5,
    )
    output = capsys.readouterr().out
    assert f"pid={pid}" in output
    assert '"rel": "self"' in output
    assert '"activity": "self"' in output
    assert "sleeping" in output
    page = next(json.loads(line) for line in output.splitlines() if '"facts"' in line)
    assert "memory" not in page


def test_a_crashed_capability_does_not_stop_the_other(tmp_path: Path, capsys) -> None:
    crash = tmp_path / "crash_plugin.py"
    crash.write_text(
        "import os\n"
        "def load(kind, body, call_params=None):\n"
        "    os._exit(1)\n"
        "async def load_async(kind, body, call_params=None):\n"
        "    return load(kind, body, call_params)\n",
        encoding="utf-8",
    )
    _book, first = _process(tmp_path, plugin=crash)
    _other, second = _process(tmp_path, plugin=_echo(tmp_path))
    hold(
        _Service(first, second),
        lines=[
            f"load message {first.pid} -- boom",
            f"load message {second.pid} -- hello",
        ],
        timeout=5,
    )
    captured = capsys.readouterr()
    assert "seen:hello" in captured.out
    assert "is gone" in captured.err or "This process" in captured.err


def test_a_prompt_file_is_kept_in_memory_and_sent_with_the_next_question(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    monkeypatch.setattr("kernel.communication.offers.tool_catalog", lambda: ())
    prompt = tmp_path / "note.md"
    prompt.write_text("you are the assistant", encoding="utf-8")
    _book, process = _process(
        tmp_path,
        plugin=_recording_plugin(tmp_path),
        resources=(
            ResourceClaim(kind="network", identity={"channel": "ledger"}),
            ResourceClaim(kind="memory", identity={"scope": "chat"}),
        ),
    )
    pid = process.pid
    hold(
        _Service(process),
        lines=[
            f"load message {pid} -- {prompt}",
            f"load message {pid} -- hello",
            f"load message {pid} -- goodbye",
        ],
        timeout=5,
    )
    calls = _calls(tmp_path)
    first = _page(calls[0]["body"])
    second = _page(calls[1]["body"])
    assert _system_text(calls[0]["body"]) == "you are the assistant"
    assert _system_text(calls[1]["body"]) == "you are the assistant"
    assert [row["content"] for row in first["rows"]] == ["hello"]
    assert "you are the assistant" not in [row["content"] for row in first["rows"]]
    assert [row["content"] for row in second["rows"]] == ["goodbye"]
    assert "hello" not in [row["content"] for row in second["rows"]]
    assert second["_links"]["message/0"]["kind"] == "user"
    saved = (tmp_path / "ledger.json").read_text(encoding="utf-8")
    assert "you are the assistant" not in saved
    assert "model answered" not in saved
    capsys.readouterr()


def test_show_prints_the_words_kept_in_memory(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setattr("kernel.communication.offers.tool_catalog", lambda: ())
    prompt = tmp_path / "note.md"
    prompt.write_text("you are the assistant", encoding="utf-8")
    _book, process = _process(
        tmp_path,
        plugin=_recording_plugin(tmp_path),
        resources=(
            ResourceClaim(kind="network", identity={"channel": "ledger"}),
            ResourceClaim(kind="memory", identity={"scope": "chat"}),
        ),
    )
    pid = process.pid
    hold(
        _Service(process),
        lines=[
            f"load message {pid} -- {prompt}",
            f"load message {pid} -- hello",
            f"show {pid}",
        ],
        timeout=5,
    )
    output = capsys.readouterr().out
    page = next(json.loads(line) for line in output.splitlines() if '"facts"' in line)
    assert page["memory"]["system"] == "you are the assistant"
    dialogue = [
        item for item in page["memory"]["items"] if item["kind"] != "system"
    ]
    assert [item["content"] for item in dialogue] == ["hello", "model answered"]
    assert [item["kind"] for item in dialogue] == ["user", "model"]
    assert all(item["time"] for item in page["memory"]["items"])
    saved = (tmp_path / "ledger.json").read_text(encoding="utf-8")
    assert "you are the assistant" not in saved
    assert "hello" not in saved



def test_later_prompt_files_stay_and_a_place_inserts(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    first = tmp_path / "one.md"
    second = tmp_path / "two.md"
    first.write_text("alpha", encoding="utf-8")
    second.write_text("beta", encoding="utf-8")
    monkeypatch.setattr("kernel.communication.offers.tool_catalog", lambda: ())
    _book, process = _process(
        tmp_path,
        plugin=_recording_plugin(tmp_path),
        resources=(
            ResourceClaim(kind="network", identity={"channel": "ledger"}),
            ResourceClaim(kind="memory", identity={"scope": "chat"}),
        ),
    )
    pid = process.pid

    def lines():
        yield f"load message {pid} -- {first}"
        yield f"load message {pid} -- {second}"
        yield f"show {pid}"
        first.write_text("alpha-edited", encoding="utf-8")
        yield f"load message {pid} -- {first}"
        yield f"load message {pid} -- 1 {second}"
        yield f"load message {pid} -- question"

    hold(_Service(process), lines=lines(), timeout=5)
    output = capsys.readouterr().out
    page = next(json.loads(line) for line in output.splitlines() if '"facts"' in line)
    assert page["memory"]["system"] == "alpha\n\nbeta"
    sent = _calls(tmp_path)[0]["body"]
    assert _system_text(sent) == "beta\n\nalpha-edited"
    assert [row["content"] for row in _page(sent)["rows"]] == ["question"]
    saved = (tmp_path / "ledger.json").read_text(encoding="utf-8")
    assert "alpha" not in saved
    assert "beta" not in saved


def test_a_reply_slower_than_a_ping_is_kept(tmp_path: Path, capsys) -> None:
    plugin = tmp_path / "slow_plugin.py"
    plugin.write_text(
        "import time\n"
        "def load(kind, body, call_params=None):\n"
        "    time.sleep(1.5)\n"
        "    return f'seen:{body}'\n"
        "async def load_async(kind, body, call_params=None):\n"
        "    return load(kind, body, call_params)\n",
        encoding="utf-8",
    )
    _book, process = _process(tmp_path, plugin=plugin)
    pid = process.pid
    assert hold(_Service(process), lines=[f"load message {pid} -- hello"])
    captured = capsys.readouterr()
    assert "seen:hello" in captured.out
    assert "This process is gone" not in captured.err


def test_a_text_fragment_is_shown_before_the_reply(tmp_path: Path, capsys) -> None:
    plugin = tmp_path / "stream_plugin.py"
    plugin.write_text(
        "import json\n"
        "def load(kind, body, call_params=None):\n"
        "    print(json.dumps({'type': 'text-delta', 'text': 'fragment'}, ensure_ascii=False), flush=True)\n"
        "    return 'translated'\n"
        "async def load_async(kind, body, call_params=None):\n"
        "    return load(kind, body, call_params)\n",
        encoding="utf-8",
    )
    _book, process = _process(tmp_path, plugin=plugin)
    pid = process.pid
    hold(_Service(process), lines=[f"load message {pid} -- hello"], timeout=5)
    output = capsys.readouterr().out
    assert output.index("fragment") < output.index("translated")


def test_an_exited_process_is_still_reported_gone(tmp_path: Path, capsys) -> None:
    crash = tmp_path / "gone_plugin.py"
    crash.write_text(
        "import os\n"
        "def load(kind, body, call_params=None):\n"
        "    os._exit(1)\n"
        "async def load_async(kind, body, call_params=None):\n"
        "    return load(kind, body, call_params)\n",
        encoding="utf-8",
    )
    _book, process = _process(tmp_path, plugin=crash)
    pid = process.pid
    hold(_Service(process), lines=[f"load message {pid} -- hello"], timeout=5)
    assert "This process is gone" in capsys.readouterr().err


def test_a_prompt_file_without_memory_is_refused(tmp_path: Path, capsys) -> None:
    prompt = tmp_path / "note.txt"
    prompt.write_text("you are the assistant", encoding="utf-8")
    _book, process = _process(tmp_path, plugin=_echo(tmp_path))
    pid = process.pid
    hold(
        _Service(process),
        lines=[
            f"load message {pid} -- {prompt}",
            f"load message {pid} -- hello",
        ],
        timeout=5,
    )
    captured = capsys.readouterr()
    assert "This process has no memory" in captured.err
    assert "seen:hello" in captured.out
    assert "you are the assistant" not in captured.out


def test_shared_memory_keeps_system_model_and_tool_output(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    prompt = tmp_path / "note.md"
    prompt.write_text("you are the assistant", encoding="utf-8")
    monkeypatch.setattr("kernel.communication.offers.tool_catalog", lambda: ())
    first, second = _pair(tmp_path, _recording_plugin(tmp_path), shared=("memory",))
    first_id = first.pid
    second_id = second.pid
    hold(
        _Service(first, second),
        lines=[
            f"show {first_id}",
            f"load message {first_id} -- {prompt}",
            f"load message {first_id} -- question",
            f'load tool {first_id} -- {{"query": "lookup"}}',
            f"load message {second_id} -- next turn",
        ],
        timeout=5,
    )
    output = capsys.readouterr().out
    page = next(json.loads(line) for line in output.splitlines() if '"links"' in line)
    assert {"rel": "share", "resource": str(second_id)} in page["links"]
    calls = _calls(tmp_path)
    assert calls[1]["kind"] == "tool"
    assert calls[1]["body"] == {"query": "lookup"}
    assert _system_text(calls[0]["body"]) == "you are the assistant"
    assert [row["content"] for row in _page(calls[0]["body"])["rows"]] == ["question"]
    shared = _page(calls[2]["body"])
    assert _system_text(calls[2]["body"]) == "you are the assistant"
    assert [row["content"] for row in shared["rows"]] == ["next turn"]
    visible = [item.get("kind") for item in shared["_links"].values()]
    assert {"user", "model", "tool"} <= set(visible)
    assert "tool done" not in [row["content"] for row in shared["rows"]]
    saved = (tmp_path / "ledger.json").read_text(encoding="utf-8")
    assert "you are the assistant" not in saved
    assert "model answered" not in saved
    assert "tool done" not in saved


def test_ask_hands_the_task_and_writes_the_result_back(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    monkeypatch.setattr("kernel.communication.offers.tool_catalog", lambda: ())
    sender_prompt = tmp_path / "sender.md"
    sender_prompt.write_text("sender secret", encoding="utf-8")
    receiver_prompt = tmp_path / "receiver.md"
    receiver_prompt.write_text("peer rules", encoding="utf-8")
    sender, receiver = _pair(tmp_path, _recording_plugin(tmp_path))
    sender_id = sender.pid
    receiver_id = receiver.pid

    class _MemoryService(_Service):
        def __init__(self, *processes: object) -> None:
            super().__init__(*processes)
            self.memories: dict[int, list] = {}

        def close(self) -> None:
            from kernel.scheduler.access import memory_contents

            for process in self.processes():
                found = memory_contents(process._pool, process.activation.grants)
                self.memories[process.pid] = [] if found is None else list(found["items"])
            super().close()

    service = _MemoryService(sender, receiver)
    hold(
        service,
        lines=[
            f"load message {sender_id} -- {sender_prompt}",
            f"load message {receiver_id} -- {receiver_prompt}",
            f"ask {receiver_id} -- please handle",
            f"load message {sender_id} -- anything else",
        ],
        timeout=5,
    )
    calls = _calls(tmp_path)
    asked = calls[0]["body"]
    followed = calls[1]["body"]
    assert _system_text(asked) == "peer rules"
    assert [row["content"] for row in _page(asked)["rows"] if row["kind"] == "user"] == ["please handle"]
    assert "sender secret" not in json.dumps(asked, ensure_ascii=False)
    assert _system_text(followed) == "sender secret"
    followed_page = _page(followed)
    assert [row["content"] for row in followed_page["rows"]] == ["anything else"]
    assert "peer rules" not in json.dumps(followed, ensure_ascii=False)
    assert "other" in [item.get("kind") for item in followed_page["_links"].values()]
    receiver_rows = service.memories[receiver_id]
    assert [row["content"] for row in receiver_rows if row["kind"] == "user"] == ["please handle"]
    assert [row["content"] for row in receiver_rows if row["kind"] == "model"] == ["model answered"]
    sender_rows = service.memories[sender_id]
    assert any(row["kind"] == "other" and row["content"] == "model answered" for row in sender_rows)
    assert all(row["content"] != "peer rules" for row in sender_rows)
    _assert_task_then_sleep(_activity_rows(tmp_path, sender_id), receiver_id)
    _assert_task_then_sleep(_activity_rows(tmp_path, receiver_id), sender_id)
    capsys.readouterr()


def test_ask_without_memory_sends_the_task_text(tmp_path: Path, capsys) -> None:
    _sender_book, sender = _process(
        tmp_path,
        plugin=_recording_plugin(tmp_path),
        resources=(
            ResourceClaim(kind="network", identity={"channel": "ledger"}),
            ResourceClaim(kind="memory", identity={"scope": "chat"}),
        ),
    )
    _receiver_book, receiver = _process(tmp_path, plugin=_recording_plugin(tmp_path))
    hold(
        _Service(sender, receiver),
        lines=[f"ask {receiver.pid} -- please handle"],
        timeout=5,
    )
    assert _calls(tmp_path) == [{"kind": "message", "body": "please handle"}]
    capsys.readouterr()


def test_a_tool_string_is_sent_unchanged(tmp_path: Path, capsys) -> None:
    _book, process = _process(
        tmp_path,
        plugin=_recording_plugin(tmp_path),
        resources=(
            ResourceClaim(kind="network", identity={"channel": "ledger"}),
            ResourceClaim(kind="memory", identity={"scope": "chat"}),
        ),
    )
    hold(_Service(process), lines=[f"load tool {process.pid} -- just text"], timeout=5)
    assert _calls(tmp_path) == [{"kind": "tool", "body": "just text"}]
    capsys.readouterr()


def test_show_accepts_an_address() -> None:
    assert _parse_line("show abc message/3-7 artifact/1-2") == (
        "show",
        "abc",
        "message/3-7 artifact/1-2",
    )


def test_load_message_accepts_an_address() -> None:
    from kernel.command.convention import UsageError

    assert _parse_line("load message 12 message/0-1 task/0 -- 总结") == (
        "load",
        "message",
        "总结",
        "12",
        "message/0-1 task/0",
    )
    assert _parse_line("load message 12 -- hello") == (
        "load",
        "message",
        "hello",
        "12",
        "",
    )
    try:
        _parse_line('load tool 12 message/0 -- {"query": "x"}')
    except UsageError:
        return
    raise AssertionError("a tool load does not take an address")


def _page_plugin(tmp_path: Path) -> Path:
    plugin = tmp_path / "page_plugin.py"
    plugin.write_text(
        "import json\n"
        "from pathlib import Path\n"
        f"LOG = Path({str(tmp_path / 'pages.jsonl')!r})\n"
        "def load(kind, body, call_params=None):\n"
        "    page = json.loads(body[-1]['content'])\n"
        "    with LOG.open('a', encoding='utf-8') as handle:\n"
        "        handle.write(json.dumps(page, ensure_ascii=False) + '\\n')\n"
        "    if page.get('read'):\n"
        "        return '已看到原文'\n"
        "    return '记得带伞'\n"
        "async def load_async(kind, body, call_params=None):\n"
        "    return load(kind, body, call_params)\n",
        encoding="utf-8",
    )
    return plugin


class _MemoryWindow:
    def __init__(self, process: object) -> None:
        self._process = process
        self.memory: list[dict] = []

    def processes(self) -> tuple:
        return (self._process,)

    def launch(self, argv: list[str]) -> tuple:
        del argv
        return ()

    def close(self) -> None:
        from kernel.scheduler.access import memory_contents

        process = self._process
        found = memory_contents(process._pool, process.activation.grants)
        self.memory = [] if found is None else list(found["items"])
        process.stop()


def _pages_log(tmp_path: Path) -> list[dict]:
    path = tmp_path / "pages.jsonl"
    if not path.is_file():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_an_address_is_read_on_the_first_page(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setattr("kernel.communication.offers.tool_catalog", lambda: ())
    _book, process = _process(
        tmp_path,
        plugin=_page_plugin(tmp_path),
        resources=(
            ResourceClaim(kind="network", identity={"channel": "ledger"}),
            ResourceClaim(kind="memory", identity={"scope": "chat"}),
        ),
    )
    window = _MemoryWindow(process)
    pid = process.pid
    hold(
        window,
        lines=[
            f"load message {pid} -- 上海今天下雨",
            f"load message {pid} message/0-1 -- 查询北京天气",
        ],
        timeout=5,
    )
    capsys.readouterr()
    pages = _pages_log(tmp_path)
    assert "read" not in pages[0]
    assert [item["address"] for item in pages[1]["read"]] == ["message/0", "message/1"]
    assert [item["content"] for item in pages[1]["read"]] == ["上海今天下雨", "记得带伞"]
    assert any(item["content"] == "查询北京天气" for item in window.memory)


def test_a_bad_address_is_refused_before_the_question(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    monkeypatch.setattr("kernel.communication.offers.tool_catalog", lambda: ())
    _book, process = _process(
        tmp_path,
        plugin=_page_plugin(tmp_path),
        resources=(
            ResourceClaim(kind="network", identity={"channel": "ledger"}),
            ResourceClaim(kind="memory", identity={"scope": "chat"}),
        ),
    )
    window = _MemoryWindow(process)
    pid = process.pid
    hold(
        window,
        lines=[
            f"load message {pid} -- 上海今天下雨",
            f"load message {pid} message/0-9 -- 查询北京天气",
        ],
        timeout=5,
    )
    captured = capsys.readouterr()
    assert len(_pages_log(tmp_path)) == 1
    assert "address space" in captured.err
    assert all(item["content"] != "查询北京天气" for item in window.memory)
