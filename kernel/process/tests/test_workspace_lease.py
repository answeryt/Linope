"""Workspace lease: mount view, mapped file pages, and embedded usage."""

from kernel.resource.definition import ResourceKind
from kernel.resource.memory.page import Page, PageState
from kernel.resource.store.page_link import PageLink
from kernel.resource.workspace.address.pages import mapped_pages
from kernel.resource.workspace.mount.mode import check_mode, confines
from kernel.resource.workspace.mount.view import admit_path, blocked, private_temp
from kernel.resource.account import (
    admits,
    byte_ceiling,
    require_room,
    workspace_room,
)
from kernel.resource.account.embedded import linked_bytes
from kernel.process.profiles import tool_with_workspace
from capability.tools.agent_tools.interaction_tools.ask_user_plugin import (
    capability_profile as ask_profile,
)
from capability.tools.agent_tools.web_search_tools.firecrawl_plugin import (
    capability_profile as firecrawl_profile,
)
from capability.tools.agent_tools.web_search_tools.searxng_plugin import (
    capability_profile as searxng_profile,
)
from pathlib import Path

import pytest


def test_no_handle_maps_no_pages() -> None:
    page = Page(address="notes.txt", size=4, state=PageState.PINNED)
    link = PageLink(relation="self", resource_id="notes.txt", handle="ws")
    assert mapped_pages("", ((page, link),)) == ()
    assert mapped_pages(None, ((page, link),)) == ()


def test_handle_maps_only_its_file_pages() -> None:
    kept = Page(address="notes.txt", size=4, state=PageState.PINNED)
    swapped = Page(address="old.txt", size=9, state=PageState.SWAPPED)
    other = Page(address="elsewhere.txt", size=3, state=PageState.RESIDENT)
    pairs = (
        (kept, PageLink(relation="self", resource_id="notes.txt", handle="ws")),
        (swapped, PageLink(relation="self", resource_id="old.txt", handle="ws")),
        (other, PageLink(relation="self", resource_id="elsewhere.txt", handle="other")),
    )
    assert mapped_pages("ws", pairs) == (kept, swapped)

    class Store:
        def all_pages(self):
            return pairs

    assert linked_bytes(Store(), "notes.txt") == 4
    assert linked_bytes(Store(), "old.txt") == 0


def test_byte_ceiling_ignores_window_and_refuses_another_body() -> None:
    assert byte_ceiling({"window": 1}) is None
    assert byte_ceiling({"bytes": 5}) == 5
    assert admits(4, 1, 5) is True
    assert admits(4, 2, 5) is False
    assert admits(4, 2, None) is True
    require_room(4, 1, 5)
    require_room(4, 2, None)
    with pytest.raises(PermissionError, match="用量到顶"):
        require_room(4, 2, 5)


def test_mount_hides_git_secrets_and_keeps_a_private_temp(tmp_path: Path) -> None:
    assert blocked(tmp_path / ".git" / "config") is True
    assert blocked(tmp_path / ".env") is True
    assert blocked(tmp_path / ".ssh" / "config") is True
    assert blocked(tmp_path / ".aws" / "credentials") is True
    assert blocked(tmp_path / "token.pem") is True
    assert blocked(tmp_path / "sign.key") is True
    assert blocked(tmp_path / "notes.txt") is False
    assert private_temp(str(tmp_path), "room").endswith("room")
    assert check_mode("read-only") == "read-only"
    assert confines("workspace-write") is True
    assert confines("danger-full-access") is False


def test_workspace_room_uses_the_lease_that_contains_the_file(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    root.mkdir()
    notes = root / "notes.txt"
    notes.write_text("hello", encoding="utf-8")
    page = Page(address=str(notes), size=5, state=PageState.RESIDENT)
    link = PageLink(relation="self", resource_id=str(notes), handle="ws")

    class Entity:
        kind = "workspace"
        identity = {"root": str(root)}

    class Lease:
        process_id = "writer"

    class Store:
        def entity(self, resource_id):
            return Entity() if resource_id == "workspace" else None

        def active_lease_rows(self):
            return (("workspace", Entity(), Lease(), "ws"),)

        def pages_for_handle(self, handle):
            if handle != "ws":
                return ()
            return ((page, link),)

        def get_process(self, process_id):
            return {
                "activation": {
                    "resource_context": {
                        "grants": [
                            {
                                "handle": "ws",
                                "kind": "workspace",
                                "limits": {"bytes": 6},
                            }
                        ]
                    }
                }
            }

    used, ceiling, counted = workspace_room(Store(), str(notes))
    assert used == 5
    assert counted == 5
    assert ceiling == 6
    require_room(max(0, used - counted), 2, ceiling)
    with pytest.raises(PermissionError, match="用量到顶"):
        require_room(used, 2, ceiling)


def test_admit_path_rejects_escape_secrets_and_other_temp(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    root.mkdir()
    own = private_temp(str(root), "me")
    Path(own).mkdir(parents=True)
    other = Path(private_temp(str(root), "them"))
    other.mkdir(parents=True)
    (other / "note.txt").write_text("x", encoding="utf-8")
    notes = root / "notes.txt"
    notes.write_text("hi", encoding="utf-8")
    pem = root / "token.pem"
    pem.write_text("k", encoding="utf-8")
    outside = tmp_path / "outside.txt"
    outside.write_text("no", encoding="utf-8")
    roots = ((str(root.resolve()), True), (own, True))
    assert admit_path(notes, roots, write=False, own_temp=own) == notes.resolve()
    for path in (other / "note.txt", pem, outside):
        with pytest.raises(PermissionError):
            admit_path(path, roots, write=False, own_temp=own)
    with pytest.raises(PermissionError, match="只能读"):
        admit_path(notes, ((str(root.resolve()), False),), write=True, own_temp="")
    link = root / "jump"
    try:
        link.symlink_to(outside)
    except OSError:
        return
    with pytest.raises(PermissionError):
        admit_path(link, roots, write=False, own_temp=own)


def test_file_peers_lease_workspace_and_search_leases_network() -> None:
    workspace = tool_with_workspace("tools.read", ())
    kinds = {claim.kind for claim in workspace.resources}
    assert ResourceKind.WORKSPACE in kinds
    assert ResourceKind.TOOL in kinds
    search = firecrawl_profile("tools.firecrawl", ())
    fetch = searxng_profile("tools.searxng", ())
    for declaration in (search, fetch):
        kinds = {claim.kind for claim in declaration.resources}
        assert ResourceKind.NETWORK in kinds
        assert ResourceKind.WORKSPACE not in kinds
    profile = ask_profile("tools.ask_user", ())
    assert all(claim.kind is not ResourceKind.WORKSPACE for claim in profile.resources)
