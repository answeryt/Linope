"""Reconcile one resource declaration into a running capability process."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from kernel.process.declaration import ProcessDeclaration
from kernel.environment import HostExecutionPolicy, ProcessEnvironment
from kernel.environment.shell import api_key_names
from kernel.process.process_creat.activation import ProcessActivation
from kernel.process.process_creat.instances import CapabilityDefinition, describe_instance
from kernel.process.process_manager.capability_process import CapabilityProcess, spawn_runtime
from kernel.process.resource_record import (
    ProcessResourceBook,
    held_from_grant,
)
from kernel.resource.compile import compile_declaration
from kernel.resource.pool import ResourcePool
from kernel.resource.resource_contract import kind_name
from kernel.thread.contracts import ThreadPolicy


class ProcessReconciler:
    """Compile a declaration, bind the pool, then spawn the process."""

    def __init__(self, pool: ResourcePool, book: ProcessResourceBook | None = None) -> None:
        self.pool = pool
        self.book = book if book is not None else ProcessResourceBook()
        self.pool.book = self.book

    def start(
        self,
        declaration: ProcessDeclaration,
        *,
        pid: int | None = None,
        environment: ProcessEnvironment | None = None,
        host_policy: HostExecutionPolicy | None = None,
        thread_policy: ThreadPolicy | None = None,
        definition: CapabilityDefinition | None = None,
        shared: tuple[str, ...] = (),
        env_file: str = "",
        env_file_keys: tuple[str, ...] = (),
        cwd: str | None = None,
    ) -> CapabilityProcess:
        if definition is None:
            definition = describe_instance(declaration.capability)
        chosen_file = ""
        chosen_keys: tuple[str, ...] = ()
        if environment is None:
            chosen_file, chosen_keys = _env_selection(
                definition,
                env_file,
                env_file_keys,
            )
        elif environment.env_file_keys:
            chosen_keys = tuple(environment.env_file_keys)
        child = None
        opened = False
        bound = False
        process: CapabilityProcess | None = None
        pid_value = None if pid is None else int(pid)
        try:
            if pid_value is None:
                child = spawn_runtime(chosen_keys)
                pid_value = int(child.pid or 0)
                if pid_value <= 0:
                    raise RuntimeError("这个能力的程序没有进程号")
            if environment is None and (chosen_file or cwd):
                environment = ProcessEnvironment.current(
                    pid=pid_value,
                    capability_id=definition.instance_id,
                    cwd=cwd or None,
                    env_file=chosen_file,
                    env_file_keys=chosen_keys,
                )
            definition = replace(
                definition,
                resource_requirements=declaration.resource_definitions(),
            )
            compiled = compile_declaration(declaration, pid_value, shared=shared)
            self.book.open(pid_value, definition.instance_id)
            opened = True
            self.pool.bind(pid_value, definition.instance_id, compiled)
            bound = True
            grants = self.pool.grants_for(pid_value)
            thread_policy = thread_policy or ThreadPolicy()
            activation = ProcessActivation(
                definition=definition,
                grants=grants,
                pid=pid_value,
                settings=dict(declaration.settings),
                environment=environment,
                host_policy=host_policy or HostExecutionPolicy(),
                thread_policy=thread_policy,
            )
            room = _room_facts(grants, environment)
            room["worker_ceiling"] = thread_policy.max_sync_workers
            room["inflight_ceiling"] = thread_policy.max_concurrent_tasks
            self.book.attach(
                pid_value,
                claims=tuple(
                    {"kind": kind_name(item.kind), "identity": dict(item.identity)}
                    for item in compiled
                ),
                leases=_held(grants, self.pool.store.active_for(pid_value)),
                room=room,
            )
            process = CapabilityProcess(
                activation,
                resource_pool=self.pool,
                book=self.book,
                child=child,
            )
            if child is not None:
                process.open_program()
            return process
        except BaseException:
            if process is not None and process._secret_copy:
                Path(process._secret_copy).unlink(missing_ok=True)
                process._secret_copy = ""
            if child is not None and child.poll() is None:
                child.kill()
            if bound and pid_value is not None:
                self.pool.release(pid_value)
            if opened and pid_value is not None:
                self.book.discard(pid_value)
            raise

    def launch(
        self,
        declaration: ProcessDeclaration,
        *,
        pid: int | None = None,
        environment: ProcessEnvironment | None = None,
        host_policy: HostExecutionPolicy | None = None,
        thread_policy: ThreadPolicy | None = None,
        definition: CapabilityDefinition | None = None,
        shared: tuple[str, ...] = (),
        replica_count: int | None = None,
        env_file: str = "",
        env_file_keys: tuple[str, ...] = (),
        cwd: str | None = None,
    ) -> tuple[CapabilityProcess, ...]:
        """Start the explicit number of independent capability processes."""
        if definition is None:
            definition = describe_instance(declaration.capability)
        count = 1 if replica_count is None else int(replica_count)
        if count < 1:
            raise ValueError("份数至少为 1")
        if pid is not None and count != 1:
            raise ValueError("指定进程号时只能启动一份")
        started: list[CapabilityProcess] = []
        for index in range(count):
            started.append(
                self.start(
                    declaration,
                    pid=pid if index == 0 else None,
                    environment=environment,
                    host_policy=host_policy,
                    thread_policy=thread_policy,
                    definition=definition,
                    shared=shared,
                    env_file=env_file,
                    env_file_keys=env_file_keys,
                    cwd=cwd,
                )
            )
        return tuple(started)


def _held(grants, leases):
    by_resource = {lease.resource_id: lease for lease in leases}
    return tuple(
        held_from_grant(grant, by_resource[grant.resource_id]) for grant in grants
    )


def _room_facts(grants, environment) -> dict:
    mode = "workspace-write"
    channel = ""
    for grant in grants:
        name = kind_name(grant.kind)
        if name == "sandbox":
            mode = str(grant.call_params.get("mode") or mode)
        elif name == "network":
            identity = (grant.metadata or {}).get("identity") or {}
            channel = str(identity.get("channel") or "")
    return {
        "mode": mode,
        "channel": channel,
    }


def _env_selection(
    definition: CapabilityDefinition,
    env_file: str,
    env_file_keys: tuple[str, ...],
) -> tuple[str, tuple[str, ...]]:
    """Pick the recorded secret file and only the key this capability names.

    A capability with no ``api_key_env`` does not receive the file. An
    explicit key list replaces the card name. Secret values are not read here.
    """
    chosen = env_file
    if not chosen:
        if env_file_keys:
            raise ValueError("还没指定环境文件，不能选择键")
        return "", ()
    if env_file_keys:
        return chosen, env_file_keys
    names = api_key_names(tuple(definition.module_paths))
    if not names:
        return "", ()
    return chosen, names

