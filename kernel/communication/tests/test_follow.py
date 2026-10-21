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
        self._items: list = []
        self.started: list[list[str]] = []
        self.memory: list[dict] = []

    def processes(self) -> tuple:
        return tuple(self._items)

    def close(self) -> None:
        model = self._items[0]
        self.memory = memory_contents(model._pool, model.activation.grants)["items"]
        for process in self._items:
            process.stop()

    def launch(self, argv: list[str]) -> tuple:
        from kernel.command.process.start import parse_start_options

        capability = parse_start_options(argv)[0]
        process = ProcessReconciler(self._pool, self._book).start(
            ProcessDeclaration(capability=capability, resources=(_NETWORK,)),
            definition=CapabilityDefinition(
                instance_id=capability,
                module_paths=(str(self._tool), str(_ADAPTER)),
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
        "                           'body': {'query': '复联五'}}, ensure_ascii=False)\n"
        "    return '复联五在 2027 年上映。来源：Avengers，https://example.com'\n"
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
        "        raise ValueError('只接 tool')\n"
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
    hold(window, lines=[f"load message {model.pid} -- 复联五什么时候上映"], timeout=5)
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
    assert "复联五在 2027 年上映" in output
    assert output.count('"type": "done"') == 1


def test_a_refused_step_is_explained_and_nothing_runs(tmp_path: Path, monkeypatch, capsys) -> None:
    window, model = _window(tmp_path, monkeypatch, first='load tool 99999 -- {"query": "复联五"}')
    hold(window, lines=[f"load message {model.pid} -- 复联五什么时候上映"], timeout=5)
    captured = capsys.readouterr()

    pages = _pages(tmp_path)
    assert pages[1]["state"] == "rejected"
    refused = json.loads(pages[1]["rows"][-1]["content"])
    assert refused["field"] == "pointer"
    assert "99999" in refused["error"]
    assert "process start tools.fake" in refused["allowed"]
    assert "99999" in captured.err
    assert window.started == [["tools.fake"]]
    assert "复联五在 2027 年上映" in captured.out


def test_a_window_that_cannot_start_keeps_the_old_conversation(tmp_path: Path, monkeypatch, capsys) -> None:
    from kernel.command.process.listen import _pages as pages_mode

    window, model = _window(tmp_path, monkeypatch)
    assert pages_mode(window, model)

    class _Plain:
        launch = None

    assert not pages_mode(_Plain(), model)
    window.close()
    capsys.readouterr()
