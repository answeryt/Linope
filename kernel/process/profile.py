"""Ask a capability for its resource declaration. Do not read its card."""

from __future__ import annotations

from collections.abc import Sequence
from types import ModuleType
from typing import Any

PROFILE_NAME = "capability_profile"
Change = tuple[str, str]


class ProfileUnavailable(Exception):
    """The capability has no usable profile. Raised before the reconciler."""

    def __init__(self, capability_id: str) -> None:
        super().__init__(f"这个能力没有可用档案: {capability_id}")
        self.capability_id = capability_id


def declaration_from_modules(
    modules: Sequence[ModuleType],
    capability_id: str,
    changes: Sequence[Change],
) -> Any:
    """Return the declaration from the first capability_profile function."""
    forwarded = tuple(changes)
    for module in modules:
        profile = getattr(module, PROFILE_NAME, None)
        if not callable(profile):
            continue
        try:
            return profile(capability_id, forwarded)
        except ProfileUnavailable:
            raise
        except Exception as exc:
            raise ProfileUnavailable(capability_id) from exc
    raise ProfileUnavailable(capability_id)


def load_declaration(capability_id: str, changes: Sequence[Change]) -> tuple[Any, Any]:
    """Load one capability once, then ask it for a declaration."""
    from kernel.process.process_creat.instances import load_capability

    modules, definition = load_capability(capability_id)
    declaration = declaration_from_modules(modules, capability_id, changes)
    return declaration, definition
