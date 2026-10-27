"""One question runs until the model answers: start, search, then answer."""

import json
from pathlib import Path

from kernel.command.process.listen import _open_programs, hold
from kernel.communication.address import memory_contents
from kernel.process.declaration import ProcessDeclaration, ResourceClaim
from kernel.process.ledger import ProcessLedger
from kernel.process.process_creat.instances import CapabilityDefinition
from kernel.process.reconcile import ProcessReconciler
from kernel.process.resource_record import ProcessResourceBook
from kernel.resource.lease import ResourceLeaseManager
from kernel.resource.pool import ResourcePool

_ADAPTER = Path(__file__).resolve().parents[3] / "capability" / "process_adapter.py"
_NETWORK = ResourceClaim(kind="network", identity={"channel": "ledger"})
_SCHEMA = {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}


class _Batch:
    def __init__(self, processes: tuple) -> None:
        self._only = processes

    def processes(self) -> tuple:
        return self._only


class _Window:
    """A window that can start processes, like the clerk, with a fake tool plugin."""

    def __init__(self, pool, book, tool: Path) -> None:
        self._pool = pool
        self._book = book
        self._tool = tool
        self.plugins: dict[str, Path] = {}
        self._items: list = []
        self.started: list[list[str]] = []
        self.memory: list[dict] = []
        self.memories: dict[int, list] = {}

    def processes(self) -> tuple:
        return tuple(self._items)

    def close(self) -> None:
        self.memories = {}
        for process in self._items:
            grants = getattr(getattr(process, "activation", None), "grants", ()) or ()
            found = memory_contents(getattr(process, "_pool", None), grants)
            self.memories[process.pid] = [] if found is None else list(found["items"])
        self.memory = self.memories[self._items[0].pid]
        for process in self._items:
            process.stop()

    def launch(self, argv: list[str]) -> tuple:
        from kernel.command.process.start import launch_options, parse_start_options
        from kernel.process.declaration import append_chosen, stamp_memory_space

        parsed = parse_start_options(argv)
        options = launch_options(parsed)
        capability = parsed[0]
        process = ProcessReconciler(self._pool, self._book).start(
            stamp_memory_space(
                append_chosen(
                    ProcessDeclaration(capability=capability, resources=(_NETWORK,)),
                    options.chosen,
                ),
                parsed[1],
            ),
            definition=CapabilityDefinition(
                instance_id=capability,
                module_paths=(str(self.plugins.get(capability, self._tool)), str(_ADAPTER)),
            ),
        )
        _open_programs(_Batch((process,)))
        self._items.append(process)
        self.started.append(list(argv))
        print(f"pid={process.pid} capability={capability}", flush=True)
        return (process,)


def _model_plugin(tmp_path: Path, first: str = "") -> Path:
    plugin = tmp_path / "page_model.py"
    plugin.write_text(
        "import json\n"
        "from pathlib import Path\n"
        f"LOG = Path({str(tmp_path / 'pages.jsonl')!r})\n"
        f"FIRST = {first!r}\n"
        "def load(kind, body, call_params=None):\n"
        "    page = json.loads(body[-1]['content'])\n"
        "    with LOG.open('a', encoding='utf-8') as handle:\n"
        "        handle.write(json.dumps(page, ensure_ascii=False) + '\\n')\n"
        "    if FIRST and page['state'] == 'asked':\n"
        "        return FIRST\n"
        "    tool = page['_links'].get('tool:tools.fake')\n"
        "    if tool is None:\n"
        "        return 'process start tools.fake'\n"
        "    if not any(row['kind'] == 'tool' for row in page['rows']):\n"
        "        return json.dumps({'state': 'continue', 'pointer': tool['pointer'],\n"
        "                           'body': {'query': 'the movie'}}, ensure_ascii=False)\n"
        "    return 'The movie opens in 2027. Source: Avengers, https://example.com'\n"
        "async def load_async(kind, body, call_params=None):\n"
        "    return load(kind, body, call_params)\n",
        encoding="utf-8",
    )
    return plugin


def _tool_plugin(tmp_path: Path) -> Path:
    plugin = tmp_path / "fake_search.py"
    plugin.write_text(
        "import json\n"
        "def load(kind, body, call_params=None):\n"
        "    if kind != 'tool':\n"
        "        raise ValueError('only accepts tool')\n"
        "    web = [{'title': 'Avengers', 'url': 'https://example.com', 'query': body['query']}]\n"
        "    return json.dumps({'success': True, 'data': {'web': web}}, ensure_ascii=False)\n"
        "async def load_async(kind, body, call_params=None):\n"
        "    return load(kind, body, call_params)\n",
        encoding="utf-8",
    )
    return plugin


