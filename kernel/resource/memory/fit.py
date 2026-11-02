"""Fit one already-named read into the remaining context budget."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from kernel.resource.memory.records import MemoryRow
from kernel.resource.memory.token_meter import estimate_tokens


Fitter = Callable[[list[MemoryRow], int], list[MemoryRow]]
_FITTER: Fitter | None = None


class ContextCapacity(RuntimeError):
    """The request that must be sent does not fit the model context."""


def register_fitter(fitter: Fitter | None) -> None:
    """Install a read-only advice function. It cannot write the store."""

    global _FITTER
    _FITTER = fitter


def fit_named_read(rows: list[MemoryRow], budget: int) -> tuple[list[MemoryRow], list[MemoryRow]]:
    """Return the rows that fit, then the rows left for another read.

    Address order is the kernel fallback. A registered fitter may reorder or
    shorten only this named read. Originals in the store are not replaced.
    """

    if budget <= 0 or not rows:
        return [], list(rows)
    total = sum(row.tokens or estimate_tokens(row.content) for row in rows)
    chosen = _advise(rows, budget) if total > budget else list(rows)
    kept: list[MemoryRow] = []
    used = 0
    for row in chosen:
        cost = row.tokens or estimate_tokens(row.content)
        if used + cost > budget:
            break
        kept.append(row)
        used += cost
    if not kept:
        return [], list(rows)
    kept_reals = {row.real for row in kept}
    left = [row for row in rows if row.real not in kept_reals]
    return kept, left


def _advise(rows: list[MemoryRow], budget: int) -> list[MemoryRow]:
    """Address order, unless a caller registered a fitter for this read."""

    if _FITTER is None:
        return list(rows)
    try:
        advised = list(_FITTER(list(rows), budget))
    except Exception:
        return list(rows)
    known = {row.real: row for row in rows}
    found: list[MemoryRow] = []
    for row in advised:
        source = known.get(row.real)
        if source is None:
            found.append(row)
            continue
        if row.content != source.content:
            found.append(
                MemoryRow(
                    real=source.real,
                    class_name=source.class_name,
                    kind=source.kind,
                    content=row.content,
                    time=source.time,
                    seq=source.seq,
                    state=source.state,
                    tokens=estimate_tokens(row.content),
                    version=source.version,
                )
            )
        else:
            found.append(source)
    return found or list(rows)


def sliding_window_fit(rows: list[MemoryRow], budget: int) -> list[MemoryRow]:
    """Use the existing tail cut when it imports. Original rows stay put."""

    from capability.context.context_compression.sliding_window.tail_token_cut import (
        find_tail_cut_by_tokens,
    )

    messages: list[dict[str, Any]] = [{"role": "user", "content": row.content} for row in rows]

    def estimate(message: dict[str, Any]) -> int:
        return estimate_tokens(message.get("content"))

    def same(_messages: list[dict[str, Any]], index: int) -> int:
        return index

    def keep(_messages: list[dict[str, Any]], cut: int, _head: int) -> int:
        return cut

    cut = find_tail_cut_by_tokens(
        messages,
        0,
        token_budget=max(1, budget),
        protect_last_n=1,
        estimate_message_tokens=estimate,
        align_boundary_backward=same,
        align_boundary_forward=same,
        ensure_last_user_message_in_tail=keep,
        ensure_last_assistant_message_in_tail=keep,
        min_tail_user_messages=1,
    )
    if cut <= 0:
        return list(rows)
    omitted = ", ".join(row.real for row in rows[:cut])
    summary = MemoryRow(
        real="summary",
        class_name="message",
        kind="model",
        content=f"Earlier rows remain stored: {omitted}",
        time=rows[0].time,
        seq=rows[0].seq,
        tokens=estimate_tokens(omitted),
    )
    return [summary, *rows[cut:]]
