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
        "        return '工具出了'\n"
        "    return '模型答了'\n"
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
    assert hold(service, lines=[f"load message {pid} -- 你好"], timeout=5)
    assert service.closed
    output = capsys.readouterr().out
    assert "seen:你好" in output
    assert '"type": "done"' in output


def test_tool_body_stays_a_mapping(tmp_path: Path, capsys) -> None:
    _book, process = _process(tmp_path, plugin=_echo(tmp_path))
    pid = process.pid
    hold(_Service(process), lines=[f'load tool {pid} -- {{"query": "分布式"}}'], timeout=5)
    output = capsys.readouterr().out
    assert '"kind": "tool"' in output
    assert "分布式" in output


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
    hold(_Service(process), lines=["load message -- 你好"], timeout=5)
    assert "完整进程号" in capsys.readouterr().err


def test_a_short_id_is_refused(tmp_path: Path, capsys) -> None:
    _book, process = _process(tmp_path)
    pid = str(process.pid)
    hold(_Service(process), lines=[f"load message {pid[:-1]} -- 你好"], timeout=5)
    assert pid in capsys.readouterr().err


def test_full_id_reaches_only_that_process(tmp_path: Path, capsys) -> None:
    _book, first = _process(tmp_path, plugin=_echo(tmp_path))
    _other, second = _process(tmp_path, plugin=_echo(tmp_path))
    hold(
        _Service(first, second),
        lines=[f"load message {first.pid} -- 你好"],
        timeout=5,
    )
    output = capsys.readouterr().out
    assert "seen:你好" in output
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
            f'load tool {pid} -- {{"query": "分布式"}}',
            f'load tool {pid} -- {{"query": "第二条"}}',
        ],
        timeout=5,
    )
    output = capsys.readouterr().out
    assert "分布式" in output
    assert "第二条" not in output


def test_ping_does_not_finish_a_once_process(tmp_path: Path, capsys) -> None:
    _book, process = _process(tmp_path, plugin=_echo(tmp_path))
    pid = process.pid
    hold(
        _Service(process),
        once=True,
        lines=[
            f"ping {pid}",
            f"load message {pid} -- 你好",
            f"load message {pid} -- 第二条",
        ],
        timeout=5,
    )
    output = capsys.readouterr().out
    assert "seen:你好" in output
    assert "第二条" not in output


def test_a_wrong_id_does_not_finish_a_once_process(tmp_path: Path, capsys) -> None:
    _book, process = _process(tmp_path, plugin=_echo(tmp_path))
    pid = process.pid
    hold(
        _Service(process),
        once=True,
        lines=[
            "load message missing -- 你好",
            f"load message {pid} -- 你好",
        ],
        timeout=5,
    )
    captured = capsys.readouterr()
    assert "seen:你好" in captured.out
    assert str(pid) in captured.err


def test_publish_text_uses_the_terminal_event(capsys) -> None:
    publish_text("你好")
    assert json.loads(capsys.readouterr().out) == {"type": "text-delta", "text": "你好"}


def test_same_window_can_list_show_and_trace(tmp_path: Path, capsys) -> None:
    _book, process = _process(tmp_path, plugin=_echo(tmp_path))
    pid = process.pid
    hold(
        _Service(process),
        lines=[
            "list",
            f"show {pid}",
            f"load message {pid} -- 你好",
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
            f"load message {first.pid} -- 炸",
            f"load message {second.pid} -- 你好",
        ],
        timeout=5,
    )
    captured = capsys.readouterr()
    assert "seen:你好" in captured.out
    assert "没了" in captured.err or "这个进程" in captured.err


def test_a_prompt_file_is_kept_in_memory_and_sent_with_the_next_question(
    tmp_path: Path, capsys
) -> None:
    prompt = tmp_path / "note.md"
    prompt.write_text("你是助手", encoding="utf-8")
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
            f"load message {pid} -- 你好",
            f"load message {pid} -- 再见",
        ],
        timeout=5,
    )
    calls = _calls(tmp_path)
    first = _contents(calls[0]["body"])
    second = _contents(calls[1]["body"])
    assert first == ["你是助手", "你好"]
    assert second == ["你是助手", "你好", "模型答了", "再见"]
    saved = (tmp_path / "ledger.json").read_text(encoding="utf-8")
    assert "你是助手" not in saved
    assert "模型答了" not in saved
    capsys.readouterr()


def test_show_prints_the_words_kept_in_memory(tmp_path: Path, capsys) -> None:
    prompt = tmp_path / "note.md"
    prompt.write_text("你是助手", encoding="utf-8")
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
            f"load message {pid} -- 你好",
            f"show {pid}",
        ],
        timeout=5,
    )
    output = capsys.readouterr().out
    page = next(json.loads(line) for line in output.splitlines() if '"facts"' in line)
    assert page["memory"]["system"] == "你是助手"
    dialogue = [
        item for item in page["memory"]["items"] if item["kind"] != "system"
    ]
    assert [item["content"] for item in dialogue] == ["你好", "模型答了"]
    assert [item["kind"] for item in dialogue] == ["user", "model"]
    assert all(item["time"] for item in page["memory"]["items"])
    saved = (tmp_path / "ledger.json").read_text(encoding="utf-8")
    assert "你是助手" not in saved
    assert "你好" not in saved