def _window(tmp_path: Path, monkeypatch, first: str = ""):
    monkeypatch.setattr("kernel.communication.offers.tool_catalog", lambda: ("tools.fake",))
    monkeypatch.setattr("kernel.communication.offers.tool_schema", lambda name: dict(_SCHEMA))
    pool = ResourcePool(ResourceLeaseManager())
    book = ProcessResourceBook(ProcessLedger(tmp_path / "ledger.json"))
    window = _Window(pool, book, _tool_plugin(tmp_path))
    model = ProcessReconciler(pool, book).start(
        ProcessDeclaration(
            capability="model.fake",
            resources=(_NETWORK, ResourceClaim(kind="memory", identity={"scope": "search"})),
        ),
        definition=CapabilityDefinition(
            instance_id="model.fake",
            module_paths=(str(_model_plugin(tmp_path, first)), str(_ADAPTER)),
        ),
    )
    window._items.append(model)
    return window, model


def _pages(tmp_path: Path) -> list[dict]:
    path = tmp_path / "pages.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_one_question_starts_searches_and_answers(tmp_path: Path, monkeypatch, capsys) -> None:
    window, model = _window(tmp_path, monkeypatch)
    hold(window, lines=[f"load message {model.pid} -- when does the movie open"], timeout=5)
    output = capsys.readouterr().out

    pages = _pages(tmp_path)
    assert [page["state"] for page in pages] == ["asked", "resulted", "resulted"]
    assert "start:tools.fake" in pages[0]["_links"]
    assert "tool:tools.fake" not in pages[0]["_links"]
    tool_pid = pages[1]["_links"]["tool:tools.fake"]["pid"]
    assert pages[1]["_links"]["tool:tools.fake"]["pointer"] == f"load tool {tool_pid} -- "
    assert any(row["content"].startswith(f"pid={tool_pid}") for row in pages[1]["rows"])
    assert any(row["kind"] == "tool" and "Avengers" in row["content"] for row in pages[2]["rows"])

    states = [row.get("state") for row in window.memory if row["kind"] != "system"]
    assert states == ["asked", "continue", "resulted", "continue", "resulted", "answered"]
    assert window.started == [["tools.fake"]]
    assert "The movie opens in 2027" in output
    assert output.count('"type": "done"') == 1


def test_a_refused_step_is_explained_and_nothing_runs(tmp_path: Path, monkeypatch, capsys) -> None:
    window, model = _window(tmp_path, monkeypatch, first='load tool 99999 -- {"query": "the movie"}')
    hold(window, lines=[f"load message {model.pid} -- when does the movie open"], timeout=5)
    captured = capsys.readouterr()

    pages = _pages(tmp_path)
    assert pages[1]["state"] == "rejected"
    refused = json.loads(pages[1]["rows"][-1]["content"])
    assert refused["field"] == "pointer"
    assert "99999" in refused["error"]
    assert "process start tools.fake" in refused["allowed"]
    assert "99999" in captured.err
    assert window.started == [["tools.fake"]]
    assert "The movie opens in 2027" in captured.out


def _reading_model_plugin(tmp_path: Path) -> Path:
    plugin = tmp_path / "reading_model.py"
    plugin.write_text(
        "import json\n"
        "from pathlib import Path\n"
        f"LOG = Path({str(tmp_path / 'pages.jsonl')!r})\n"
        "def load(kind, body, call_params=None):\n"
        "    page = json.loads(body[-1]['content'])\n"
        "    with LOG.open('a', encoding='utf-8') as handle:\n"
        "        handle.write(json.dumps(page, ensure_ascii=False) + '\\n')\n"
        "    if page.get('read'):\n"
        "        return 'I have seen the old messages.'\n"
        "    return json.dumps({'state': 'continue', 'pointer': 'message/0'}, ensure_ascii=False)\n"
        "async def load_async(kind, body, call_params=None):\n"
        "    return load(kind, body, call_params)\n",
        encoding="utf-8",
    )
    return plugin


