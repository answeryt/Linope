"""Translate message roles at the model vendor boundary.

Kernel storage uses ``user_msg``, ``model_msg``, ``tool_msg``, and
``system_msg``. OpenAI, Anthropic, and Gemini receive ``user``,
``assistant``, ``tool``, and ``system``. Gemini then names the model's
speech ``model``.
"""

from __future__ import annotations

_TO_VENDOR = {
    "user_msg": "user",
    "model_msg": "assistant",
    "tool_msg": "tool",
    "system_msg": "system",
}

_TO_KERNEL = {
    "user": "user_msg",
    "assistant": "model_msg",
    "model": "model_msg",
    "tool": "tool_msg",
    "system": "system_msg",
}


def vendor_role(role: object) -> str:
    """Role string a vendor request accepts. Kernel abbreviations are translated."""
    text = "" if role is None else str(role)
    return _TO_VENDOR.get(text, text)


def kernel_role(role: object) -> str:
    """Role string stored in the kernel. Vendor names are translated."""
    text = "" if role is None else str(role)
    if text in _TO_VENDOR:
        return text
    return _TO_KERNEL.get(text, text)
