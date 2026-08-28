# -*- coding: utf-8 -*-
"""Replay-based durable Process engine composed only from injected plugins."""

from __future__ import annotations

import hashlib
import inspect
from collections.abc import Callable, Mapping, Sequence
from copy import deepcopy
from typing import Any
from uuid import uuid4


PLUGIN_NAME = "kernel_process_runtime"
PLUGIN_VERSION = "1.0"

_TERMINAL = frozenset({"terminated", "completed", "failed", "cancelled"})


class ReplayedCommandError(RuntimeError):
    """Fallback replay error used when the journal provides no error factory."""

    def __init__(self, error: Any) -> None:
        self.error = deepcopy(error)
        message = (
            str(error.get("message") or error.get("type") or "command failed")
            if isinstance(error, Mapping)
            else str(error)
        )
        super().__init__(message)


class ProcessFailedError(RuntimeError):
    """Fallback failed-Process error for the dependency-free handle."""

    def __init__(self, process_id: str, error: Any) -> None:
        self.process_id = process_id
        self.error = deepcopy(error)
        message = (
            str(error.get("message") or error.get("type") or "process failed")
            if isinstance(error, Mapping)
            else str(error or "process failed")
        )
        super().__init__(message)


class _ProcessBlocked(RuntimeError):
    pass


async def _await(value: Any) -> Any:
    return await value if inspect.isawaitable(value) else value


def wait(
    condition: Mapping[str, Any] | str,
    *,
    release: Sequence[str] = (),
    reason: str | None = None,
) -> dict[str, Any]:
    value = {"key": condition} if isinstance(condition, str) else dict(condition)
    return {
        "action": "wait",
        "condition": value,
        "release": list(release),
        "reason": reason,
    }


def complete(result: Any = None) -> dict[str, Any]:
    return {"action": "complete", "result": result}


class _ProcessHandle:
    def __init__(self, process_id: str, run_id: str, store: Any, engine: Any) -> None:
        self.process_id = process_id
        self.run_id = run_id
        self.store = store
        self.engine = engine

    def status(self) -> dict[str, Any]:
        require_run = getattr(self.store, "require_run", None)
        record = (
            dict(require_run(self.process_id, self.run_id))
            if callable(require_run)
            else self.engine._require(self.process_id)
        )
        if str(record.get("run_id")) != self.run_id:
            raise RuntimeError("handle run_id does not match stored Process run")
        return deepcopy(record)

    def done(self) -> bool:
        return str(self.status().get("state")) in _TERMINAL

    def result(self) -> Any:
        record = self.status()
        if not self.done():
            raise RuntimeError("process is not complete")
        if record.get("error") is not None:
            raise ProcessFailedError(self.process_id, record.get("error"))
        return deepcopy(record.get("result"))

    async def wait_result(self) -> Any:
        while not self.done():
            before = self.status()
            await self.engine.run_next(self.process_id)
            after = self.status()
            if before == after and str(after.get("state")) == "waiting":
                raise RuntimeError("process is waiting for an activation")
        return self.result()


