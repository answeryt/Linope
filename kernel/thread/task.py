"""Processes and threads are tasks in one thread group.

The process is the group leader task. Later threads are sibling tasks that
share the process's resource ledger. The model scheduler switches tasks and
does not ask whether the next one belongs to another process or thread.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


_STATE = {
    "idle": "idle",
    "ask_model": "ready",
    "using_model": "using_model",
    "wait_tool": "waiting",
    "wait_helpers": "waiting",
    "answer": "ready",
    "done": "done",
}


@dataclass
class Task:
    """One independently advancing line of execution.

    ``pid`` is this task's process id. ``tgid`` names the resource ledger
    shared by the task group. The ledger stays a list of borrowed memory,
    files, and network. The program counter and registers stay here.
    """

    id: str
    pid: int
    tgid: int = 0
    leader: bool = False
    program_counter: str = "idle"
    registers: dict[str, Any] = field(default_factory=dict)
    state: str = "idle"

    def __post_init__(self) -> None:
        if self.tgid <= 0:
            self.tgid = int(self.pid)
        if self.id == str(self.tgid):
            self.leader = True

    def move(self, program_counter: str, registers: dict[str, Any] | None = None, **items: Any) -> None:
        """Remember the next step and any small notes that step needs."""

        self.program_counter = str(program_counter or "idle")
        self.state = _STATE.get(self.program_counter, self.state)
        if registers:
            self.registers.update(registers)
        if items:
            self.registers.update(items)


class ThreadTable:
    """The tasks in one process's thread group.

    The first task is the process/thread-group leader and uses the process
    pid as its id. Sibling tasks use ``pid.sequence`` ids.
    """

    def __init__(self, pid: int, first_id: str = "") -> None:
        self.pid = int(pid)
        self._seq = 1
        self._items: dict[str, Task] = {}
        # ``first_id`` remains accepted for activation compatibility, but a
        # process leader always has the process pid as its task id.
        self.first = self.open(task_id=str(self.pid))

    def open(
        self,
        *,
        task_id: str = "",
        registers: dict[str, Any] | None = None,
        program_counter: str = "idle",
    ) -> Task:
        """Open one task that shares this process's resource ledger."""

        if task_id:
            ident = str(task_id)
        else:
            self._seq += 1
            ident = f"{self.pid}.{self._seq}"
        if ident != str(self.pid):
            suffix = ident.rsplit(".", 1)[-1]
            if suffix.isdigit():
                self._seq = max(self._seq, int(suffix))
        current = self._items.get(ident)
        if current is not None:
            current.move(program_counter, registers or {})
            return current
        task = Task(
            id=ident,
            pid=self.pid,
            tgid=self.pid,
            leader=ident == str(self.pid),
            program_counter=program_counter,
            registers=dict(registers or {}),
            state=_STATE.get(program_counter, "idle"),
        )
        self._items[ident] = task
        return task

    def get(self, task_id: str) -> Task | None:
        return self._items.get(str(task_id))

    def threads(self) -> tuple[Task, ...]:
        return tuple(self._items.values())

    def drop(self) -> None:
        self._items.clear()


_TABLES: dict[int, ThreadTable] = {}


def open_process_threads(pid: int, first_id: str = "") -> ThreadTable:
    """Create the leader task for a process. A second call returns its table."""

    pid = int(pid)
    current = _TABLES.get(pid)
    if current is not None:
        return current
    table = ThreadTable(pid, first_id=first_id)
    _TABLES[pid] = table
    return table


def threads_for(pid: int) -> ThreadTable | None:
    return _TABLES.get(int(pid))


def close_process_threads(pid: int) -> None:
    table = _TABLES.pop(int(pid), None)
    if table is not None:
        table.drop()


def ensure_threads(process: Any) -> ThreadTable:
    """The task group for a live process. A stand-in process gets one too."""

    table = getattr(process, "threads", None)
    if isinstance(table, ThreadTable):
        return table
    pid = _pid_of(process)
    found = _TABLES.get(pid) if pid else None
    if found is None:
        found = ThreadTable(pid)
        if pid:
            _TABLES[pid] = found
    try:
        process.threads = found
    except Exception:
        pass
    return found


def note_arrival(process: Any, body: Any) -> Task:
    """A user sentence lands on the process's leader task."""

    task = ensure_threads(process).first
    if isinstance(body, str) and body:
        task.registers["question"] = body
    if task.program_counter in {"", "idle", "done"}:
        task.move("ask_model")
    return task


def _pid_of(process: Any) -> int:
    pid = getattr(process, "pid", None)
    if pid:
        try:
            return int(pid)
        except (TypeError, ValueError):
            return 0
    activation = getattr(process, "activation", None)
    try:
        return int(getattr(activation, "pid", 0) or 0)
    except (TypeError, ValueError):
        return 0
