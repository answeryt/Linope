"""Links stay on the representation until a client follows them."""

import pytest

from kernel.hypermedia.file_link import (
    representation_for_file,
)
from kernel.hypermedia.follow import follow_selected, link_named
from kernel.hypermedia.link import Link
from kernel.hypermedia.representation import Representation
from kernel.hypermedia.observation import observation_body
from kernel.hypermedia.representation_json import file_resource_payload
from kernel.hypermedia.tool_effect import (
    ToolEffect,
    declare_tool,
    effect_for,
    forget_tool,
)
from kernel.hypermedia.uri import (
    content_uri,
    parse_action_uri,
    parse_content_uri,
    parse_resource_uri,
    parse_tool_uri,
    resource_uri,
)


def _document() -> Representation:
    return Representation(
        facts={"name": "notes"},
        links=(
            Link(relation="item", resource_id="file-a", handle="handle-a"),
            Link(relation="item", resource_id="file-b", handle="handle-b"),
            Link(relation="item", resource_id="file-c", handle=""),
        ),
    )


def test_one_representation_carries_many_links():
    document = _document()
    assert document.facts["name"] == "notes"
    assert [link.resource_id for link in document.links] == [
        "file-a",
        "file-b",
        "file-c",
    ]


def test_follow_only_selected_links_with_a_handle():
    result = follow_selected(_document(), {"file-a", "file-c"})
    assert [link.resource_id for link in result.followed] == ["file-a"]
    assert [link.resource_id for link in result.left] == ["file-b", "file-c"]


def test_following_nothing_writes_no_pages():
    result = follow_selected(_document(), ())
    assert result.followed == ()
    assert len(result.left) == 3


def test_link_without_relation_or_target_is_rejected():
    with pytest.raises(ValueError):
        Link(relation="", resource_id="file-a", handle="handle-a")
    with pytest.raises(ValueError):
        Link(relation="item", resource_id="", handle="handle-a")


def test_a_file_link_with_a_handle_can_be_followed():
    document = representation_for_file(r"C:\身份.md", "handle-a")
    result = follow_selected(document, {r"C:\身份.md"})
    assert result.left == ()
    assert [link.relation for link in result.followed] == ["self"]
    assert [link.handle for link in result.followed] == ["handle-a"]


def test_a_file_link_without_a_handle_stays_put():
    document = representation_for_file(r"C:\身份.md", "")
    result = follow_selected(document, {r"C:\身份.md"})
    assert result.followed == ()
    assert [link.resource_id for link in result.left] == [r"C:\身份.md"]


def test_http_uri_and_hateoas_payload_are_uniform():
    link = Link(relation="self", resource_id="identity.md", handle="a" * 32)
    base = "http://127.0.0.1:49152"
    href = resource_uri(link, base)
    assert href == f"{base}/resources/{link.handle}"
    assert parse_resource_uri(href) == link.handle
    content = content_uri(link, base)
    assert parse_content_uri(content) == link.handle

    payload = file_resource_payload(
        path=link.resource_id,
        handle=link.handle,
        state="resident",
        base_url=base,
    )
    assert payload["type"] == "file"
    assert payload["_links"]["self"]["rel"] == "self"
    assert payload["_links"]["self"]["href"] == href
    assert payload["_links"]["content"]["rel"] == "content"
    assert payload["_links"]["content"]["method"] == "GET"
    assert payload["_links"]["pin"]["method"] == "POST"
    assert payload["_links"]["swap"]["method"] == "POST"
    assert "admit" not in payload["_links"]
    assert parse_action_uri(payload["_links"]["pin"]["href"]) == (link.handle, "pin")


def test_page_state_decides_which_relations_appear():
    handle = "b" * 32
    base = "http://127.0.0.1:49152"
    resident = file_resource_payload("notes.md", handle, "resident", base)
    pinned = file_resource_payload("notes.md", handle, "pinned", base)
    swapped = file_resource_payload("notes.md", handle, "swapped", base)
    assert set(resident["_links"]) == {"self", "content", "pin", "swap"}
    assert set(pinned["_links"]) == {"self", "content"}
    assert set(swapped["_links"]) == {"self", "admit"}
    assert link_named(Representation(facts={}, links=()), "content") is None


def test_link_named_returns_only_a_followable_relation():
    document = _document()
    assert link_named(document, "item").resource_id == "file-a"
    assert link_named(document, "missing") is None


def test_compress_and_tools_join_the_menu_only_when_asked():
    handle = "c" * 32
    base = "http://127.0.0.1:49152"
    plain = file_resource_payload("notes.md", handle, "resident", base)
    assert "compress" not in plain["_links"]
    assert "web_search" not in plain["_links"]
    offered = file_resource_payload(
        "notes.md",
        handle,
        "resident",
        base,
        compress=True,
        tool_names=("web_search", "read"),
    )
    assert offered["_links"]["compress"]["method"] == "POST"
    assert offered["_links"]["web_search"]["method"] == "POST"
    assert parse_tool_uri(offered["_links"]["web_search"]["href"]) == (
        handle,
        "web_search",
    )
    hidden = file_resource_payload(
        "notes.md",
        handle,
        "swapped",
        base,
        compress=True,
        tool_names=("web_search",),
    )
    assert "compress" not in hidden["_links"]
    assert "content" not in hidden["_links"]
    assert "web_search" in hidden["_links"]


def test_tool_effects_keep_search_free_and_compression_system():
    assert effect_for("web_search") is ToolEffect.LINK
    assert effect_for("grep") is ToolEffect.LINK
    assert effect_for("read") is ToolEffect.OCCUPY
    assert effect_for("bash") is ToolEffect.OCCUPY
    assert effect_for("context.sliding_window") is ToolEffect.SYSTEM
    assert effect_for("mcp__remote__lookup") is ToolEffect.LINK
    declare_tool("mcp__remote__write", ToolEffect.OCCUPY)
    try:
        assert effect_for("mcp__remote__write") is ToolEffect.OCCUPY
    finally:
        forget_tool("mcp__remote__write")
    assert effect_for("mcp__remote__write") is ToolEffect.LINK


def test_observation_carries_the_self_href_and_a_copy():
    payload = file_resource_payload(
        "notes.md",
        "d" * 32,
        "resident",
        "http://127.0.0.1:49152",
    )
    body = observation_body(payload)
    assert body["operation"] == "observe"
    assert body["href"] == payload["_links"]["self"]["href"]
    assert body["representation"]["state"] == "resident"
    assert "swap" in body["representation"]["_links"]


def test_http_uri_rejects_non_loopback_and_invalid_paths():
    with pytest.raises(ValueError):
        parse_resource_uri("https://example.com/resources/" + "a" * 32)
    with pytest.raises(ValueError):
        parse_resource_uri("http://127.0.0.1:49152/resources/../secret")
    with pytest.raises(ValueError):
        parse_resource_uri("http://127.0.0.1:49152/resources/not-a-handle")
    with pytest.raises(ValueError):
        parse_resource_uri("http://127.0.0.1:49152/resources/" + "a" * 32 + "?x=1")
