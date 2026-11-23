from types import SimpleNamespace

import pytest

from kernel.command.model import run
from kernel.scheduler.model_scheduler.cores import Cores


def test_model_cores_command_resizes_an_idle_runtime() -> None:
    cores = Cores()
    runtime = SimpleNamespace(
        drive=SimpleNamespace(cores=cores, busy=lambda: False),
    )

    result = run(["cores", "2"], runtime=runtime)

    assert result["cores"] == 2


def test_model_cores_command_rejects_a_live_turn() -> None:
    runtime = SimpleNamespace(
        drive=SimpleNamespace(cores=Cores(), busy=lambda: True),
    )

    with pytest.raises(RuntimeError, match="model_cores_busy"):
        run(["cores", "2"], runtime=runtime)


def test_model_run_forwards_text_and_reasoning_notices() -> None:
    emitted: list[tuple[str, dict[str, object], str]] = []

    class FakeCores:
        def run(self, body: object, *, on_notice: object = None) -> object:
            assert body == "hello"
            assert callable(on_notice)
            on_notice({"kind": "model.delta", "text": "answer"})
            on_notice({"kind": "model.reasoning.delta", "text": "thinking"})
            on_notice({"kind": "unknown", "text": "ignored"})
            return {"type": "model_turn"}

    runtime = SimpleNamespace(
        drive=SimpleNamespace(cores=FakeCores()),
        emit=lambda kind, data, request_id="": emitted.append((kind, data, request_id)),
    )

    result = run(
        ["run", "--", "hello"],
        runtime=runtime,
        request={"request_id": "request-1"},
    )

    assert result == {"type": "model_turn"}
    assert emitted == [
        ("model.delta", {"text": "answer"}, "request-1"),
        ("model.reasoning.delta", {"text": "thinking"}, "request-1"),
    ]
