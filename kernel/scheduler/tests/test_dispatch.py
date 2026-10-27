"""Scheduling lives in one package. The older modules only forward to it."""

import inspect

from kernel.communication.verify import Step
from kernel.hypermedia.link import Link
from kernel.hypermedia.representation import Representation
from kernel.scheduler.requests import ActionCall, Answer, MemoryRead, classify


def test_a_read_an_action_and_an_answer_stay_different() -> None:
    assert isinstance(classify(Step("read", "message/0-2")), MemoryRead)
    assert isinstance(classify(Step("answer", "answer", "ok")), Answer)
    action = classify(Step("tool", "load tool 7 -- ", pid=7, capability="tools.ddgs"))
    assert isinstance(action, ActionCall)
    assert action.way == "tool"
    assert action.pid == 7


def test_the_model_loop_and_the_route_have_one_home() -> None:
    import importlib.util

    import kernel.load_balancing.route as balancing
    import kernel.scheduler.model_turn as turns
    import kernel.scheduler.route as routing
    import kernel.scheduler.threads as threads
    import kernel.thread.runtime as runtime

    assert importlib.util.find_spec("kernel.communication.follow") is None
    assert balancing.route is routing.route
    assert "def route" not in inspect.getsource(balancing)
    assert "while True" in inspect.getsource(turns)
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
