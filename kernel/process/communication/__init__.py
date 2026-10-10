"""Peer-to-peer channels. Process lifetime and leases stay outside this package."""

from kernel.process.communication.channel import Channel, ChannelOpen
from kernel.process.communication.registry import (
    channel_names,
    load_channel,
    open_channel,
    register_channel,
    unregister_channel,
)

__all__ = [
    "Channel",
    "ChannelOpen",
    "channel_names",
    "load_channel",
    "open_channel",
    "register_channel",
    "unregister_channel",
]
