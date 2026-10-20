"""Reconcile one resource declaration into a running capability process."""

from __future__ import annotations

import uuid
from dataclasses import replace

from kernel.process.declaration import ProcessDeclaration
from kernel.environment import HostExecutionPolicy, ProcessEnvironment
from kernel.environment.shell import api_key_names
from kernel.process.process_creat.activation import ProcessActivation
from kernel.process.process_creat.instances import CapabilityDefinition, describe_instance
from kernel.process.process_manager.capability_process import CapabilityProcess
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
        process_id: str | None = None,
        environment: ProcessEnvironment | None = None,
        host_policy: HostExecutionPolicy | None = None,
        thread_policy: ThreadPolicy | None = None,
        definition: CapabilityDefinition | None = None,
        shared: tuple[str, ...] = (),
        env_file: str = "",
        env_file_keys: tuple[str, ...] = (),
        cwd: str | None = None,
    ) -> CapabilityProcess:
        process_id = process_id or uuid.uuid4().hex
        if definition is None:
            definition = describe_instance(declaration.capability)
        if environment is None:
            chosen_file, chosen_keys = _env_selection(
                definition,
                env_file,
                env_file_keys,
            )
            if chosen_file or cwd:
                environment = ProcessEnvironment.current(
                    process_id=process_id,
                    capability_id=definition.instance_id,
                    cwd=cwd or None,
                    env_file=chosen_file,
                    env_file_keys=chosen_keys,
                )
        definition = replace(
            definition,
            resource_requirements=declaration.resource_definitions(),
        )
        compiled = compile_declaration(declaration, process_id, shared=shared)
        self.book.open(process_id, definition.instance_id)
        try:
            self.pool.bind(process_id, definition.instance_id, compiled)
        except BaseException:
            self.book.discard(process_id)
            raise
        try:
            grants = self.pool.grants_for(process_id)
            activation = ProcessActivation(
                definition=definition,
                grants=grants,
                process_id=process_id,
                settings=dict(declaration.settings),
                environment=environment,
                host_policy=host_policy or HostExecutionPolicy(),
                thread_policy=thread_policy or ThreadPolicy(),
            )
            self.book.attach(
                process_id,
                claims=tuple(
                    {"kind": kind_name(item.kind), "identity": dict(item.identity)}
                    for item in compiled
                ),
                leases=_held(grants, self.pool.store.active_for(process_id)),
                room=_room_facts(grants, environment),
            )
            return CapabilityProcess(
                activation,
                resource_pool=self.pool,
                book=self.book,
            )
        except BaseException:
            self.pool.release(process_id)
            self.book.discard(process_id)
            raise

    def launch(
        self,
        declaration: ProcessDeclaration,
        *,
        process_id: str | None = None,
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
        if process_id is not None and count != 1:
            raise ValueError("指定进程号时只能启动一份")
        started: list[CapabilityProcess] = []
        for index in range(count):
            started.append(
                self.start(
                    declaration,
                    process_id=process_id if index == 0 else None,
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

