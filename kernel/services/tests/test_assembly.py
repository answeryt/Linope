"""Opening a service asks the existing launcher once per member."""

from __future__ import annotations

import pytest

from kernel.services.host import ServiceHost, open_service
from kernel.services.spec import LaunchOptions, ServiceSpec
from kernel.services.tests.fakes import Reconciler, Store, load_declaration


def _host(reconciler: Reconciler, store: Store) -> ServiceHost:
    return ServiceHost(
        open_store=lambda _locator=None: store,
        pool=lambda opened: opened,
        reconciler=lambda _pool: reconciler,
        load_declaration=load_declaration,
    )


def test_an_agent_opens_one_peer_process_per_member() -> None:
    reconciler = Reconciler(None)
    store = Store()
    service = open_service(
        ServiceSpec(
            "agent",
            members=("model.openai_chat_model", "tools.bash"),
            options={"share": True},
        ),
        LaunchOptions(store_locator="memory:"),
        _host(reconciler, store),
    )
    try:
        assert reconciler.launched == ["model.openai_chat_model", "tools.bash"]
        assert [member.role for member in service.members()] == ["model", "tool:bash"]
        assert store.shared == ("model.openai_chat_model", "tools.bash")
    finally:
        service.close()
    assert store.closed is True
    assert service.members()[0].alive is False


def test_sharing_adds_names_without_clearing_the_existing_choice() -> None:
    store = Store(shared=("tools.read",))
    service = open_service(
        ServiceSpec("agent", members=("model.a", "tools.bash"), options={"share": True}),
        host=_host(Reconciler(None), store),
    )
    service.close()
    assert store.shared == ("tools.read", "model.a", "tools.bash")


def test_a_later_member_failing_stops_the_ones_already_open() -> None:
    reconciler = Reconciler(None)
    reconciler.fail_on.add("tools.bash")
    store = Store()
    with pytest.raises(RuntimeError, match="tools.bash"):
        open_service(
            ServiceSpec("agent", members=("model.a", "tools.bash")),
            host=_host(reconciler, store),
        )
    assert store.closed is True
    assert reconciler.launched == ["model.a", "tools.bash"]
    assert reconciler.opened[0].stopped is True
