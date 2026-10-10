"""Assemble calls outside the capability plugin."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from kernel.process.process_manager.client import Receipt
from kernel.process.process_manager.supervisor import CapabilityProcess


@dataclass(frozen=True)
class Call:
    """One call that has not been submitted yet."""

    process: CapabilityProcess
    message: dict[str, Any]
    caller_id: str | None = None


def chain(calls: Sequence[Call], timeout: float = 10.0) -> Receipt:
    """Submit in order. The next message carries the previous receipt."""
    if not calls:
        raise ValueError("chain 至少要有一次调用")
    receipt: Receipt | None = None
    for call in calls:
        message = dict(call.message)
        if receipt is not None:
            message["prior"] = receipt
        receipt = call.process.submit(
            message,
            timeout=timeout,
            caller_id=call.caller_id,
        )
    assert receipt is not None
    return receipt


def group(calls: Sequence[Call], timeout: float = 10.0) -> tuple[Receipt, ...]:
    """Submit every call without waiting for the set to finish."""
    return tuple(
        call.process.submit(
            dict(call.message),
            timeout=timeout,
            caller_id=call.caller_id,
        )
        for call in calls
    )


def chord(
    calls: Sequence[Call],
    next_call: Call,
    timeout: float = 10.0,
) -> Receipt:
    """Wait for the group, then submit one new message with their results."""
    receipts = group(calls, timeout)
    results = [
        receipt.wait(timeout, caller_id=next_call.caller_id)
        for receipt in receipts
    ]
    message = dict(next_call.message)
    message["results"] = results
    return next_call.process.submit(
        message,
        timeout=timeout,
        caller_id=next_call.caller_id,
    )
