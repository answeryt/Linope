"""Old marker commands are no longer a command form."""

import pytest

from kernel.command import main
from kernel.command.parser import UsageError


def test_marker_commands_are_not_accepted() -> None:
    with pytest.raises(UsageError):
        main(["service", "start", "agent", "svc"])
    with pytest.raises((UsageError, RuntimeError)):
        main(["load", "tools.read", "cap", "tool", "{}"])


def test_process_start_is_a_command() -> None:
    with pytest.raises(UsageError):
        main(["process"])
    with pytest.raises(UsageError):
        main(["process", "start"])
