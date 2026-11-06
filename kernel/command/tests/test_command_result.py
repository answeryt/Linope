"""A command result is the whole answer, not one stream fragment."""

from kernel.command.process.clerk import execute_line
from kernel.command.process.listen import _show
from kernel.command.window import bind_window, reset_window


def test_a_turn_prints_every_text_block(capsys) -> None:
    _show(
        {
            "type": "model" + "_turn",
            "blocks": [
                {"type": "text", "text": "第一行"},
                {"type": "reasoning", "text": "hidden"},
                {"type": "text", "text": "第二行"},
            ],
        }
    )
    assert capsys.readouterr().out == "第一行\n第二行\n"


def test_a_command_result_drops_stream_fragments() -> None:
    class Window:
        def _command(self, text: str) -> None:
            del text
            print('{"type": "text-delta", "text": "."}', flush=True)
            _show(
                {
                    "type": "model" + "_turn",
                    "blocks": [
                        {"type": "text", "text": "第一行"},
                        {"type": "text", "text": "第二行"},
                    ],
                }
            )
            print('{"type": "done"}', flush=True)

    token = bind_window(Window())
    try:
        assert execute_line("load message 1 -- hello") == "第一行\n第二行"
    finally:
        reset_window(token)
