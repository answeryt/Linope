"""Selected channel and published listen addresses."""

from __future__ import annotations

import threading
from typing import Any


class ChannelSection:
    """Which transport is selected, and where each process is listening."""

    name = "channel"
    flat_keys = ("channel", "endpoints")

    def __init__(self, lock: threading.RLock) -> None:
        self._lock = lock
        self._channel: tuple[str | None, dict[str, Any]] = (None, {})
        self._endpoints: dict[str, dict[str, str]] = {}

    def selected_channel(self) -> tuple[str | None, dict[str, Any]]:
        with self._lock:
            name, settings = self._channel
            return name, dict(settings)

    def select_channel(
        self,
        name: str | None,
        settings: dict[str, Any] | None = None,
    ) -> None:
        with self._lock:
            self._channel = (
                None if name in (None, "", "off") else str(name),
                dict(settings or {}),
            )

    def publish_endpoint(
        self,
        process_id: str,
        method: str,
        endpoint: str,
    ) -> None:
        with self._lock:
            self._endpoints[process_id] = {
                "method": method,
                "endpoint": endpoint,
            }

    def endpoint_for(self, process_id: str) -> str | None:
        with self._lock:
            found = self._endpoints.get(process_id)
            return None if found is None else found.get("endpoint")

    def export_part(self) -> dict[str, Any]:
        return {
            "channel": [self._channel[0], dict(self._channel[1])],
            "endpoints": {
                process_id: dict(endpoint)
                for process_id, endpoint in self._endpoints.items()
            },
        }

    def import_part(self, payload: dict[str, Any]) -> None:
        raw_channel = payload.get("channel") or [None, {}]
        self._channel = (
            raw_channel[0],
            dict(raw_channel[1] or {}) if len(raw_channel) > 1 else {},
        )
        self._endpoints.clear()
        self._endpoints.update(
            {
                str(key): dict(value)
                for key, value in (payload.get("endpoints") or {}).items()
            }
        )
