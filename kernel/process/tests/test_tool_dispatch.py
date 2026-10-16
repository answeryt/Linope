"""A tool step keeps its call id and does not execute the tool to read its schema."""

from kernel.process.process_manager.tool_dispatch import declared_tool_schema, tool_request


def test_a_tool_request_keeps_the_call_and_wraps_mcp() -> None:
    plain = tool_request("read", {"file_path": "a.py"}, call_id="call-1", task_id="task-1")
    assert plain["tool_name"] == "read"
    assert plain["call_id"] == "call-1"
    assert plain["task_id"] == "task-1"
    assert plain["body"] == {"file_path": "a.py"}
    wrapped = tool_request("mcp.echo", {"text": "hi"}, call_id="call-2", task_id="task-1")
    assert wrapped["body"] == {"name": "mcp.echo", "arguments": {"text": "hi"}}


def test_schema_lookup_does_not_invent_a_missing_capability() -> None:
    assert declared_tool_schema("tools.not_a_real_capability") == []
