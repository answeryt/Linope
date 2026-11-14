"""Lines sent to a process that is already open in the runtime."""

from __future__ import annotations

from kernel.command.process.listen import PING_TIMEOUT, _one_line


def run(
    argv: list[str],
    *,
    runtime: object = None,
    request: dict[str, object] | None = None,
) -> int:
    """Hand one recognized line to the living runtime."""
    del argv
    target = runtime
    if target is None:
        raise RuntimeError("session_not_open")
    raw = str((request or {}).get("line") or "")
    handed, result = _one_line(
        target,
        raw,
        PING_TIMEOUT,
        emit_done=False,
        return_result=True,
    )
    if handed and result is not None and not getattr(target, "deferred", False):
        target.close_once(raw)
    return result
