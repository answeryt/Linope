"""A command result is a value, never a display byte."""

from kernel.command.process.clerk import execute_line


def test_nested_command_returns_structured_value() -> None:
    class Window:
        nested = False

        def _execute_text(self, text: str, *, request_id: str = "") -> object:
            del request_id
            assert text == "process list"
            return {"processes": [{"pid": 7, "capability": "tools.read"}]}

    assert execute_line("process list", Window()) == {
        "processes": [{"pid": 7, "capability": "tools.read"}]
    }
