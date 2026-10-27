"""Which links a page offers for tools and models, from fake processes."""

from types import SimpleNamespace

from kernel.communication.offers import command_offers
from kernel.communication.page import CommandOffer


class _Service:
    def __init__(self, *processes, launchable: bool = True) -> None:
        self._items = processes
        if not launchable:
            self.launch = None

    def processes(self) -> tuple:
        return self._items

    def launch(self, argv: list[str]) -> tuple:
        del argv
        return ()


def _process(pid: int, capability: str, *, alive: bool = True):
    return SimpleNamespace(pid=pid, capability=capability, is_alive=alive)


def _offers(monkeypatch, service, asking, busy=()):
    monkeypatch.setattr(
        "kernel.command.process.listen._shown_activity",
        lambda process, record: "with" if process.pid in busy else "sleeping",
    )
    return command_offers(
        service,
        asking,
        catalog=("tools.ddgs", "model.openai_chat_model"),
        schema=lambda name: {"type": "object"},
    )


def test_nothing_up_offers_a_start_for_tools_and_models(monkeypatch) -> None:
    me = _process(100, "model.openai_chat_model")
    offers = _offers(monkeypatch, _Service(me), me)
    assert offers == (
        CommandOffer("start", "model.openai_chat_model"),
        CommandOffer("start", "tools.ddgs"),
    )


def test_a_sleeping_model_is_offered_as_ask_and_a_tool_as_load(monkeypatch) -> None:
    me = _process(100, "model.openai_chat_model")
    other = _process(205, "model.openai_chat_model")
    helper = _process(201, "model.openai_chat_model")
    tool = _process(300, "tools.ddgs")
    offers = _offers(monkeypatch, _Service(me, other, helper, tool), me)
    assert offers == (
        CommandOffer("ask", "model.openai_chat_model", pid=201),
        CommandOffer("tool", "tools.ddgs", pid=300, schema={"type": "object"}),
    )
    assert offers[0].pointer == "ask 201 -- "


def test_a_busy_model_offers_nothing_and_a_dead_one_offers_a_start(monkeypatch) -> None:
    me = _process(100, "tools.ddgs")
    busy = _process(205, "model.openai_chat_model")
    offers = _offers(monkeypatch, _Service(me, busy), me, busy={205})
    assert [offer.relation for offer in offers] == ["start:tools.ddgs"]
    dead = _process(205, "model.openai_chat_model", alive=False)
    offers = _offers(monkeypatch, _Service(me, dead), me)
    assert "start:model.openai_chat_model" in [offer.relation for offer in offers]


def test_read_only_hides_write_tools_even_when_named() -> None:
    me = _process(100, "model.openai_chat_model")
    me.settings = {"permission": "read-only", "capabilities": ["read", "write", "bash"]}
    offers = command_offers(
        _Service(me),
        me,
        catalog=("tools.read", "tools.write", "tools.bash", "model.openai_chat_model"),
        schema=lambda name: {"type": "object"},
    )
    assert [offer.capability for offer in offers] == ["model.openai_chat_model", "tools.read"]


def test_a_window_that_cannot_launch_offers_no_start(monkeypatch) -> None:
    me = _process(100, "model.openai_chat_model")
    tool = _process(300, "tools.ddgs")
    offers = _offers(monkeypatch, _Service(me, tool, launchable=False), me)
    assert [offer.relation for offer in offers] == ["tool:tools.ddgs"]
    nothing = _offers(monkeypatch, _Service(me, launchable=False), me)
    assert nothing == ()


def test_the_asking_model_never_offers_itself(monkeypatch) -> None:
    me = _process(100, "model.openai_chat_model")
    offers = _offers(monkeypatch, _Service(me), me)
    assert all(offer.pid != 100 for offer in offers)
