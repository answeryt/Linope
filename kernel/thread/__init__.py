"""Processes and threads are tasks with their own execution state.

Submodules are imported explicitly so loading this package does not pull a
process runtime into the import graph.
"""

__all__ = ["Task", "ThreadTable", "close_process_threads", "ensure_threads", "note_arrival", "open_process_threads"]


def __getattr__(name: str):
    if name in {"Task", "ThreadTable"}:
        from kernel.thread.task import Task, ThreadTable

        return {"Task": Task, "ThreadTable": ThreadTable}[name]
    if name in {"close_process_threads", "ensure_threads", "note_arrival", "open_process_threads"}:
        from kernel.thread import task as task_module

        return getattr(task_module, name)
    raise AttributeError(name)
