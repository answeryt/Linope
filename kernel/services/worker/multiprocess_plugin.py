# -*- coding: utf-8 -*-
"""Spawn one OS process per agent worker.

Target is injected (usually AgentApp.run wrapped for a fresh event loop).
"""

from __future__ import annotations

import logging
import multiprocessing
import os
import signal
import time
from collections.abc import Callable
from typing import Any


PLUGIN_NAME = "kernel_multiprocess"
PLUGIN_VERSION = "1.0"

SIGKILL: int | None = getattr(signal, "SIGKILL", None)


class WorkerSupervisor:
    """Parent process that keeps N worker children alive."""

    def __init__(
        self,
        target: Callable[..., Any],
        *,
        workers: int,
        args: tuple[Any, ...] = (),
        kwargs: dict[str, Any] | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        if workers < 1:
            raise ValueError("workers must be at least 1")
        if target is None:
            raise TypeError("target is required")
        self.target = target
        self.workers = workers
        self.args = args
        self.kwargs = dict(kwargs or {})
        self.logger = logger or logging.getLogger(PLUGIN_NAME)
        self.processes: list[multiprocessing.Process] = []
        self._should_exit = False

    @property
    def pid(self) -> int:
        return os.getpid()

    def run(self) -> None:
        self.startup()
        try:
            while not self._should_exit:
                if self.should_restart():
                    self.restart()
                time.sleep(0.5)
        except KeyboardInterrupt:
            self._should_exit = True
        finally:
            self.shutdown()

    def startup(self) -> None:
        self.logger.info("started parent process [%s]", self.pid)
        for worker_id in range(self.workers):
            process = self._start_one(worker_id)
            self.processes.append(process)

    def shutdown(self) -> None:
        for worker_id, process in enumerate(self.processes):
            if process.is_alive():
                process.terminate()
            self.logger.info("stopping child process %s [%s]", worker_id, process.pid)
            process.join(timeout=10)
            if process.is_alive():
                process.kill()
        self.logger.info("stopping parent process [%s]", self.pid)

    def restart(self) -> None:
        kept: list[multiprocessing.Process] = []
        for worker_id, process in enumerate(self.processes):
            if process.is_alive():
                kept.append(process)
                continue
            log_msg = "worker %s (pid:%s) exited with code %s"
            if (
                SIGKILL is not None
                and process.exitcode
                and abs(process.exitcode) == SIGKILL
            ):
                log_msg += " perhaps out of memory?"
            self.logger.error(log_msg, worker_id, process.pid, process.exitcode)
            kept.append(self._start_one(worker_id))
        self.processes = kept

    def should_restart(self) -> bool:
        return not all(process.is_alive() for process in self.processes)

    def _start_one(self, worker_id: int) -> multiprocessing.Process:
        kwargs = {**self.kwargs, "worker_id": worker_id}
        process = multiprocessing.Process(
            target=self.target,
            args=self.args,
            kwargs=kwargs,
            name=f"agent-worker-{worker_id}",
        )
        process.start()
        self.logger.info("started child process %s [%s]", worker_id, process.pid)
        return process
