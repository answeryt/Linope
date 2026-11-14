"""Pointers stay independent from the removed terminal context."""

from kernel.communication.page import CommandOffer
from kernel.hypermedia.uri import parse_resource_uri


def test_command_pointers_do_not_require_a_runtime_context() -> None:
    assert CommandOffer("start", "tools.read").pointer == "process start tools.read"
    assert CommandOffer("tool", "tools.read", pid=7).pointer == "load tool 7 -- "
    assert CommandOffer("ask", "tools.read", pid=7).pointer == "ask 7 -- "


def test_resource_uri_pointer_keeps_its_address() -> None:
    assert parse_resource_uri("http://127.0.0.1/resources/abcdef") == "abcdef"
