"""The scheduler routes requests. It no longer admits work through an asyncio pool."""

import kernel.scheduler as scheduler
import kernel.thread as threads


def test_the_scheduler_exports_route_only() -> None:
    assert scheduler.__all__ == ["route"]
    assert "run_runtime" not in scheduler.__all__


def test_a_thread_is_a_task_with_its_own_program_counter() -> None:
    assert "Task" in threads.__all__
    assert "ThreadRuntime" not in threads.__all__
    assert "ThreadPolicy" not in threads.__all__
