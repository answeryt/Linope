"""route refuses to choose a transport."""

import pytest

from kernel.load_balancing.route import route


def test_route_without_a_channel_does_not_name_one() -> None:
    with pytest.raises(ValueError, match="^No channel selected$") as caught:
        route(
            None,
            kind="memory",
            identity={},
            body={},
            capability="tools.x",
            opener=lambda: "1",
        )
    assert "open_channel" not in str(caught.value)
