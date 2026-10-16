"""Resource account: pages, context tokens, network, and communication."""

import threading

from kernel.process.declaration import ProcessDeclaration, ResourceClaim
from kernel.process.ledger import MemoryResourceStore
from kernel.resource.account import (
    process,
    record_communication,
    record_context,
    record_network,
    service,
    total,
)
from kernel.resource.compile import compile_declaration
from kernel.resource.definition import ResourceKind
from kernel.resource.memory.page import Page, PageState
from kernel.resource.pool import ResourcePool
from kernel.resource.store.page_link import PageLink
from kernel.resource.store.resource_section import ResourceSection


def test_process_service_and_total_sum_embedded_pages_once() -> None:
    store = MemoryResourceStore()
    declaration = ProcessDeclaration(
        capability="tools.write",
        resources=(
            ResourceClaim(
                kind=ResourceKind.WORKSPACE,
                identity={"root": "/proj"},
                limits={"bytes": 10},
            ),
        ),
    )
    compiled = compile_declaration(declaration, "writer")
    store.register_process("writer", "tools.write", None, "running")
    store.register_process("reader", "tools.read", None, "running")
    pool = ResourcePool(store)
    pool.bind("writer", "tools.write", compiled)
    handle = pool.grants_for("writer")[0].handle
    store.set_activation(
        "writer",
        {
            "resource_context": {
                "grants": [{"handle": handle, "limits": {"bytes": 10}}]
            }
        },
    )
    store.save_page(
        Page(address="/proj/notes.txt", size=4, state=PageState.PINNED),
        PageLink(relation="self", resource_id=compiled[0].resource_id, handle=handle),
    )
    store.save_page(
        Page(address="/proj/old.txt", size=9, state=PageState.SWAPPED),
        PageLink(relation="self", resource_id=compiled[0].resource_id, handle=handle),
    )

    one = process(store, "writer")
    line = one.line("workspace")
    assert line is not None
    assert line.used == 4
    assert line.ceiling == 10
    assert line.unit == "bytes"
    assert process(store, "reader").line("workspace") is None

    both = service(store, ("writer", "reader"))
    assert both.line("workspace") is not None
    assert both.line("workspace").used == 4
    assert total(store).line("workspace").used == 4


def test_context_network_and_communication_add_up() -> None:
    store = MemoryResourceStore()
    store.register_process("model-a", "model.openai_chat_model", None, "running")
    store.register_process("model-b", "model.openai_chat_model", None, "running")
    record_context(store, "model-a", occupied=30, ceiling=100, output_tokens=10)
    record_context(store, "model-a", occupied=40, ceiling=100, output_tokens=12)
    record_context(store, "model-b", occupied=5, ceiling=100, output_tokens=5)
    record_network(store, "model-a", sent=3, received=7, requests=1)
    record_network(store, "model-a", sent=1, received=1, requests=1)
    record_communication(store, "model-a", {"operation": "ping"})

    first = process(store, "model-a").line("context")
    assert first is not None
    assert first.used == 40
    assert first.ceiling == 100
    assert first.unit == "tokens"
    assert first.detail_of("output") == 22

    both = service(store, ("model-a", "model-b"))
    context = both.line("context")
    assert context is not None
    assert context.used == 45
    assert context.ceiling == 200
    assert context.detail_of("output") == 27
    network = both.line("network")
    assert network is not None
    assert network.used == 12
    assert network.detail_of("requests") == 2
    assert network.ceiling is None
    sent = len('{"operation": "ping"}'.encode("utf-8"))
    assert process(store, "model-a").line("communication").used == sent
    assert total(store).line("context").used == 45


def test_notes_round_trip_through_the_resource_section() -> None:
    section = ResourceSection(threading.RLock())
    section.save_page(
        Page(address="/proj/notes.txt", size=4, state=PageState.PINNED),
        PageLink(relation="self", resource_id="memory-1", handle="mem"),
    )
    section.add_note("writer", "network", {"sent": 2, "received": 3, "requests": 1})
    payload = section.export_part()
    restored = ResourceSection(threading.RLock())
    restored.import_part(payload)
    assert restored.note("writer", "network") == {"sent": 2, "received": 3, "requests": 1}
    assert restored.all_pages()[0][0].size == 4
