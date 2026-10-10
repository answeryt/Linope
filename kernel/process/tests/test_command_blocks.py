from __future__ import annotations

from kernel.command.command_blocks import (
    command_lines_from_reply,
    reply_text,
    tool_body,
)


def test_process_result_envelope_is_unwrapped_before_command_scan() -> None:
    reply = {
        "event": "result",
        "result": "load tools.glob tool {pattern:**/*,path:.}",
    }
    assert reply_text(reply).startswith("load tools.glob tool")
    assert command_lines_from_reply(reply, frozenset({"load"})) == [
        "load tools.glob tool {pattern:**/*,path:.}"
    ]


def test_text_block_is_scanned_but_tool_result_is_not() -> None:
    reply = {
        "event": "result",
        "result": {
            "type": "model_turn",
            "blocks": [
                {"type": "text", "text": "load room"},
                {"type": "tool-result", "request_id": "1", "output": "load room"},
            ],
        },
    }
    assert command_lines_from_reply(reply, frozenset({"room"})) == ["room"]


def test_old_model_mapping_is_accepted_as_tool_arguments() -> None:
    assert tool_body('{pattern:**/*,path:.}') == {
        "pattern": "**/*",
        "path": ".",
    }
