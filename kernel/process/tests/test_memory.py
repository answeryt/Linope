"""Long-term pages occupy a model's window. Unfollowed links occupy nothing."""

from kernel.process.hypermedia.follow import follow_selected
from kernel.process.hypermedia.link import Link
from kernel.process.hypermedia.representation import Representation
from kernel.resource.definition import ResourceGrant, ResourceKind
from kernel.resource.memory.ledger import ledger_for
from kernel.resource.memory.page import PageState, page_for_target
from kernel.resource.memory.page_table import PageTable
from kernel.resource.memory.readers import Reader, measure, tightest_window
from kernel.resource.memory.task_kind import TaskKind, task_kind_for


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

    table = PageTable()
    for link in result.followed:
        table = table.place(page_for_target(link.resource_id, size=30))

    assert [page.address for page in table.pages] == ["hit-a"]
    ledger = ledger_for(table.pages, window=100)
    assert ledger.used == 30
    assert ledger.fits()


def test_swapped_page_drops_out_of_the_window_and_pinned_page_stays():
    table = PageTable(
        pages=(
            page_for_target("hit-a", 30),
            page_for_target("hit-b", 40),
        )
    )
    table = table.pin("hit-a").swap_out("hit-b")
    assert table.pages[0].state is PageState.PINNED
    assert table.pages[1].state is PageState.SWAPPED
    assert ledger_for(table.pages, window=50).used == 30


def test_two_model_windows_are_not_added():
    pages = (page_for_target("hit-a", 30),)
    readers = (
        Reader(model_id="small-model", window=40),
        Reader(model_id="large-model", window=200),
    )
    ledgers = measure(pages, readers)

    assert [ledger.window for ledger in ledgers] == [40, 200]
    assert [ledger.used for ledger in ledgers] == [30, 30]
    assert tightest_window(readers) == 40
    assert all(ledger.window != 240 for ledger in ledgers)
    assert ledgers[0].fits()
    assert not ledger_for(pages, window=20).fits()


def test_resource_kinds_and_handle_view_stay_as_they_were():
    assert [kind.value for kind in ResourceKind] == [
        "context",
        "model",
        "memory",
        "workspace",
        "tool",
        "network",
        "identity",
        "persistence",
        "lifecycle",
        "communication",
        "prompt",
    ]
    payload = ResourceGrant(
        resource_id="entity-1",
        kind=ResourceKind.CONTEXT,
        handle="handle-1",
    ).process_payload()
    assert payload["handle"] == "handle-1"
    assert "resource_id" not in payload
