"""Opening a service asks the existing launcher once per member."""

from __future__ import annotations

import pytest

from kernel.services.host import ServiceHost, launch_session
from kernel.services.spec import LaunchOptions, ServiceSpec
from kernel.services.tests.fakes import Reconciler, Store, load_declaration


def _host(reconciler: Reconciler, store: Store) -> ServiceHost:
    return ServiceHost(
        open_store=lambda _locator=None: store,
        pool=lambda opened: opened,
        reconciler=lambda _pool: reconciler,
        load_declaration=load_declaration,
    )


def test_a_capability_session_starts_one_process_and_close_stops_it() -> None:
    reconciler = Reconciler(None)
    store = Store()
    service = launch_session(
        ServiceSpec("capability", members=("tools.bash",)),
        LaunchOptions(store_locator="memory:"),
        _host(reconciler, store),
    )
    try:
        assert reconciler.launched == ["tools.bash"]
        assert [member.role for member in service.members()] == ["capability"]
    finally:
        service.close()
    assert store.closed is True
    assert service.members()[0].alive is False


def test_a_later_member_failing_stops_the_ones_already_open() -> None:
    reconciler = Reconciler(None)
    reconciler.fail_on.add("tools.mcp_config")
    store = Store()
    with pytest.raises(RuntimeError, match="tools.mcp_config"):
        launch_session(
            ServiceSpec("mcp", members=("tools.mcp_tool_manager", "tools.mcp_config")),
            host=_host(reconciler, store),
        )
    assert store.closed is True
    assert reconciler.opened[0].stopped is True
