"""Commands for selecting and using the model compute resource."""

from __future__ import annotations

import json
from typing import Any

from kernel.command.convention import UsageError, guard, parse

USAGE = (
    "usage: linope model cores <count>\n"
    "usage: linope model use <model capability> "
    "[--change topic=value]\n"
    "       linope model run -- <message or JSON request>"
)


@guard(USAGE)
def run(
    argv: list[str],
    *,
    runtime: Any = None,
    request: dict[str, Any] | None = None,
) -> Any:
    del request
    if not argv:
        raise UsageError(USAGE)
    from kernel.scheduler.model_scheduler.cores import get_cores

    resource = get_cores() if runtime is None else runtime.drive.cores
    if argv[0] == "cores":
        invocation = parse(argv[1:], flags={}, usage=USAGE)
        if len(invocation.position) != 1 or invocation.body is not None:
            raise UsageError(USAGE)
        if runtime is not None and runtime.drive.busy():
            raise RuntimeError("model_cores_busy")
        try:
            count = int(invocation.position[0])
        except ValueError as exc:
            raise UsageError("Model core count must be an integer") from exc
        return resource.set_count(count)
    if argv[0] == "use":
        invocation = parse(argv[1:], flags={"change": "repeat"}, usage=USAGE)
        if len(invocation.position) != 1 or invocation.body is not None:
            raise UsageError(USAGE)
        changes = tuple(
            _change(item) for item in invocation.options.get("change") or ()
        )
        return resource.use(
            invocation.position[0],
            changes,
            env_file=str(getattr(runtime, "_env_file", "") or ""),
        )
    if argv[0] == "run":
        invocation = parse(argv[1:], flags={}, usage=USAGE)
        if invocation.position or invocation.body is None:
            raise UsageError(USAGE)
        return resource.run(_body(invocation.body))
    raise UsageError(USAGE)


def _change(raw: str) -> tuple[str, str]:
    if "=" not in raw:
        raise UsageError("change is written as --change topic=value")
    topic, value = raw.split("=", 1)
    if not topic:
        raise UsageError("change is written as --change topic=value")
    return topic, value


def _body(raw: str) -> Any:
    text = str(raw)
    stripped = text.strip()
    if stripped.startswith(("{", "[")):
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            return text
    return text
