from __future__ import annotations

import importlib.util
import inspect
import unittest
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]


def load(relative: str) -> Any:
    path = ROOT / relative
    spec = importlib.util.spec_from_file_location(path.stem, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


expression = load("kernel/process/continuation/expression_plugin.py")
continuation = load("kernel/process/continuation/continuation_plugin.py")
runtime = load("kernel/process/runtime/process_runtime_plugin.py")


class ContinuationExpressionTest(unittest.TestCase):
    def world(
        self,
        *,
        now: float = 10,
        created_at: float = 0,
        event: dict[str, Any] | None = None,
        events: list[dict[str, Any]] | None = None,
        latches: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "now": now,
            "created_at": created_at,
            "event": event,
            "events": list(events or ()),
            "latches": dict(latches or {}),
        }

    def test_logical_composition_is_canonical(self) -> None:
        left = expression.after(10) & expression.event("market.updated")
        right = expression.event("market.updated") & expression.after(10)
        self.assertEqual(left, right)
        self.assertEqual(left.to_dict(), right.to_dict())

    def test_once_latches_after_first_success(self) -> None:
        tree = expression.once(
            expression.event("ready") & ~expression.event("cancel")
        )
        first = expression.evaluate(
            tree,
            self.world(events=[{"type": "ready"}]),
        )
        self.assertTrue(first.value)
        self.assertTrue(first.latches)

        later = expression.evaluate(
            tree,
            self.world(
                events=[{"type": "ready"}, {"type": "cancel"}],
                latches=first.latches,
            ),
        )
        self.assertTrue(later.value)

        without_once = expression.evaluate(
            expression.event("ready") & ~expression.event("cancel"),
            self.world(events=[{"type": "ready"}, {"type": "cancel"}]),
        )
        self.assertFalse(without_once.value)

    def test_then_requires_event_order(self) -> None:
        tree = expression.then(
            expression.event("open"),
            expression.event("fill"),
        )
        fill_first = expression.evaluate(
            tree,
            self.world(events=[{"type": "fill"}]),
        )
        self.assertFalse(fill_first.value)

        opened = expression.evaluate(
            tree,
            self.world(
                events=[{"type": "fill"}, {"type": "open"}],
                latches=fill_first.latches,
            ),
        )
        self.assertFalse(opened.value)

        filled = expression.evaluate(
            tree,
            self.world(
                events=[{"type": "fill"}, {"type": "open"}, {"type": "fill"}],
                latches=opened.latches,
            ),
        )
        self.assertTrue(filled.value)

    def test_within_expires_after_deadline(self) -> None:
        tree = expression.within(5, expression.event("start"))
        pending = expression.evaluate(
            tree,
            self.world(now=3, created_at=0),
        )
        self.assertFalse(pending.value)
        self.assertEqual(5.0, pending.next_check_at)

        expired = expression.evaluate(
            tree,
            self.world(now=6, created_at=0),
        )
        self.assertFalse(expired.value)

        on_time = expression.evaluate(
            tree,
            self.world(
                now=4,
                created_at=0,
                events=[{"type": "start"}],
            ),
        )
        self.assertTrue(on_time.value)

    def test_new_primitive_does_not_change_continuation_record(self) -> None:
        registry = expression.default_primitives()

        def in_region(
            params: dict[str, Any], world: dict[str, Any]
        ) -> Any:
            event = world.get("event") or {}
            return expression.Evaluation(event.get("region") == params["region"])

        registry.register("space.in_region", in_region)
        where = expression.Expression(
            {
                "op": "primitive",
                "name": "space.in_region",
                "version": "1",
                "params": {"region": "asia"},
            }
        )
        when = expression.after(0) & where
        record = continuation.build_continuation(
            "process-1",
            "run-1",
            "execution-1",
            sequence=0,
            when=when,
            clock=lambda: 100.0,
        )
        names = [item["name"] for item in when.to_dict()["args"]]
        self.assertEqual({"time.after", "space.in_region"}, set(names))
        self.assertEqual(when.to_dict(), record["when"])

        ready = expression.evaluate(
            record["when"],
            self.world(
                now=100,
                created_at=100,
                event={"type": "location", "region": "asia"},
            ),
            primitives=registry,
        )
        self.assertTrue(ready.value)

    def test_boolean_context_is_rejected(self) -> None:
        with self.assertRaisesRegex(TypeError, "portable"):
            bool(expression.after(1))

    def test_legacy_continuation_parameters_are_removed(self) -> None:
        context_parameters = inspect.signature(
            runtime.ProcessContext.continuation
        ).parameters
        builder_parameters = inspect.signature(
            continuation.build_continuation
        ).parameters
        for name in ("delay", "wait_for", "schedule"):
            self.assertNotIn(name, context_parameters)
            self.assertNotIn(name, builder_parameters)
        with self.assertRaises(TypeError):
            continuation.build_continuation(
                "process-1",
                "run-1",
                "execution-1",
                sequence=0,
                delay=1,
            )


if __name__ == "__main__":
    unittest.main()
