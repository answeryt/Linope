"""Resource-hint load balancing. The public entry is route."""

__all__ = ["route"]


def __getattr__(name: str):
    if name == "route":
        from kernel.load_balancing.route import route

        return route
    raise AttributeError(name)
