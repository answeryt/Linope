"""Reconcile one resource declaration into a running capability process."""

from __future__ import annotations

import uuid
from dataclasses import replace
from typing import cast

from kernel.process.declaration import ProcessDeclaration
from kernel.environment import HostExecutionPolicy, ProcessEnvironment
from kernel.environment.shell import api_key_names
from kernel.process.process_creat.activation import ProcessActivation
from kernel.process.process_creat.instances import CapabilityDefinition, describe_instance
from kernel.process.process_manager.replica_layout.layout import (
    RunningReplica,
    replica_label,
)
from kernel.process.process_manager.replica_layout.registry import load_layout

from kernel.process.process_manager.supervisor import CapabilityProcess
from kernel.communication.directory import selected_channel
from kernel.resource.compile import compile_declaration
from kernel.resource.pool import ResourcePool
from kernel.process.process_manager.ledger_contracts import ReconcileStore
from kernel.resource.store.locator import default_env_file
from kernel.thread.contracts import ThreadPolicy


class ProcessReconciler:
    """Compile a declaration, bind the pool, then spawn the process."""

    def __init__(self, pool: ResourcePool) -> None:
        self.pool = pool

    def start(
        self,
        declaration: ProcessDeclaration,
        *,
        process_id: str | None = None,
        environment: ProcessEnvironment | None = None,
        host_policy: HostExecutionPolicy | None = None,
        thread_policy: ThreadPolicy | None = None,
        definition: CapabilityDefinition | None = None,
        replica_name: str | None = None,
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
        store = cast(ReconcileStore, self.pool.store)
        shared = store.shares_capability(definition.instance_id)
        compiled = compile_declaration(
            declaration,
            process_id,
            shared=shared,
        )
        store.register_process(
            process_id,
            definition.instance_id,
            None,
            "starting",
        )
        try:
            self.pool.bind(process_id, definition.instance_id, compiled)
        except BaseException:
            store.update_process(process_id, status="failed", exit_code=None)
            raise
        try:
            channel_name, channel_settings = selected_channel(self.pool.store)
            activation = ProcessActivation(
                definition=definition,
                grants=self.pool.grants_for(process_id),
                process_id=process_id,
                settings=dict(declaration.settings),
                environment=environment,
                host_policy=host_policy or HostExecutionPolicy(),
                thread_policy=thread_policy or ThreadPolicy(),
                communication={
                    "name": channel_name or "ledger",
                    "settings": channel_settings,
                },
            )
            process = CapabilityProcess(activation, resource_pool=self.pool)
            process.ready_message = process.start()
            if replica_name is not None:
                store.set_replica_name(process_id, replica_name)
        except BaseException:
            self.pool.release(process_id)
            raise
        return process

    def launch(
        self,
        declaration: ProcessDeclaration,
        *,
        process_id: str | None = None,
        environment: ProcessEnvironment | None = None,
        host_policy: HostExecutionPolicy | None = None,
        thread_policy: ThreadPolicy | None = None,
        definition: CapabilityDefinition | None = None,
        replica_count: int | None = None,
        env_file: str = "",
        env_file_keys: tuple[str, ...] = (),
        cwd: str | None = None,
    ) -> tuple[CapabilityProcess, ...]:
        """Start the copies named by replica_count and the selected layout."""
        if definition is None:
            definition = describe_instance(declaration.capability)
        store = cast(ReconcileStore, self.pool.store)
        selected, settings = _selected_layout(store)
        if selected is None:
            if replica_count not in (None, 1):
                raise ValueError("还没选择布局，一次只能启动一份。先执行 linope layout")
            return (
                self.start(
                    declaration,
                    process_id=process_id,
                    environment=environment,
                    host_policy=host_policy,
                    thread_policy=thread_policy,
                    definition=definition,
                    env_file=env_file,
                    env_file_keys=env_file_keys,
                    cwd=cwd,
                ),
            )
        layout = load_layout(selected)
        _configure_layout(layout, settings, replica_count)
        running = _running_replicas(store, definition.instance_id)
        replica_plan = layout.plan_replicas(definition.instance_id, running)
        for replica in replica_plan.to_stop:
            store.set_desired(replica.process_id, "stop")
        started: list[CapabilityProcess] = []
        try:
            for spec in replica_plan.to_start:
                started.append(
                    self.start(
                        declaration,
                        process_id=spec.process_id,
                        environment=environment,
                        host_policy=host_policy,
                        thread_policy=thread_policy,
                        definition=definition,
                        replica_name=spec.replica_name,
                        env_file=env_file,
                        env_file_keys=env_file_keys,
                        cwd=cwd,
                    )
                )
        except BaseException:
            for process in started:
                process.stop()
            raise
        return tuple(started)


def _env_selection(
    definition: CapabilityDefinition,
    env_file: str,
    env_file_keys: tuple[str, ...],
) -> tuple[str, tuple[str, ...]]:
    """Pick the recorded secret file and only the key this capability names.

    A capability with no ``api_key_env`` does not receive the file. An
    explicit key list replaces the card name. Secret values are not read here.
    """
    chosen = env_file or default_env_file()
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


def _configure_layout(
    layout: object,
    settings: dict,
    replica_count: int | None,
) -> None:
    """Let each layout interpret launch settings without name-based branching."""
    configure = getattr(layout, "configure_launch", None)
    if configure is not None:
        configure(replica_count, settings)
        return
    if replica_count is not None:
        raise ValueError("这个布局不接受启动命令上的份数")
    apply_settings = getattr(layout, "apply_settings", None)
    if apply_settings is not None:
        apply_settings(settings)


def _apply_replica_count(
    name: str,
    layout: object,
    settings: dict,
    replica_count: int | None,
) -> None:
    """Compatibility alias for callers of the pre-registry helper."""
    if name == "counted" and hasattr(layout, "apply_settings"):
        count = 1 if replica_count is None else replica_count
        layout.apply_settings({"count": count})
        return
    _configure_layout(layout, settings, replica_count)


def _selected_layout(store: ReconcileStore) -> tuple[str | None, dict]:
    name, settings = store.selected_layout()
    if not name:
        return None, {}
    return str(name), dict(settings or {})


def _running_replicas(
    store: ReconcileStore,
    capability_id: str,
) -> tuple[RunningReplica, ...]:
    found: list[RunningReplica] = []
    for row in store.running_replicas(capability_id):
        replica_name = row["replica_name"] or ""
        if not replica_name:
            continue
        found.append(
            RunningReplica(
                capability=capability_id,
                replica_name=replica_name,
                label=replica_label(capability_id, replica_name),
                process_id=row["process_id"],
            )
        )
    return tuple(found)
