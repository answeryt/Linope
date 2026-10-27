"""One scheduler for model turns, pointer steps, resource routing, and thread admission."""

__all__ = ["classify", "route", "run_runtime", "turn"]


def __getattr__(name: str):
    if name == "turn":
        from kernel.scheduler.model_turn import turn

        return turn
    if name == "route":
        from kernel.scheduler.route import route

        return route
    if name == "run_runtime":
        from kernel.scheduler.threads import run_runtime

        return run_runtime
    if name == "classify":
        from kernel.scheduler.requests import classify

        return classify
    raise AttributeError(name)
