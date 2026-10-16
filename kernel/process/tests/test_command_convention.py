"""Old marker commands are no longer a command form."""

from kernel.command import main


def test_marker_commands_are_not_accepted() -> None:
    assert main(["service", "start", "agent", "svc"]) == 2
    assert main(["load", "tools.read", "cap", "tool", "{}"]) == 2
