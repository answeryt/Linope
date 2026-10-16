"""Resource accounting for the whole machine, one service, and one process."""

from kernel.resource.account.embedded import admits, byte_ceiling, require_room
from kernel.resource.account.recorded import (
    record_communication,
    record_context,
    record_network,
    record_network_current,
)
from kernel.resource.account.report import Line, Report
from kernel.resource.account.view import process, service, total, workspace_room

__all__ = [
    "Line",
    "Report",
    "admits",
    "byte_ceiling",
    "process",
    "record_communication",
    "record_context",
    "record_network",
    "record_network_current",
    "require_room",
    "service",
    "total",
    "workspace_room",
]