def test_a_read_is_journaled_and_stays_out_of_memory(tmp_path: Path, monkeypatch, capsys) -> None:
    from kernel.trace.journal import Journal, journal_beside

    monkeypatch.setattr("kernel.communication.offers.tool_catalog", lambda: ())
    pool = ResourcePool(ResourceLeaseManager())
    book = ProcessResourceBook(ProcessLedger(tmp_path / "ledger.json"))
    window = _Window(pool, book, _tool_plugin(tmp_path))
    model = ProcessReconciler(pool, book).start(
        ProcessDeclaration(
            capability="model.fake",
            resources=(_NETWORK, ResourceClaim(kind="memory", identity={"scope": "search"})),
        ),
        definition=CapabilityDefinition(
            instance_id="model.fake",
            module_paths=(str(_reading_model_plugin(tmp_path)), str(_ADAPTER)),
        ),
    )
    window._items.append(model)
    hold(window, lines=[f"load message {model.pid} -- look at what was said before"], timeout=5)
    capsys.readouterr()

    pages = _pages(tmp_path)
    assert pages[1]["read"][0]["address"] == "message/0"
    assert pages[1]["read"][0]["time"]
    assert pages[0]["rows"][0]["time"] == pages[1]["read"][0]["time"]
    assert pages[0]["_links"]["message/0"]["time"] == pages[1]["read"][0]["time"]

    rows = Journal(journal_beside(tmp_path / "ledger.json")).rows()
    reads = [row for row in rows if row.get("step") == "read"]
    assert len(reads) == 1
    assert reads[0]["pid"] == model.pid
    assert "message/0" in reads[0]["text"]
    assert reads[0]["state"] == "asked"
    assert all("message/0" not in str(row.get("content") or "") for row in window.memory)
    assert any(row["content"] == "I have seen the old messages." for row in window.memory)


def _asking_model_plugin(tmp_path: Path) -> Path:
    plugin = tmp_path / "asking_model.py"
    plugin.write_text(
        "import json\n"
        "from pathlib import Path\n"
        f"LOG = Path({str(tmp_path / 'pages.jsonl')!r})\n"
        "def load(kind, body, call_params=None):\n"
        "    page = json.loads(body[-1]['content'])\n"
        "    with LOG.open('a', encoding='utf-8') as handle:\n"
        "        handle.write(json.dumps(page, ensure_ascii=False) + '\\n')\n"
        "    ask = page['_links'].get('ask:model.helper')\n"
        "    if ask is None:\n"
        "        return 'process start model.helper --with memory=helper'\n"
        "    if not any(row['content'].startswith('red-black tree') for row in page['rows']):\n"
        "        return ask['pointer'] + 'write a red-black tree'\n"
        "    return 'The helper finished the red-black tree.'\n"
        "async def load_async(kind, body, call_params=None):\n"
        "    return load(kind, body, call_params)\n",
        encoding="utf-8",
    )
    return plugin


def _helper_plugin(tmp_path: Path) -> Path:
    plugin = tmp_path / "helper_model.py"
    plugin.write_text(
        "import json\n"
        "def load(kind, body, call_params=None):\n"
        "    if kind != 'message':\n"
        "        raise ValueError('only accepts message')\n"
        "    page = json.loads(body[-1]['content'])\n"
        "    task = next(row['content'] for row in page['rows'] if row['kind'] == 'user')\n"
        "    return 'red-black tree: received \"' + task + '\"'\n"
        "async def load_async(kind, body, call_params=None):\n"
        "    return load(kind, body, call_params)\n",
        encoding="utf-8",
    )
    return plugin


