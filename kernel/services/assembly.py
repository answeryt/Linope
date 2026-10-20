"""Turn a spec into a service handle."""

from __future__ import annotations

from kernel.process.resource_record import ProcessResourceBook, RecordStatus
from kernel.services.handle import ServiceHandle
from kernel.services.host import ServiceHost
from kernel.services.registry import load_blueprint
from kernel.services.spec import LaunchOptions, ServicePlan, ServiceSpec


class ServiceAssembler:
    """Spec -> plan -> handle."""

    def __init__(self, host: ServiceHost) -> None:
        self.host = host

    def open(self, spec: ServiceSpec, options: LaunchOptions) -> ServiceHandle:
        plan = load_blueprint(spec.kind).plan(spec)
        opened = _start_members(self.host, plan, options)
        return ServiceHandle(plan, opened)


def _start_members(host: ServiceHost, plan: ServicePlan, options: LaunchOptions):
    """Create one resource account for every member process."""
    from pathlib import Path

    from kernel.process.ledger import ProcessLedger
    from kernel.resource.lease import ResourceLeaseManager
    from kernel.resource.pool import ResourcePool

    pool = ResourcePool(ResourceLeaseManager())
    ledger_path = options.ledger_path or str(Path.cwd() / ".linope" / "processes.json")
    ledger = ProcessLedger(ledger_path)
    book = ProcessResourceBook(ledger)
    _reap_dead(book)
    reconciler = host.reconciler(pool)
    reconciler.book = book
    reconciler.pool.book = book
    opened = []
    try:
        for member in plan.members:
            declaration, definition = host.load_declaration(
                member.capability,
                member.changes,
            )
            from kernel.process.declaration import append_chosen

            declaration = append_chosen(declaration, options.chosen)
            processes = reconciler.launch(
                declaration,
                definition=definition,
                shared=options.shared,
                replica_count=member.replica_count,
                env_file=options.env_file,
                env_file_keys=options.env_file_keys,
                cwd=options.cwd,
                host_policy=options.host_policy,
                thread_policy=options.thread_policy,
            )
            opened.append((member, processes))
    except BaseException:
        for _member, processes in opened:
            for process in processes:
                process.stop()
        raise
    return tuple(opened)


def _reap_dead(book: ProcessResourceBook) -> None:
    """Close accounts whose operating-system process is already gone."""
    from kernel.process.process_manager.liveness import process_matches

    for record in book.records():
        if record.status != RecordStatus.READY or record.pid <= 0:
            continue
        if process_matches(record.pid, record.started or None):
            continue
        book.close(record.process_id)
