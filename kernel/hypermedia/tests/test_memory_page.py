"""A model page: this turn's words, older addresses, and the links it may follow."""

from types import SimpleNamespace

from kernel.hypermedia.memory_page import CommandOffer, memory_page, page_document
from kernel.hypermedia.process_page import process_page


def _rows() -> list[dict]:
    return [
        {"address": "system/0", "kind": "system", "content": "规矩", "seq": 1},
        {"address": "message/0", "kind": "user", "content": "旧问题", "seq": 2},
        {"address": "message/1", "kind": "model", "content": "旧回答", "seq": 3, "state": "answered"},
        {"address": "message/2", "kind": "user", "content": "新问题", "seq": 4, "state": "asked"},
        {"address": "task/0", "kind": "other", "content": "pid=7 capability=tools.ddgs", "seq": 5, "state": "resulted"},
    ]


def test_only_this_turn_carries_words() -> None:
    document = page_document(memory_page(_rows(), scope="s", seq=5))
    assert document["state"] == "resulted"
    assert [row["content"] for row in document["rows"]] == ["新问题", "pid=7 capability=tools.ddgs"]
    assert {"system/0", "message/0", "message/1", "answer"} <= set(document["_links"])
    assert "content" not in document["_links"]["message/0"]


def test_command_links_carry_their_pointer_pid_and_schema() -> None:
    page = memory_page(
        _rows(),
        scope="s",
        seq=5,
        commands=(
            CommandOffer("start", "tools.firecrawl"),
            CommandOffer("tool", "tools.ddgs", pid=7, schema={"required": ["query"]}),
        ),
    )
    links = page_document(page)["_links"]
    assert links["start:tools.firecrawl"]["pointer"] == "process start tools.firecrawl"
    assert links["tool:tools.ddgs"]["pointer"] == "load tool 7 -- "
    assert links["tool:tools.ddgs"]["pid"] == 7
    assert links["tool:tools.ddgs"]["schema"] == {"required": ["query"]}


def test_a_handle_changes_when_the_seq_changes() -> None:
    first = page_document(memory_page(_rows(), scope="s", seq=5))["_links"]["answer"]["handle"]
    later = page_document(memory_page(_rows(), scope="s", seq=6))["_links"]["answer"]["handle"]
    assert first != later
    assert len(first) == 32


def test_stop_is_not_followed_with_the_bare_pid() -> None:
    record = SimpleNamespace(pid=4321, status="ready", capability_id="tools.ddgs", leases=(), started="t")
    stop = next(link for link in process_page(record, "sleeping").links if link.relation == "stop")
    assert stop.handle != "4321"
    assert stop.can_follow()
