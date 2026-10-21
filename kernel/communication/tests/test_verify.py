"""One model output checked against one page. Nothing is started here."""

import json

from kernel.communication.verify import Rejection, Step, verify
from kernel.hypermedia.memory_page import CommandOffer, memory_page, page_document

_SCHEMA = {
    "type": "object",
    "properties": {
        "query": {"type": "string"},
        "limit": {"type": "integer", "minimum": 1, "maximum": 10},
    },
    "required": ["query"],
}


def _rows() -> list[dict]:
    return [
        {"address": "system/0", "kind": "system", "content": "规矩", "seq": 1},
        {"address": "message/0", "kind": "user", "content": "旧问题", "seq": 2},
        {"address": "message/1", "kind": "model", "content": "旧回答", "seq": 3, "state": "answered"},
        {"address": "message/2", "kind": "user", "content": "复联五什么时候上映", "seq": 4, "state": "asked"},
    ]


def _page(*commands: CommandOffer, seq: int = 4):
    return memory_page(_rows(), scope="search", seq=seq, commands=commands)


def _start_page():
    return _page(CommandOffer("start", "tools.ddgs"))


def _tool_page():
    return _page(CommandOffer("tool", "tools.ddgs", pid=18432, schema=_SCHEMA))


def test_a_bare_start_line_passes() -> None:
    step = verify("process start tools.ddgs --with memory=search --share memory", _start_page())
    assert isinstance(step, Step)
    assert step.way == "start"
    assert step.argv == ("tools.ddgs", "--with", "memory=search", "--share", "memory")


def test_the_same_start_as_continue_is_the_same_step() -> None:
    bare = verify("process start tools.ddgs --share memory", _start_page())
    wrapped = verify(
        json.dumps({"state": "continue", "pointer": "process start tools.ddgs --share memory"}),
        _start_page(),
    )
    assert bare == wrapped


def test_a_bare_tool_line_and_its_continue_form_agree() -> None:
    bare = verify('load tool 18432 -- {"query": "复联五", "limit": 5}', _tool_page())
    wrapped = verify(
        json.dumps(
            {
                "state": "continue",
                "pointer": "load tool 18432 -- ",
                "body": {"query": "复联五", "limit": 5},
            },
            ensure_ascii=False,
        ),
        _tool_page(),
    )
    assert isinstance(bare, Step) and bare.way == "tool"
    assert bare == wrapped
    assert bare.pid == 18432
    assert bare.body == {"query": "复联五", "limit": 5}


def test_a_linope_prefix_and_a_code_fence_are_still_a_command() -> None:
    step = verify("```text\nlinope process start tools.ddgs\n```", _start_page())
    assert isinstance(step, Step) and step.way == "start"


def test_a_command_in_backticks_is_still_checked_as_a_command() -> None:
    line = 'load tool 18432 -- {"query": "复联五", "limit": 5}'
    assert verify(f"`{line}`", _tool_page()) == verify(line, _tool_page())
    refused = verify('`load tool 99999 -- {"query": "复联五"}`', _tool_page())
    assert isinstance(refused, Rejection)
    assert refused.field == "pointer"


def test_plain_words_are_an_answer() -> None:
    step = verify("复联五在 2027 年上映。来源：标题，https://example.com", _start_page())
    assert step == Step("answer", "answer", "复联五在 2027 年上映。来源：标题，https://example.com")


def test_answer_as_continue_needs_words() -> None:
    step = verify(json.dumps({"state": "continue", "pointer": "answer", "body": ""}), _start_page())
    assert isinstance(step, Rejection)
    assert step.field == "body"


def test_a_read_pointer_expands_its_range() -> None:
    step = verify(json.dumps({"state": "continue", "pointer": "message/0-1"}), _start_page())
    assert step == Step("read", "message/0 message/1")


def test_a_read_outside_the_page_is_refused() -> None:
    step = verify(json.dumps({"state": "continue", "pointer": "message/0-9"}), _start_page())
    assert isinstance(step, Rejection)
    assert step.field == "pointer"
    assert "message/3" in step.error


def test_a_start_that_is_not_offered_lists_what_is() -> None:
    step = verify("process start tools.firecrawl", _start_page())
    assert isinstance(step, Rejection)
    assert step.field == "pointer"
    assert step.got == "process start tools.firecrawl"
    assert "process start tools.ddgs" in step.allowed
    assert step.seq == 4


def test_a_wrong_pid_is_refused_with_details() -> None:
    step = verify('load tool 99999 -- {"query": "复联五"}', _tool_page())
    assert isinstance(step, Rejection)
    payload = step.payload()
    assert set(payload) == {"error", "field", "got", "allowed", "seq"}
    assert "99999" in payload["error"]
    assert payload["field"] == "pointer"
    assert "load tool 18432 -- " in payload["allowed"]


def test_parser_errors_keep_the_parser_words() -> None:
    step = verify("load tool 18432", _tool_page())
    assert isinstance(step, Rejection)
    assert step.error.startswith("用法: load")


def test_an_unknown_start_option_is_refused() -> None:
    step = verify("process start tools.ddgs --nope 1", _start_page())
    assert isinstance(step, Rejection)
    assert step.field == "pointer"


def test_tool_arguments_follow_the_schema() -> None:
    page = _tool_page()
    missing = verify('load tool 18432 -- {"limit": 5}', page)
    assert isinstance(missing, Rejection) and missing.field == "body.query"
    wide = verify('load tool 18432 -- {"query": "复联五", "limit": 50}', page)
    assert isinstance(wide, Rejection) and wide.field == "body.limit"
    assert "1 到 10" in wide.error
    text = verify("load tool 18432 -- 复联五", page)
    assert isinstance(text, Rejection) and text.field == "body"


def test_broken_json_and_a_wrong_state_say_where() -> None:
    broken = verify('{"state": "continue", "pointer": ', _start_page())
    assert isinstance(broken, Rejection) and broken.field == "format"
    wrong = verify(json.dumps({"state": "go", "pointer": "answer"}), _start_page())
    assert isinstance(wrong, Rejection) and wrong.field == "state"


def test_other_commands_are_not_on_the_page() -> None:
    step = verify("list", _start_page())
    assert isinstance(step, Rejection)
    assert step.error == "这条命令不在当前页里"


def test_a_stale_page_and_a_stale_handle_are_refused() -> None:
    old = _start_page()
    stale = verify("process start tools.ddgs", old, current_seq=5)
    assert isinstance(stale, Rejection) and stale.field == "seq"
    old_handle = page_document(old)["_links"]["start:tools.ddgs"]["handle"]
    newer = _page(CommandOffer("start", "tools.ddgs"), seq=5)
    replay = verify(
        json.dumps({"state": "continue", "pointer": "process start tools.ddgs", "handle": old_handle}),
        newer,
    )
    assert isinstance(replay, Rejection) and replay.field == "seq"