class ProcessContext:
    """Deterministic command API rebuilt for every Process replay."""

    def __init__(
        self,
        engine: "ProcessEngine",
        process_run: Mapping[str, Any],
        definition: Mapping[str, Any],
        *,
        activation: Mapping[str, Any] | None = None,
        execution: Mapping[str, Any] | None = None,
    ) -> None:
        self.engine = engine
        self.process = dict(process_run)
        self.definition = dict(definition)
        self.activation = deepcopy(dict(activation or {}))
        self.execution = deepcopy(dict(execution or {}))
        self.command_index = int(self.execution.get("command_start") or 0)

    @property
    def process_id(self) -> str:
        return str(self.process["process_id"])

    @property
    def run_id(self) -> str:
        return str(self.process["run_id"])

    @property
    def execution_id(self) -> str:
        return str(self.execution["execution_id"])

    @property
    def execution_index(self) -> int:
        return int(self.execution["execution_index"])

    @property
    def initial_input(self) -> Any:
        return deepcopy(self.process.get("initial_input"))

    @property
    def state(self) -> dict[str, Any]:
        return deepcopy(self.process)

    async def run(self, task: Any, input: Any = None) -> Any:
        return await self._run_command(
            task,
            input,
            command_type="task",
            command_name=self.engine._task_name(task),
        )

    async def invoke(
        self, thread: str, interface: str, input: Any = None
    ) -> Any:
        target = self.engine._resolve_thread_interface(
            self.definition, str(thread), str(interface)
        )
        return await self._run_command(
            target,
            input,
            command_type="invoke",
            command_name=f"{thread}.{interface}",
        )

    async def start_process(
        self,
        process_type: str,
        input: Any = None,
        *,
        process_id: str | None = None,
        version: str | None = None,
    ) -> Any:
        index = self._next_index()
        child_id = process_id or self.engine._child_process_id(
            self.process_id,
            self.run_id,
            index,
            str(process_type),
        )
        command_input = {
            "process_type": str(process_type),
            "input": deepcopy(input),
            "process_id": child_id,
            "version": version,
        }
        command = self.engine.journal.append_command(
            self.process_id,
            self.run_id,
            index,
            "start_process",
            str(process_type),
            str(self.definition["version"]),
            command_input,
        )
        if command.get("status") == "failed":
            raise self.engine._replayed_error(command.get("error"))
        if command.get("status") == "completed":
            output = command.get("result") or {}
            return self.engine._make_handle(
                str(output["process_id"]), str(output["run_id"])
            )
        existing = self.engine._get(child_id)
        if existing is None:
            await self.engine.activate(
                {
                    "activation_id": self.engine._child_activation_id(
                        self.process_id, self.run_id, index
                    ),
                    "process_id": child_id,
                    "process_type": str(process_type),
                    "definition_version": version,
                    "input": deepcopy(input),
                    "caused_by": {
                        "process_id": self.process_id,
                        "run_id": self.run_id,
                        "command_index": index,
                    },
                }
            )
            existing = self.engine._require(child_id)
        elif str(existing.get("process_type")) != str(process_type):
            raise ValueError("deterministic child ID belongs to another process type")
        output = {
            "process_id": child_id,
            "run_id": str(existing["run_id"]),
        }
        self.engine.journal.complete_command(
            self.process_id, self.run_id, index, output
        )
        return self.engine._make_handle(child_id, output["run_id"])

    def wait(
        self,
        condition: Mapping[str, Any] | str,
        *,
        release: Sequence[str] = (),
        reason: str | None = None,
    ) -> dict[str, Any]:
        return wait(condition, release=release, reason=reason)

    def complete(self, result: Any = None) -> dict[str, Any]:
        return complete(result)

    def continuation(
        self,
        input: Any = None,
        *,
        reason: str | None = None,
        when: Any = None,
        priority: int = 0,
    ) -> dict[str, Any]:
        """Request another execution when an expression becomes true."""
        return {
            "action": "continuation",
            "input": deepcopy(input),
            "reason": reason,
            "when": deepcopy(when),
            "priority": int(priority),
        }

    async def _run_command(
        self,
        task: Any,
        input: Any,
        *,
        command_type: str,
        command_name: str,
    ) -> Any:
        index = self._next_index()
        prior = self.engine.journal.get_command(
            self.process_id, self.run_id, index
        )
        command = self.engine.journal.append_command(
            self.process_id,
            self.run_id,
            index,
            command_type,
            command_name,
            str(self.definition["version"]),
            input,
        )
        status = str(command.get("status") or "pending")
        if status == "completed":
            return deepcopy(command.get("result"))
        if status == "failed":
            raise self.engine._replayed_error(command.get("error"))
        if prior is not None:
            raise _ProcessBlocked(f"command {index} is still pending")
        try:
            result = await self.engine._execute_task(task, input, self)
        except BaseException as exc:
            self.engine.journal.fail_command(
                self.process_id, self.run_id, index, exc
            )
            raise
        self.engine.journal.complete_command(
            self.process_id, self.run_id, index, result
        )
        return deepcopy(result)

    def _next_index(self) -> int:
        index = self.command_index
        self.command_index += 1
        return index


