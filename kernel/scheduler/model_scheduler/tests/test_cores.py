from kernel.scheduler.model_scheduler.cores import Cores
from kernel.scheduler.model_scheduler.model import ModelCard


def _card() -> ModelCard:
    return ModelCard(
        capability="model.test",
        card_id="test",
        provider="test",
        model="test-model",
        context_limit=1024,
        call_params={"temperature": 0.2},
    )


def test_resizing_copies_the_current_card_to_new_cores() -> None:
    cores = Cores()
    cores.model.install_card(_card())

    info = cores.set_count(3)

    assert info["configured"] is True
    assert info["cores"] == 3
    assert [model.card.model for model in cores.models] == [
        "test-model",
        "test-model",
        "test-model",
    ]


def test_resizing_rejects_zero_and_can_shrink_when_idle() -> None:
    cores = Cores(3)

    try:
        cores.set_count(0)
    except ValueError as exc:
        assert "at least 1" in str(exc)
    else:
        raise AssertionError("zero cores must be rejected")

    assert cores.set_count(1)["cores"] == 1
