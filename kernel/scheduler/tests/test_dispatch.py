"""Scheduling routes requests and admits threads. The model loop lives with the capability."""

import inspect

from kernel.hypermedia.link import Link
from kernel.hypermedia.representation import Representation


def test_the_route_lives_with_the_scheduler() -> None:
    import kernel.load_balancing.route as balancing
    import kernel.scheduler.route as routing
    import kernel.scheduler.threads as threads
    import kernel.thread.runtime as runtime

    assert balancing.route is routing.route
    assert "def route" not in inspect.getsource(balancing)
    assert "def route" in inspect.getsource(routing)
    assert "while not stopping" not in inspect.getsource(runtime.ThreadRuntime.run)
    assert "while not stopping" in inspect.getsource(threads.run_runtime)


def test_link_selection_does_not_run_a_turn() -> None:
    import kernel.hypermedia.follow as follow
    import kernel.hypermedia.link_selector as selector

    assert follow.follow_selected is selector.select_links
    source = inspect.getsource(selector)
    assert "launch" not in source
    assert "memory_contents" not in source
    page = Representation(
        {},
        (Link("message/0", "message/0", "abc"), Link("closed", "message/1", "")),
    )
    chosen = selector.select_links(page, ["message/0", "message/1"])
    assert [link.resource_id for link in chosen.followed] == ["message/0"]
    assert [link.resource_id for link in chosen.left] == ["message/1"]