class ProcessEngine:
    """Durable Process runner which replays functions from their first input."""

    def __init__(
        self,
        *,
        processes: Any,
        store: Any = None,
        journal: Any = None,
        queue: Any = None,
        task_executor: Any = None,
        lifecycle: Any = None,
        resources: Any = None,
        eager: bool = True,
        table: Any = None,
        handle_factory: Callable[..., Any] | None = None,
        continuation_builder: Callable[..., Mapping[str, Any]] | None = None,
        scheduler: Any = None,
    ) -> None:
        self.store = store if store is not None else table
        if self.store is None or journal is None or lifecycle is None:
            raise TypeError("store, journal, and lifecycle are required")
        self.table = self.store
        self.journal = journal
        self.queue = queue
        self.task_executor = task_executor
        self.lifecycle = lifecycle
        self.resources = resources
        self.eager = bool(eager)
        self.handle_factory = handle_factory
        self.continuation_builder = continuation_builder
        self.scheduler = scheduler
        self.processes = self._normalize_processes(processes)
        if not self.processes:
            raise ValueError("at least one process definition is required")

    async def activate(self, activation: Mapping[str, Any]) -> dict[str, Any]:
        payload = deepcopy(dict(activation))
        process_type = str(payload.get("process_type") or "")
        if not process_type:
            raise ValueError("activation requires process_type")
        requested_version = payload.get("definition_version")
        process_id = payload.get("process_id")
        current = self._get(str(process_id)) if process_id else None
        if current is not None:
            if str(current.get("state")) in _TERMINAL:
                raise RuntimeError("terminated process cannot be activated")
            if str(current.get("process_type")) != process_type:
                raise ValueError("activation process_type does not match existing process")
            stored_version = str(current.get("definition_version") or "1")
            if requested_version is not None and str(requested_version) != stored_version:
                raise ValueError("activation definition version does not match Process run")
            definition = self._definition(process_type, stored_version)
            activation_id = payload.get("activation_id")
            if activation_id is not None and str(activation_id) in {
                str(item) for item in (current.get("activation_ids") or ())
            }:
                return current
        else:
            definition = self._definition(
                process_type,
                None if requested_version is None else str(requested_version),
            )
            current = self.lifecycle.create(
                process_type,
                process_id=None if process_id is None else str(process_id),
                definition_version=str(definition["version"]),
                caused_by=payload.get("caused_by"),
                initial_input=deepcopy(payload.get("input")),
            )
            payload["process_id"] = current["process_id"]
        payload.setdefault("activation_id", uuid4().hex)
        current = self.lifecycle.activate(str(current["process_id"]), payload)
        if self.eager:
            return await self.run_next(str(current["process_id"]))
        await self._enqueue(payload)
        return current

    async def schedule_activation(
        self, activation: Mapping[str, Any]
    ) -> dict[str, Any]:
        """Persist and enqueue one Scheduler-approved internal Activation."""
        payload = deepcopy(dict(activation))
        process_id = str(payload.get("process_id") or "")
        process = self._require(process_id)
        if str(process.get("state")) in _TERMINAL:
            raise RuntimeError("terminated process cannot be activated")
        if str(payload.get("process_type") or "") != str(process["process_type"]):
            raise ValueError("activation process_type does not match existing process")
        if str(payload.get("definition_version") or "1") != str(
            process.get("definition_version") or "1"
        ):
            raise ValueError("activation definition version does not match Process run")
        current = self.lifecycle.activate(process_id, payload)
        await self._enqueue(payload)
        return current

    async def start_run(
        self,
        process_id: str,
        input: Any = None,
        *,
        version: str | None = None,
        activation_id: str | None = None,
    ) -> dict[str, Any]:
        """Start a new run for a completed logical Process."""
        previous = self._require(str(process_id))
        process_type = str(previous["process_type"])
        definition = self._definition(process_type, version)
        current = self.lifecycle.start_run(
            str(process_id),
            definition_version=str(definition["version"]),
            initial_input=deepcopy(input),
            caused_by={
                "process_id": str(process_id),
                "run_id": str(previous["run_id"]),
                "relation": "new_run",
            },
        )
        payload = {
            "activation_id": activation_id or uuid4().hex,
            "process_id": str(process_id),
            "process_type": process_type,
            "definition_version": str(definition["version"]),
            "input": deepcopy(input),
        }
        current = self.lifecycle.activate(str(process_id), payload)
        if self.eager:
            return await self.run_next(str(process_id))
        await self._enqueue(payload)
        return current

    async def run_next(self, process_id: str | None = None) -> dict[str, Any]:
        if process_id is None:
            dequeue = getattr(self.queue, "dequeue", None)
            if not callable(dequeue):
                raise TypeError("process_id is required when queue has no dequeue")
            queued = await _await(dequeue())
            if queued is None:
                raise LookupError("queue is empty")
            process_id = (
                str(queued.get("process_id"))
                if isinstance(queued, Mapping)
                else str(queued)
            )
        process = self._require(str(process_id))
        if str(process.get("state")) in _TERMINAL:
            return process
        definition = self._definition(
            str(process["process_type"]),
            str(process.get("definition_version") or "1"),
        )
        active = process.get("active_execution")
        if isinstance(active, Mapping):
            execution = deepcopy(dict(active))
            activation = deepcopy(dict(execution["activation"]))
        else:
            pending = [
                deepcopy(dict(item))
                for item in (
                    process.get("pending_activations")
                    or process.get("mailbox")
                    or ()
                )
            ]
            if not pending:
                return process
            activation = pending.pop(0)
            execution_index = int(process.get("next_execution_index") or 0)
            execution = {
                "execution_id": self._execution_id(
                    str(process["process_id"]),
                    str(process["run_id"]),
                    execution_index,
                    str(activation.get("activation_id") or ""),
                ),
                "execution_index": execution_index,
                "activation_id": str(activation.get("activation_id") or ""),
                "activation": deepcopy(activation),
                "command_start": int(process.get("next_command_index") or 0),
                "status": "running",
            }
            process["pending_activations"] = pending
            process["mailbox"] = deepcopy(pending)
            process["active_execution"] = deepcopy(execution)
            process["next_execution_index"] = execution_index + 1
            self._put(process)
            self._mark_continuation_consumed(activation)
        if str(process.get("state")) != "running":
            process = self.lifecycle.run(str(process_id))
        else:
            process = self._require(str(process_id))
        handler = definition.get("handler")
        if not callable(handler):
            raise TypeError("process handler must be callable")
        context = ProcessContext(
            self,
            process,
            definition,
            activation=activation,
            execution=execution,
        )
        try:
            outcome = await _await(
                handler(context, deepcopy(activation.get("input")))
            )
        except _ProcessBlocked as exc:
            return self.lifecycle.wait(
                str(process_id),
                condition={"command": context.command_index - 1},
                reason=str(exc),
            )
        except BaseException as exc:
            error = {
                "type": type(exc).__name__,
                "module": type(exc).__module__,
                "message": str(exc),
            }
            self._finish_execution(
                str(process_id), context, outcome="failed", error=error
            )
            return self.lifecycle.fail(
                str(process_id), reason=str(exc), error=error
            )
        commands = self.journal.list_commands(
            context.process_id, context.run_id
        )
        if len(commands) > context.command_index:
            error = {
                "type": "NonDeterminismError",
                "module": __name__,
                "message": (
                    "Process returned before replaying all recorded commands: "
                    f"consumed {context.command_index}, recorded {len(commands)}"
                ),
            }
            self._finish_execution(
                str(process_id), context, outcome="failed", error=error
            )
            return self.lifecycle.fail(
                str(process_id), reason=error["message"], error=error
            )
        return await self._apply_outcome(str(process_id), outcome, context)

    async def invoke(
        self,
        process_id: str,
        thread: str,
        function: str,
        input: Any = None,
    ) -> Any:
        process = self._require(process_id)
        definition = self._definition(
            str(process["process_type"]),
            str(process.get("definition_version") or "1"),
        )
        context = ProcessContext(self, process, definition)
        return await context.invoke(thread, function, input)

    async def _apply_outcome(
        self, process_id: str, outcome: Any, context: ProcessContext
    ) -> dict[str, Any]:
        action = (
            str(outcome.get("action") or "complete")
            if isinstance(outcome, Mapping) and "action" in outcome
            else "complete"
        )
        if action == "wait":
            self._finish_execution(
                process_id, context, outcome="waiting", result=outcome
            )
            return self.lifecycle.wait(
                process_id,
                condition=outcome.get("condition"),
                reason=outcome.get("reason"),
            )
        if action == "ready":
            self._finish_execution(
                process_id, context, outcome="ready", result=outcome
            )
            return self.lifecycle.resume(process_id)
        if action == "continuation":
            if self.continuation_builder is None or self.scheduler is None:
                raise RuntimeError(
                    "continuation_builder and scheduler are required"
                )
            continuation = dict(
                self.continuation_builder(
                    context.process_id,
                    context.run_id,
                    context.execution_id,
                    sequence=context.execution_index,
                    reason=outcome.get("reason"),
                    input=outcome.get("input"),
                    when=outcome.get("when"),
                    priority=int(outcome.get("priority") or 0),
                )
            )
            self._finish_execution(
                process_id,
                context,
                outcome="continuation",
                result={"continuation_id": continuation["continuation_id"]},
            )
            self.lifecycle.continuation(process_id, continuation)
            submit = getattr(self.scheduler, "submit", None)
            if not callable(submit):
                raise TypeError("scheduler must provide submit")
            await _await(submit(continuation))
            return self._require(process_id)
        if action != "complete":
            raise ValueError(f"unknown process action: {action}")
        result = (
            outcome.get("result")
            if isinstance(outcome, Mapping) and "action" in outcome
            else outcome
        )
        self._finish_execution(
            process_id, context, outcome="completed", result=result
        )
        return self.lifecycle.complete(process_id, result=result)

    def _finish_execution(
        self,
        process_id: str,
        context: ProcessContext,
        *,
        outcome: str,
        result: Any = None,
        error: Any = None,
    ) -> dict[str, Any]:
        updater = getattr(self.store, "update", None)
        if not callable(updater):
            raise TypeError("store must provide update for Process executions")

        def finish(record: dict[str, Any]) -> dict[str, Any]:
            active = record.get("active_execution")
            if not isinstance(active, Mapping):
                return record
            execution = deepcopy(dict(active))
            if str(execution.get("execution_id")) != context.execution_id:
                raise RuntimeError("active Process execution changed")
            execution["status"] = "completed"
            execution["outcome"] = str(outcome)
            execution["result"] = deepcopy(result)
            execution["error"] = deepcopy(error)
            execution["command_end"] = int(context.command_index)
            history = [
                deepcopy(dict(item)) for item in (record.get("executions") or ())
            ]
            history.append(execution)
            record["executions"] = history
            record["active_execution"] = None
            record["next_command_index"] = int(context.command_index)
            return record

        return dict(updater(process_id, finish))

    def _mark_continuation_consumed(
        self, activation: Mapping[str, Any]
    ) -> None:
        caused_by = activation.get("caused_by")
        if not isinstance(caused_by, Mapping):
            return
        continuation_id = caused_by.get("continuation_id")
        store = getattr(self.scheduler, "continuations", None)
        marker = getattr(store, "mark_consumed", None)
        if continuation_id is not None and callable(marker):
            marker(str(continuation_id))

    async def _execute_task(
        self, task: Any, input: Any, context: ProcessContext
    ) -> Any:
        execute = getattr(self.task_executor, "execute", None)
        if callable(execute):
            return await _await(
                execute(
                    task,
                    deepcopy(input),
                    context=context,
                    resources=self.resources,
                )
            )
        if not callable(task):
            raise TypeError("task_executor is required for non-callable tasks")
        try:
            signature = inspect.signature(task)
        except (TypeError, ValueError):
            return await _await(task(deepcopy(input)))
        if self._can_bind(signature, context, input):
            return await _await(task(context, deepcopy(input)))
        if self._can_bind(signature, input):
            return await _await(task(deepcopy(input)))
        if self._can_bind(signature):
            return await _await(task())
        raise TypeError(f"cannot invoke task {self._task_name(task)!r}")

    async def _enqueue(self, activation: Mapping[str, Any]) -> None:
        enqueue = getattr(self.queue, "enqueue", None)
        if callable(enqueue):
            payload = deepcopy(dict(activation))
            process_id = str(payload.get("process_id") or "")
            activation_id = str(payload.get("activation_id") or "")
            await _await(
                enqueue(
                    "process",
                    process_id,
                    payload=payload,
                    priority=int(payload.get("priority") or 0),
                    deduplication_key=(
                        f"activation:{activation_id}" if activation_id else None
                    ),
                )
            )

    def _definition(
        self, name: str, version: str | None = None
    ) -> dict[str, Any]:
        if version is None:
            versions = [
                item
                for (process_name, _), item in self.processes.items()
                if process_name == name
            ]
            if not versions:
                raise KeyError(f"unknown process type: {name}")
            return dict(versions[-1])
        item = self.processes.get((name, str(version)))
        if item is None:
            raise KeyError(f"unknown process type/version: {name}@{version}")
        if str(item.get("name")) != name or str(item.get("version")) != str(version):
            raise ValueError("Process definition name/version mismatch")
        return dict(item)

    @staticmethod
    def _normalize_processes(processes: Any) -> dict[tuple[str, str], dict[str, Any]]:
        values = getattr(processes, "values", None)
        if isinstance(processes, Mapping) and processes.get("handler"):
            items = [processes]
        elif callable(values):
            items = list(values())
        else:
            items = list(processes)
        normalized: dict[tuple[str, str], dict[str, Any]] = {}
        for source in items:
            if callable(source) and not isinstance(source, Mapping):
                attached = getattr(source, "__process_definition__", None)
                if not isinstance(attached, Mapping):
                    attached = {
                        "name": source.__name__,
                        "version": "1",
                        "handler": source,
                    }
                item = dict(attached)
            elif isinstance(source, Mapping):
                item = dict(source)
            else:
                raise TypeError("process definitions must be mappings or callables")
            name = str(item.get("name") or "")
            version = str(item.get("version") or "1")
            if not name or not callable(item.get("handler")):
                raise ValueError("Process definition requires name and handler")
            item["name"] = name
            item["version"] = version
            key = (name, version)
            if key in normalized:
                raise ValueError(f"duplicate Process definition: {name}@{version}")
            normalized[key] = item
        return normalized

    @staticmethod
    def _resolve_thread_interface(
        definition: Mapping[str, Any], thread: str, interface: str
    ) -> dict[str, Any]:
        for item in definition.get("threads") or ():
            if str(item.get("name")) != thread:
                continue
            contract = (item.get("interfaces") or {}).get(interface)
            handler = (item.get("handlers") or {}).get(interface)
            if isinstance(contract, Mapping) and callable(handler):
                selected = dict(item)
                selected["interfaces"] = {interface: dict(contract)}
                selected["handlers"] = {interface: handler}
                return selected
            break
        raise KeyError(f"unknown thread interface: {thread}.{interface}")

    @staticmethod
    def _task_name(task: Any) -> str:
        if isinstance(task, Mapping):
            return str(task.get("name") or type(task).__name__)
        return str(
            task
            if isinstance(task, str)
            else getattr(task, "name", None)
            or getattr(task, "__qualname__", None)
            or getattr(task, "__name__", None)
            or type(task).__name__
        )

    @staticmethod
    def _can_bind(signature: inspect.Signature, *args: Any) -> bool:
        try:
            signature.bind(*args)
        except TypeError:
            return False
        return True

    @staticmethod
    def _execution_id(
        process_id: str,
        run_id: str,
        execution_index: int,
        activation_id: str,
    ) -> str:
        material = (
            f"{process_id}\0{run_id}\0{execution_index}\0{activation_id}".encode()
        )
        return "execution_" + hashlib.sha256(material).hexdigest()[:32]

    @staticmethod
    def _child_process_id(
        process_id: str, run_id: str, index: int, child_name: str
    ) -> str:
        material = f"{process_id}\0{run_id}\0{index}\0{child_name}".encode()
        return "child_" + hashlib.sha256(material).hexdigest()[:32]

    @staticmethod
    def _child_activation_id(process_id: str, run_id: str, index: int) -> str:
        material = f"{process_id}\0{run_id}\0{index}\0activation".encode()
        return "activation_" + hashlib.sha256(material).hexdigest()[:32]

    def _replayed_error(self, error: Any) -> BaseException:
        factory = getattr(self.journal, "replayed_error", None)
        return factory(error) if callable(factory) else ReplayedCommandError(error)

    def _make_handle(self, process_id: str, run_id: str) -> Any:
        if self.handle_factory is not None:
            return self.handle_factory(
                process_id, run_id, store=self.store, engine=self
            )
        return _ProcessHandle(process_id, run_id, self.store, self)

    def _get(self, process_id: str) -> dict[str, Any] | None:
        getter = getattr(self.store, "get", None)
        if not callable(getter):
            raise TypeError("store must provide get")
        record = getter(process_id)
        return None if record is None else dict(record)

    def _require(self, process_id: str) -> dict[str, Any]:
        require = getattr(self.store, "require", None)
        if callable(require):
            return dict(require(process_id))
        record = self._get(process_id)
        if record is None:
            raise KeyError(process_id)
        return record

    def _put(self, record: Mapping[str, Any]) -> dict[str, Any]:
        stored = self.store.put(deepcopy(dict(record)))
        return dict(stored) if isinstance(stored, Mapping) else dict(record)


ProcessRuntime = ProcessEngine
