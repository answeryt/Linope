"""Receipts, assembled calls, and fencing checks."""

import os

from kernel.process.declaration import ProcessDeclaration, ResourceClaim
from kernel.process.process_manager.compose import Call, chain, chord, group
from kernel.process.process_manager.delegation import holding_exclusive
from kernel.process.process_manager.liveness import process_identity, process_matches
from kernel.process.process_manager.supervisor import wait_first
from kernel.process.reconcile import ProcessReconciler
from kernel.resource.definition import ResourceKind
from kernel.resource.pool import ResourcePool
from kernel.process.ledger import FileResourceStore

import pytest


def _declaration() -> ProcessDeclaration:
    return ProcessDeclaration(
        capability="context.sliding_window",
        resources=(
            ResourceClaim(
                kind=ResourceKind.CONTEXT,
                identity={"window": "default"},
            ),
        ),
    )


def test_submit_waits_on_the_receipt(tmp_path) -> None:
    pool = ResourcePool(FileResourceStore(tmp_path / "resources.json"))
    process = ProcessReconciler(pool).start(_declaration())
    try:
        receipt = process.submit({"operation": "ping"})
        reply = process.wait(receipt)
        assert reply["event"] == "pong"
        assert reply["request_id"] == receipt.request_id
    finally:
        process.stop()
        pool.store.close()


def test_group_and_chord_submit_new_work(tmp_path) -> None:
    pool = ResourcePool(FileResourceStore(tmp_path / "resources.json"))
    process = ProcessReconciler(pool).start(_declaration())
    try:
        receipts = group(
            (
                Call(process, {"operation": "ping"}),
                Call(process, {"operation": "ping"}),
            )
        )
        assert len(receipts) == 2
        ready = wait_first(receipts)
        assert ready
        final = chord(
            (Call(process, {"operation": "ping"}),),
            Call(process, {"operation": "ping"}),
        )
        assert process.wait(final)["event"] == "pong"
        followed = chain((Call(process, {"operation": "ping"}),))
        assert process.wait(followed)["event"] == "pong"
    finally:
        process.stop()
        pool.store.close()


def test_waiting_while_holding_another_process_is_refused(tmp_path) -> None:
    pool = ResourcePool(FileResourceStore(tmp_path / "resources.json"))
    process = ProcessReconciler(pool).start(_declaration())
    try:
        receipt = process.submit({"operation": "ping"})
        with holding_exclusive("other-process"):
            with pytest.raises(RuntimeError, match="独占进程"):
                process.wait(receipt)
    finally:
        process.stop()
        pool.store.close()


def test_authorize_rejects_a_revoked_handle(tmp_path) -> None:
    pool = ResourcePool(FileResourceStore(tmp_path / "resources.json"))
    process = ProcessReconciler(pool).start(_declaration())
    handle = process.activation.resource_context.grants[0].handle
    try:
        owner = process.activation.process_id
        pool.authorize(handle, owner)
        with pytest.raises(PermissionError, match="不属于"):
            pool.authorize(handle, "other-process")
        process.revoke(handle)
        with pytest.raises(PermissionError, match="旧凭证"):
            pool.authorize(handle, owner)
    finally:
        process.stop()
        pool.store.close()


def test_current_process_identity_matches() -> None:
    identity = process_identity(os.getpid())
    assert process_matches(os.getpid(), identity)
    assert process_matches(-1, identity) is False