def test_later_prompt_files_stay_and_a_place_inserts(tmp_path: Path, capsys) -> None:
    first = tmp_path / "one.md"
    second = tmp_path / "two.md"
    first.write_text("甲", encoding="utf-8")
    second.write_text("乙", encoding="utf-8")
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
        first.write_text("甲改", encoding="utf-8")
        yield f"load message {pid} -- {first}"
        yield f"load message {pid} -- 1 {second}"
        yield f"load message {pid} -- 问"

    hold(_Service(process), lines=lines(), timeout=5)
    output = capsys.readouterr().out
    page = next(json.loads(line) for line in output.splitlines() if '"facts"' in line)
    assert page["memory"]["system"] == "甲\n\n乙"
    assert _contents(_calls(tmp_path)[0]["body"])[0] == "乙\n\n甲改"
    saved = (tmp_path / "ledger.json").read_text(encoding="utf-8")
    assert "甲" not in saved
    assert "乙" not in saved


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
    assert hold(_Service(process), lines=[f"load message {pid} -- 你好"])
    captured = capsys.readouterr()
    assert "seen:你好" in captured.out
    assert "这个进程没了" not in captured.err


def test_a_text_fragment_is_shown_before_the_reply(tmp_path: Path, capsys) -> None:
    plugin = tmp_path / "stream_plugin.py"
    plugin.write_text(
        "import json\n"
        "def load(kind, body, call_params=None):\n"
        "    print(json.dumps({'type': 'text-delta', 'text': '片段'}, ensure_ascii=False), flush=True)\n"
        "    return '译完'\n"
        "async def load_async(kind, body, call_params=None):\n"
        "    return load(kind, body, call_params)\n",
        encoding="utf-8",
    )
    _book, process = _process(tmp_path, plugin=plugin)
    pid = process.pid
    hold(_Service(process), lines=[f"load message {pid} -- 你好"], timeout=5)
    output = capsys.readouterr().out
    assert output.index("片段") < output.index("译完")


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
    hold(_Service(process), lines=[f"load message {pid} -- 你好"], timeout=5)
    assert "这个进程没了" in capsys.readouterr().err


def test_a_prompt_file_without_memory_is_refused(tmp_path: Path, capsys) -> None:
    prompt = tmp_path / "note.txt"
    prompt.write_text("你是助手", encoding="utf-8")
    _book, process = _process(tmp_path, plugin=_echo(tmp_path))
    pid = process.pid
    hold(
        _Service(process),
        lines=[
            f"load message {pid} -- {prompt}",
            f"load message {pid} -- 你好",
        ],
        timeout=5,
    )
    captured = capsys.readouterr()
    assert "这个进程没有记忆" in captured.err
    assert "seen:你好" in captured.out
    assert "你是助手" not in captured.out


def test_shared_memory_keeps_system_model_and_tool_output(tmp_path: Path, capsys) -> None:
    prompt = tmp_path / "note.md"
    prompt.write_text("你是助手", encoding="utf-8")
    first, second = _pair(tmp_path, _recording_plugin(tmp_path), shared=("memory",))
    first_id = first.pid
    second_id = second.pid
    hold(
        _Service(first, second),
        lines=[
            f"show {first_id}",
            f"load message {first_id} -- {prompt}",
            f"load message {first_id} -- 问题",
            f'load tool {first_id} -- {{"query": "查"}}',
            f"load message {second_id} -- 下一次",
        ],
        timeout=5,
    )
    output = capsys.readouterr().out
    page = next(json.loads(line) for line in output.splitlines() if '"links"' in line)
    assert {"rel": "share", "resource": str(second_id)} in page["links"]
    calls = _calls(tmp_path)
    assert calls[1]["kind"] == "tool"
    assert calls[1]["body"] == {"query": "查"}
    assert _contents(calls[2]["body"]) == ["你是助手", "问题", "模型答了", "工具出了", "下一次"]
    saved = (tmp_path / "ledger.json").read_text(encoding="utf-8")
    assert "你是助手" not in saved
    assert "模型答了" not in saved
    assert "工具出了" not in saved


def test_ask_hands_the_task_and_writes_the_result_back(tmp_path: Path, capsys) -> None:
    sender_prompt = tmp_path / "sender.md"
    sender_prompt.write_text("发送方秘密", encoding="utf-8")
    receiver_prompt = tmp_path / "receiver.md"
    receiver_prompt.write_text("对方规矩", encoding="utf-8")
    sender, receiver = _pair(tmp_path, _recording_plugin(tmp_path))
    sender_id = sender.pid
    receiver_id = receiver.pid
    hold(
        _Service(sender, receiver),
        lines=[
            f"load message {sender_id} -- {sender_prompt}",
            f"load message {receiver_id} -- {receiver_prompt}",
            f"ask {receiver_id} -- 请处理",
            f"load message {sender_id} -- 还有吗",
        ],
        timeout=5,
    )
    calls = _calls(tmp_path)
    asked = _contents(calls[0]["body"])
    followed = _contents(calls[1]["body"])
    assert asked == ["对方规矩", "请处理"]
    assert "发送方秘密" not in asked
    assert followed == ["发送方秘密", "模型答了", "还有吗"]
    assert "对方规矩" not in followed
    _assert_task_then_sleep(_activity_rows(tmp_path, sender_id), receiver_id)
    _assert_task_then_sleep(_activity_rows(tmp_path, receiver_id), sender_id)
    capsys.readouterr()


def test_show_accepts_an_address() -> None:
    assert _parse_line("show abc message/3-7 artifact/1-2") == (
        "show",
        "abc",
        "message/3-7 artifact/1-2",
    )