def test_a_model_starts_another_model_and_asks_it(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setattr("kernel.communication.offers.tool_catalog", lambda: ("model.helper",))
    pool = ResourcePool(ResourceLeaseManager())
    book = ProcessResourceBook(ProcessLedger(tmp_path / "ledger.json"))
    window = _Window(pool, book, _tool_plugin(tmp_path))
    window.plugins["model.helper"] = _helper_plugin(tmp_path)
    model = ProcessReconciler(pool, book).start(
        ProcessDeclaration(
            capability="model.fake",
            resources=(_NETWORK, ResourceClaim(kind="memory", identity={"scope": "code"})),
        ),
        definition=CapabilityDefinition(
            instance_id="model.fake",
            module_paths=(str(_asking_model_plugin(tmp_path)), str(_ADAPTER)),
        ),
    )
    window._items.append(model)
    hold(window, lines=[f"load message {model.pid} -- find a helper to write a red-black tree"], timeout=5)
    output = capsys.readouterr().out

    pages = _pages(tmp_path)
    assert [page["state"] for page in pages] == ["asked", "resulted", "resulted"]
    assert "start:model.helper" in pages[0]["_links"]
    helper_pid = pages[1]["_links"]["ask:model.helper"]["pid"]
    assert "start:model.helper" not in pages[1]["_links"]
    assert pages[1]["_links"]["ask:model.helper"]["pointer"] == f"ask {helper_pid} -- "
    handed = [row for row in window.memory if row["content"].startswith("red-black tree")]
    assert len(handed) == 1
    assert handed[0]["kind"] == "other" and "write a red-black tree" in handed[0]["content"]
    helper_rows = window.memories[helper_pid]
    assert [row["content"] for row in helper_rows if row["kind"] == "user"] == ["write a red-black tree"]
    assert [row["content"] for row in helper_rows if row["kind"] == "model"] == [
        'red-black tree: received "write a red-black tree"'
    ]
    assert handed[0]["address"].startswith("task/")
    assert window.started == [["model.helper", "--with", "memory=helper"]]
    assert "The helper finished the red-black tree" in output


def test_memory_uses_a_page_even_when_the_window_cannot_launch(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    from kernel.command.process.listen import _pages as pages_mode

    window, model = _window(tmp_path, monkeypatch)
    assert pages_mode(window, model)

    class _Plain:
        launch = None

    assert pages_mode(_Plain(), model)
    window.close()
    capsys.readouterr()


def test_without_launch_a_sleeping_tool_stays_callable(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    window, model = _window(tmp_path, monkeypatch)
    assert window.launch(["tools.fake"])
    window.launch = None
    hold(window, lines=[f"load message {model.pid} -- when does the movie open"], timeout=5)
    capsys.readouterr()
    pages = _pages(tmp_path)
    assert "start:tools.fake" not in pages[0]["_links"]
    assert "tool:tools.fake" in pages[0]["_links"]
    assert any(row["kind"] == "tool" and "Avengers" in row["content"] for row in pages[-1]["rows"])
    assert window.started == [["tools.fake"]]


def test_without_launch_a_start_command_is_refused(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    plugin = tmp_path / "refusing_model.py"
    plugin.write_text(
        "import json\n"
        "from pathlib import Path\n"
        f"LOG = Path({str(tmp_path / 'pages.jsonl')!r})\n"
        "def load(kind, body, call_params=None):\n"
        "    page = json.loads(body[-1]['content'])\n"
        "    with LOG.open('a', encoding='utf-8') as handle:\n"
        "        handle.write(json.dumps(page, ensure_ascii=False) + '\\n')\n"
        "    if page['state'] == 'asked':\n"
        "        return 'process start tools.fake'\n"
        "    return 'answered without starting'\n"
        "async def load_async(kind, body, call_params=None):\n"
        "    return load(kind, body, call_params)\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("kernel.communication.offers.tool_catalog", lambda: ("tools.fake",))
    monkeypatch.setattr("kernel.communication.offers.tool_schema", lambda name: dict(_SCHEMA))
    pool = ResourcePool(ResourceLeaseManager())
    book = ProcessResourceBook(ProcessLedger(tmp_path / "ledger.json"))
    window = _Window(pool, book, _tool_plugin(tmp_path))
    model = ProcessReconciler(pool, book).start(
        ProcessDeclaration(
            capability="model.fake",
            resources=(_NETWORK, ResourceClaim(kind="memory", identity={"scope": "search"})),
        ),
        definition=CapabilityDefinition(
            instance_id="model.fake",
            module_paths=(str(plugin), str(_ADAPTER)),
        ),
    )
    window._items.append(model)
    window.launch = None
    hold(window, lines=[f"load message {model.pid} -- start something"], timeout=5)
    captured = capsys.readouterr()
    pages = _pages(tmp_path)
    assert "start:tools.fake" not in pages[0]["_links"]
    assert pages[1]["state"] == "rejected"
    assert window.started == []
    assert "answered without starting" in captured.out


def test_a_start_step_without_launch_is_refused_in_the_turn(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    from kernel.communication.channel import MemoryChannel
    from kernel.hypermedia.representation import Representation
    from kernel.scheduler.model_turn import _run
    from kernel.scheduler.requests import ActionCall

    window, model = _window(tmp_path, monkeypatch)
    window.launch = None
    try:
        _run(
            window,
            model,
            MemoryChannel(model._pool),
            ActionCall(
                "start",
                "process start tools.fake",
                argv=("tools.fake",),
                capability="tools.fake",
            ),
            Representation({"seq": 0}, ()),
        )
        rows = memory_contents(model._pool, model.activation.grants)["items"]
        refused = [row for row in rows if row.get("state") == "rejected"]
        assert refused
        assert "cannot start" in refused[-1]["content"]
        assert window.started == []
    finally:
        window.close()
    capsys.readouterr()
