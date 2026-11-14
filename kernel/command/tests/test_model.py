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
