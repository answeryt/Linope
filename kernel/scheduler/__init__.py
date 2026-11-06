"""One scheduler for resource routing and thread admission."""

__all__ = ["route", "run_runtime"]


def __getattr__(name: str):
    if name == "route":
        from kernel.scheduler.route import route

        return route
    if name == "run_runtime":
        from kernel.scheduler.threads import run_runtime

        return run_runtime
    raise AttributeError(name)
