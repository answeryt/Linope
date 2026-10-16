"""Unfollowed links occupy nothing. Followed links are an occupy task."""

import threading

import pytest

from kernel.hypermedia.follow import follow_selected
from kernel.hypermedia.link import Link
from kernel.hypermedia.representation import Representation
from kernel.resource.communication.kind import channel
from kernel.resource.context.kind import identity as context_identity
from kernel.resource.definition import ResourceGrant, ResourceKind
from kernel.resource.memory.page import Page, PageState
from kernel.resource.memory.task_kind import TaskKind, task_kind_for
from kernel.resource.account.embedded import linked_bytes
from kernel.resource.message import MessageRole, message
from kernel.resource.network.kind import hosts
from kernel.resource.store.page_link import PageLink
from kernel.resource.store.resource_section import ResourceSection
from kernel.resource.tool.kind import identity as tool_identity
from kernel.resource.workspace.kind import identity as workspace_identity


def _document() -> Representation:
    return Representation(
        facts={"name": "search"},
        links=(
            Link(relation="item", resource_id="hit-a", handle="handle-a"),
            Link(relation="item", resource_id="hit-b", handle="handle-b"),
        ),
    )


def test_unfollowed_links_occupy_nothing_and_followed_links_become_pages():
    result = follow_selected(_document(), {"hit-a"})
    assert task_kind_for(followed=False) is TaskKind.FREE
    assert task_kind_for(followed=True) is TaskKind.OCCUPY
    assert [link.resource_id for link in result.followed] == ["hit-a"]


def test_resource_kinds_and_handle_view_stay_as_they_were():
    assert [kind.value for kind in ResourceKind] == [
        "context",
        "memory",
        "workspace",
        "tool",
        "network",
        "communication",
    ]
    payload = ResourceGrant(
        resource_id="entity-1",
        kind=ResourceKind.CONTEXT,
        handle="handle-1",
    ).process_payload()
    assert payload["handle"] == "handle-1"
    assert "resource_id" not in payload


def test_linked_bytes_count_embedded_representations_only() -> None:
    section = ResourceSection(threading.RLock())
    section.save_page(
        Page(address="kept-body", size=5, state=PageState.PINNED),
        PageLink(relation="self", resource_id="kept"),
    )
    section.save_page(
        Page(address="link-only", size=9, state=PageState.SWAPPED),
        PageLink(relation="self", resource_id="link-only"),
    )
    assert linked_bytes(section, "kept") == 5
    assert linked_bytes(section, "link-only") == 0


def test_facility_kind_rules_and_message_roles() -> None:
    assert context_identity("context.sliding_window") == {"id": "context.sliding_window"}
    assert tool_identity("tools.bash") == {"id": "tools.bash"}
    assert workspace_identity("sandbox.local") == {"root": "sandbox.local"}
    assert hosts((" a ", "", "b")) == ("a", "b")
    assert channel(" ledger ") == "ledger"
    assert message(MessageRole.MODEL, "你好") == {
        "role": "model_msg",
        "content": "你好",
    }
    with pytest.raises(ValueError):
        workspace_identity("")
    with pytest.raises(ValueError):
        context_identity("")
    with pytest.raises(ValueError):
        channel("  ")
