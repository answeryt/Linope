"""In-process asynchronous execution and synchronous plugin bridges.

Submodules are intentionally imported explicitly to keep the process
activation/import graph acyclic.
"""

__all__ = ["ClaimedRequest", "ThreadInbox", "ThreadPolicy", "ThreadRuntime"]


def __getattr__(name: str):
    if name in {"ClaimedRequest", "ThreadInbox", "ThreadPolicy"}:
        from kernel.thread.contracts import ClaimedRequest, ThreadInbox, ThreadPolicy

        return {
            "ClaimedRequest": ClaimedRequest,
            "ThreadInbox": ThreadInbox,
            "ThreadPolicy": ThreadPolicy,
        }[name]
    if name == "ThreadRuntime":
        from kernel.thread.runtime import ThreadRuntime

        return ThreadRuntime
    raise AttributeError(name)
