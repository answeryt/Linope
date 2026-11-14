"""The shape of one process leader or sibling task.

Processes and threads are tasks: each has its own program counter and
registers while sharing the resource ledger of one process. The model
scheduler can switch either without a second rule.
"""

from kernel.thread.task import Task, ThreadTable

__all__ = ["Task", "ThreadTable"]
