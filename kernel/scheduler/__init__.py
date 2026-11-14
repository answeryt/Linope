"""One scheduler for resource routing. Model turns are tasks."""

__all__ = ["route"]


def __getattr__(name: str):
    if name == "route":
        from kernel.scheduler.route import route

        return route
    raise AttributeError(name)
