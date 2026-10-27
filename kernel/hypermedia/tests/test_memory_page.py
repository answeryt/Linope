"""A model page: this turn's words, older addresses, and the links it may follow."""

from types import SimpleNamespace

from kernel.communication.page import CommandOffer, model_page
from kernel.hypermedia.memory_page import memory_page, page_document
from kernel.hypermedia.process_page import process_page


def _rows() -> list[dict]:
    return [
        {"address": "system/0", "kind": "system", "content": "rules", "seq": 1, "time": "2026-10-22T15:00:00+00:00"},
        {"address": "message/0", "kind": "user", "content": "old question", "seq": 2, "time": "2026-10-22T15:01:00+00:00"},
        {"address": "message/1", "kind": "model", "content": "old answer", "seq": 3, "state": "answered", "time": "2026-10-22T15:02:00+00:00"},
        {"address": "message/2", "kind": "user", "content": "new question", "seq": 4, "state": "asked", "time": "2026-10-22T15:03:00+00:00"},
        {"address": "task/0", "kind": "other", "content": "pid=7 capability=tools.ddgs", "seq": 5, "state": "resulted", "time": "2026-10-22T15:04:00+00:00"},
    ]


def test_only_this_turn_carries_words() -> None:
    document = page_document(model_page(_rows(), scope="s", seq=5))
    assert document["state"] == "resulted"
    assert [row["content"] for row in document["rows"]] == ["new question", "pid=7 capability=tools.ddgs"]
    assert [row["time"] for row in document["rows"]] == [
        "2026-10-22T15:03:00+00:00",
        "2026-10-22T15:04:00+00:00",
    ]
    assert {"system/0", "message/0", "message/1", "answer"} <= set(document["_links"])
    assert document["_links"]["message/0"]["time"] == "2026-10-22T15:01:00+00:00"
    assert document["_links"]["message/0"]["kind"] == "user"
    assert "content" not in document["_links"]["message/0"]
    assert "time" not in document["_links"]["answer"]


def test_command_links_carry_their_pointer_pid_and_schema() -> None:
    page = model_page(
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
    assert "time" not in links["start:tools.firecrawl"]
    assert "time" not in links["tool:tools.ddgs"]


def test_a_handle_changes_when_the_seq_changes() -> None:
    first = page_document(model_page(_rows(), scope="s", seq=5))["_links"]["answer"]["handle"]
    later = page_document(model_page(_rows(), scope="s", seq=6))["_links"]["answer"]["handle"]
    assert first != later
    assert len(first) == 32


def test_a_memory_projection_lists_addresses_without_commands() -> None:
    document = page_document(memory_page(_rows(), scope="s", seq=5))
    assert "message/0" in document["_links"]
    assert "answer" not in document["_links"]
    assert "memory" not in document["_links"]
    assert all(not name.startswith("start:") for name in document["_links"])


def test_stop_is_not_followed_with_the_bare_pid() -> None:
    record = SimpleNamespace(pid=4321, status="ready", capability_id="tools.ddgs", leases=(), started="t")
    stop = next(link for link in process_page(record, "sleeping").links if link.relation == "stop")
    assert stop.handle != "4321"
    assert stop.can_follow()
