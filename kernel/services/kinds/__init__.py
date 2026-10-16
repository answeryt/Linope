"""Built-in service kinds. Importing this package registers them."""

from __future__ import annotations

from kernel.services.kinds.capability import CapabilityBlueprint
from kernel.services.kinds.mcp import McpBlueprint
from kernel.services.kinds.model import ModelBlueprint
from kernel.services.registry import register_service_kind

register_service_kind("capability", CapabilityBlueprint())
register_service_kind("model", ModelBlueprint())
register_service_kind("mcp", McpBlueprint())

__all__ = ["CapabilityBlueprint", "McpBlueprint", "ModelBlueprint"]
