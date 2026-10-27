"""Provider-neutral tool transcripts become each vendor's request fields."""

import asyncio
from types import SimpleNamespace

from capability.model.model_API.model_interface.anthropic import (
    format_messages as anthropic_messages,
    parse_stream_parts as anthropic_stream,
)
from capability.model.model_API.model_interface.gemini import (
    format_messages as gemini_messages,
    parse_response_turn as gemini_turn,
)
from capability.model.model_API.model_interface.openai_chat import format_messages as chat_messages
from capability.model.model_API.model_interface.openai_response import (
    _DropRepeatedText,
    format_messages as response_messages,
    parse_response_turn as response_turn,
    parse_stream_parts as response_stream,
)
from capability.model.model_runtime.assembler import BlockAssembler


def _transcript() -> list[dict]:
    return [
        {"role": "user", "content": "read the file"},
        {
            "role": "assistant",
            "content": [
                {"type": "text", "text": "I will read it"},
                {"type": "tool-call", "id": "call-1", "name": "read", "arguments": {"file_path": "a.py"}},
            ],
        },
        {"role": "tool", "name": "read", "tool_call_id": "call-1", "content": "print(1)"},
    ]


def test_chat_completions_keep_the_tool_call_id() -> None:
    messages = chat_messages(_transcript())
    call = messages[1]["tool_calls"][0]
    assert call["id"] == "call-1"
    assert call["function"]["name"] == "read"
    assert messages[2]["role"] == "tool"
    assert messages[2]["tool_call_id"] == "call-1"


def test_responses_use_function_call_output() -> None:
    messages = response_messages(_transcript())
    call = next(item for item in messages if item.get("type") == "function_call")
    output = next(item for item in messages if item.get("type") == "function_call_output")
    assert call["call_id"] == "call-1"
    assert call["name"] == "read"
    assert output == {
        "type": "function_call_output",
        "call_id": "call-1",
        "output": "print(1)",
    }
    result = SimpleNamespace(
        output_text="",
        output=[SimpleNamespace(type="function_call", call_id="call-9", id="", name="read", arguments="{}")],
        usage=None,
    )
    turn = response_turn(result)
    assert turn["blocks"][0]["id"] == "call-9"


def test_a_repeated_delta_is_not_appended() -> None:
    payload = '{"state":"continue","pointer":"message/0-3","body":""}'

    async def chunks():
        yield SimpleNamespace(type="response.output_text.delta", delta=payload)
        yield SimpleNamespace(type="response.output_text.delta", delta=payload)
        yield SimpleNamespace(type="response.output_text.done", text=payload)

    async def collect():
        assembler = BlockAssembler()
        async for chunk in _DropRepeatedText(chunks()):
            for part in response_stream(chunk):
                assembler.push(part)
        return assembler.finish().text()

    assert asyncio.run(collect()) == payload


def test_response_done_event_does_not_repeat_the_text() -> None:
    assembler = BlockAssembler()
    chunks = (
        SimpleNamespace(type="response.output_text.delta", delta="process start tools.firecrawl"),
        SimpleNamespace(type="response.output_text.done", text="process start tools.firecrawl"),
    )
    for chunk in chunks:
        for part in response_stream(chunk):
            assembler.push(part)
    assert response_stream(chunks[1]) == []
    assert assembler.finish().text() == "process start tools.firecrawl"


def test_anthropic_names_a_streamed_tool() -> None:
    messages = anthropic_messages(_transcript())
    tool_use = messages[1]["content"][1]
    assert tool_use["type"] == "tool_use"
    assert tool_use["id"] == "call-1"
    assert tool_use["name"] == "read"
    assert messages[2]["content"][0]["tool_use_id"] == "call-1"
    chunk = SimpleNamespace(
        type="content_block_start",
        index=0,
        content_block=SimpleNamespace(type="tool_use", id="call-2", name="bash"),
    )
    assert anthropic_stream(chunk)[0]["name"] == "bash"


def test_gemini_uses_function_call_and_function_response() -> None:
    messages = gemini_messages(_transcript())
    assert messages[1]["parts"][1]["function_call"]["name"] == "read"
    assert messages[2]["parts"][0]["function_response"]["name"] == "read"
    result = SimpleNamespace(
        text="",
        candidates=[
            SimpleNamespace(
                content=SimpleNamespace(
                    parts=[SimpleNamespace(function_call=SimpleNamespace(id="call-3", name="read", args={"file_path": "a.py"}))]
                )
            )
        ],
        usage_metadata=None,
    )
    turn = gemini_turn(result)
    assert turn["blocks"][0]["name"] == "read"
    assert turn["blocks"][0]["id"] == "call-3"
