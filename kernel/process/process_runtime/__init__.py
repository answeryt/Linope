"""Generic runtime for one Capability OS Process."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kernel.process.process_creat.activation import ProcessActivation
    from kernel.process.process_manager.lifecycle import ProcessStatus
    from kernel.process.process_manager.capability_process import CapabilityProcess

__all__ = ["CapabilityProcess", "ProcessActivation", "ProcessStatus"]


def __getattr__(name: str):
    """Resolve legacy exports lazily to avoid runtime/manager import cycles."""
    if name == "CapabilityProcess":
        from kernel.process.process_manager.capability_process import CapabilityProcess

        return CapabilityProcess
    if name == "ProcessActivation":
        from kernel.process.process_creat.activation import ProcessActivation

        return ProcessActivation
    if name == "ProcessStatus":
        from kernel.process.process_manager.lifecycle import ProcessStatus

        return ProcessStatus
    raise AttributeError(name)
