"""Capability contract helpers.

In this package, "contract" means 能力契约: a small code-level declaration of
what a capability provides, requires, and supports. It is not business/legal
contract data and it does not execute capability logic.

Leaf plugins must not import this package. They declare a literal
``MODEL_CAPABILITY`` dict; Host/Discovery validates that dict here.
"""

from .capability_contract import CapabilityContract
from .model_contract import model_capability
from .model_contract import model_fallback
from .model_contract import model_interface
from .model_contract import model_message
from .model_contract import model_parameter
from .model_contract import model_provider
from .model_contract import model_thread
from .model_contract import model_token

__all__ = [
    "CapabilityContract",
    "model_capability",
    "model_fallback",
    "model_interface",
    "model_message",
    "model_parameter",
    "model_provider",
    "model_thread",
    "model_token",
]
