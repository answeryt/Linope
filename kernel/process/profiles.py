"""Claims for peers that touch files or talk to other processes."""

from __future__ import annotations

import json
import os

from kernel.environment.mount import project_identity, root_from
from kernel.environment.sandbox_vocab import (
    DANGER_FULL_ACCESS,
    READ_ONLY,
    WORKSPACE_WRITE,
    check_mode,
    narrower,
)
from kernel.process.declaration import ProcessDeclaration, ResourceClaim
from kernel.resource.definition import ResourceKind


READ_TOOLS = frozenset({"read", "glob", "grep", "read_image"})
COMMAND_TOOLS = frozenset({"bash", "pwsh", "bash_persistent", "run_code"})


def tool_effect(capability_id: str) -> str:
    """Classify a tool as read, command, or write. Unknown tools stay write."""
    name = str(capability_id).split(".")[-1]
    if name in READ_TOOLS:
        return "read"
    if name in COMMAND_TOOLS or name == "terminal" or name.startswith("terminal_"):
        return "command"
    return "write"


def tool_allowed(
    capability: str,
    permission: str | None = None,
    capabilities: object = None,
) -> bool:
    """Whether one tool may be shown for a model permission and allow-list."""
    if not str(capability).startswith("tools."):
        return True
    short = str(capability).split(".", 1)[1]
    allowed = _names(capabilities)
    if allowed is not None and short not in allowed and capability not in allowed:
        return False
    if not permission:
        return True
    if check_mode(str(permission)) == READ_ONLY:
        return tool_effect(capability) == "read"
    return True


def tool_with_workspace(
    capability_id: str,
    changes,
    *,
    effect: str | None = None,
) -> ProcessDeclaration:
    """A file, shell, or terminal process leases a tool and a sandbox.

    A startup mode can narrow the tool, but it cannot rise above the tool's
    ceiling or above the current session mode.
    """
    root = root_from(changes, os.getcwd())
    chosen = effect or tool_effect(capability_id)
    mode = _mode(changes, chosen)
    return ProcessDeclaration(
        capability=capability_id,
        resources=(
            ResourceClaim(kind=ResourceKind.TOOL, identity={"id": capability_id}),
            ResourceClaim(
                kind=ResourceKind.SANDBOX,
                identity=project_identity(root),
                call_params={"mode": mode},
            ),
            ResourceClaim(
                kind=ResourceKind.NETWORK,
                identity={"channel": "ledger"},
            ),
        ),
    )


def tool_only(capability_id: str) -> ProcessDeclaration:
    """A tool without a sandbox. It can still be addressed on the ledger channel."""
    return ProcessDeclaration(
        capability=capability_id,
        resources=(
            ResourceClaim(kind=ResourceKind.TOOL, identity={"id": capability_id}),
            ResourceClaim(kind=ResourceKind.NETWORK, identity={"channel": "ledger"}),
        ),
    )


def current_session_mode() -> str | None:
    """The last sandbox/mode event for this project, if one was recorded."""
    from kernel.trace.journal import Journal, journal_path

    folder = os.environ.get("LINOPE_SESSION_ROOT") or None
    try:
        rows = Journal(journal_path(folder)).rows()
    except (OSError, json.JSONDecodeError):
        return None
    from kernel.environment.session_mode import effective_mode

    return effective_mode(rows)


def _mode(changes, effect: str) -> str:
    ceiling, default = _bounds(effect)
    requested = _requested(changes)
    session = current_session_mode()
    chosen = default if requested is None else requested
    if session is not None and requested is None:
        chosen = session
    chosen = narrower(chosen, ceiling)
    if session is not None:
        chosen = narrower(chosen, session)
    return chosen


def _bounds(effect: str) -> tuple[str, str]:
    if effect == "read":
        return READ_ONLY, READ_ONLY
    if effect not in {"write", "command"}:
        raise ValueError(f"Unknown tool capability: {effect}")
    return DANGER_FULL_ACCESS, WORKSPACE_WRITE


def _requested(changes) -> str | None:
    found = None
    for topic, raw in changes or ():
        if topic in {"mode", "permission"} and str(raw).strip():
            found = check_mode(str(raw))
    return found


def _names(capabilities: object) -> set[str] | None:
    if capabilities is None:
        return None
    if isinstance(capabilities, str):
        text = capabilities.strip()
        if not text:
            return set()
        return {item.strip() for item in text.split(",") if item.strip()}
    if isinstance(capabilities, (list, tuple, set)):
        return {str(item).strip() for item in capabilities if str(item).strip()}
    raise TypeError("capabilities must be a list of names")
