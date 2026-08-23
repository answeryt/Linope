# -*- coding: utf-8 -*-
"""Runnable agent worker: start the injected application and wait until exit.

Inject an AgentApplication (or any object with start/stop). This file does
not import the application plugin.
"""

from __future__ import annotations

import asyncio
import logging
import signal
from typing import Any


PLUGIN_NAME = "kernel_agent_app"
PLUGIN_VERSION = "1.0"


class AgentApp:
    """Process-level run loop for one agent worker."""

    def __init__(
        self,
        application: Any,
        *,
        logger: logging.Logger | None = None,
    ) -> None:
        if application is None:
            raise TypeError("application is required")
        self.application = application
        self.logger = logger or logging.getLogger(PLUGIN_NAME)
        self._should_exit = asyncio.Event()

    def exit(self) -> None:
        self._should_exit.set()

    def _install_signals(self) -> None:
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, self.exit)
            except (NotImplementedError, RuntimeError):
                return

    async def run(self, **start_options: Any) -> None:
        self._should_exit = asyncio.Event()
        self._install_signals()
        await self.application.start(**start_options)
        try:
            await self._should_exit.wait()
        except asyncio.CancelledError:
            self.exit()
            raise
        finally:
            await self.application.stop()
