from kernel.hypermedia.representation_json import links_for_state
from kernel.hypermedia.uri import parse_action_uri, parse_resource_uri
from kernel.hypermedia.link import Link
from kernel.resource.definition import ResourceKind


def test_resource_kinds_are_only_the_process_resources() -> None:
    assert tuple(kind.value for kind in ResourceKind) == (
        "memory",
        "tool",
        "sandbox",
        "network",
    )


def test_page_menu_has_only_state_actions() -> None:
    resident = {link.relation for link in links_for_state("notes.txt", "a" * 32, "resident")}
    swapped = {link.relation for link in links_for_state("notes.txt", "a" * 32, "swapped")}
    assert resident == {"self", "content", "pin", "swap"}
    assert swapped == {"self", "admit"}


def test_resource_uris_keep_the_handle_opaque() -> None:
    link = Link(relation="self", resource_id="C:/private/notes.txt", handle="a" * 32)
    href = "http://127.0.0.1:49152/resources/" + link.handle
    assert parse_resource_uri(href) == link.handle
    assert parse_action_uri(href + "/pin") == (link.handle, "pin")
