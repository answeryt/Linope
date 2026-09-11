# -*- coding: utf-8 -*-

from __future__ import annotations

import asyncio
import gc
import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType

from kernel.compose.capability.assembly.context import ListenerResult
from kernel.compose.capability.assembly.file_loader import DriverManager
from kernel.compose.capability.assembly.file_loader import FileModuleLoader
from kernel.compose.capability.discovery.loader import inject_capabilities
from kernel.compose.capability.discovery.loader import kernel_capability_types

ROOT = Path(__file__).resolve().parents[2]


class ResourceContainerDiscoveryTest(unittest.TestCase):
    def test_discovery_finds_compose_runtime_stack(self) -> None:
        names = {item.name for item in kernel_capability_types()}
        self.assertIn("kernel_compose_definition", names)
        self.assertIn("kernel_compose_executor", names)
        self.assertIn("kernel_compose_binding", names)
        self.assertIn("kernel_compose_runtime", names)

    def test_inject_rejects_legacy_composition_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            composition = Path(directory) / "composition.yaml"
            composition.write_text("plugins: []\n", encoding="utf-8")
            with self.assertRaises(Exception) as raised:
                inject_capabilities(composition, repo=ROOT)
        self.assertIn("composition files are no longer supported", str(raised.exception))

    def test_resource_container_can_load_module_by_name(self) -> None:
        res = inject_capabilities(repo=ROOT)
        try:
            module = res.get("kernel_compose_definition")
            self.assertEqual(module.PLUGIN_NAME, "kernel_compose_definition")
        finally:
            res.unload()

    def test_listener_filter_exact_and_prefix(self) -> None:
        res = inject_capabilities(repo=ROOT)
        try:
            called: list[str] = []

            def exact_listener(res_container, broadcast):
                called.append("exact")
                res_container.provide("demo.exact", {"name": "exact"})
                return {"handled": True, "stop": True}

            def prefix_listener(_res_container, _broadcast):
                called.append("prefix")
                return ListenerResult(handled=True)

            def global_listener(_res_container, _broadcast):
                called.append("global")
                return False

            res.listen_capability(
                global_listener,
                name="global",
                priority=1,
                weak=False,
            )
            res.listen_capability(
                prefix_listener,
                name="prefix",
                priority=5,
                prefix="demo.",
                weak=False,
            )
            res.listen_capability(
                exact_listener,
                name="exact",
                priority=10,
                capability="demo.exact",
                weak=False,
            )
            lease = asyncio.run(res.request_async("demo.exact", owner="tester"))
            self.assertEqual(lease.capability, "demo.exact")
            self.assertEqual(called, ["exact"])
            self.assertEqual(res.get("demo.exact")["name"], "exact")
        finally:
            res.unload()

    def test_listener_lifecycle_events_and_context_manager(self) -> None:
        res = inject_capabilities(repo=ROOT)
        try:
            events: list[tuple[str, str, str]] = []

            def on_connected(event):
                events.append((event.event, event.name, event.reason))

            def on_disconnected(event):
                events.append((event.event, event.name, event.reason))

            res.listen_listener_connected(on_connected)
            res.listen_listener_disconnected(on_disconnected)

            def receiver(res_container, broadcast):
                if broadcast.capability == "life.demo":
                    res_container.provide("life.demo", True)

            with res.connected_listener(
                receiver,
                name="temp-receiver",
                capability="life.demo",
                priority=1,
                weak=False,
            ):
                lease = asyncio.run(res.request_async("life.demo"))
                self.assertEqual(lease.capability, "life.demo")

            self.assertIn(("connected", "temp-receiver", "explicit"), events)
            self.assertIn(("disconnected", "temp-receiver", "explicit"), events)
        finally:
            res.unload()

    def test_weak_listener_auto_disconnect(self) -> None:
        res = inject_capabilities(repo=ROOT)
        try:
            events: list[tuple[str, str]] = []

            def on_disconnected(event):
                events.append((event.name, event.reason))

            res.listen_listener_disconnected(on_disconnected)

            class Receiver:
                def __init__(self) -> None:
                    self.called = 0

                def callback(self, _res, _broadcast):
                    self.called += 1

            receiver = Receiver()
            res.listen_capability(
                receiver.callback,
                name="weak-receiver",
                capability="demo.weak",
                weak=True,
            )

            def strong_listener(res_container, broadcast):
                if broadcast.capability == "demo.weak":
                    res_container.provide("demo.weak", True)
                    return {"handled": True, "stop": True}
                return None

            res.listen_capability(
                strong_listener,
                name="strong-receiver",
                capability="demo.weak",
                weak=False,
            )

            del receiver
            gc.collect()

            lease = asyncio.run(res.request_async("demo.weak"))
            self.assertEqual(lease.capability, "demo.weak")
            self.assertIn(("weak-receiver", "garbage_collected"), events)
            listener_names = [item[0] for item in res.listeners()]
            self.assertNotIn("weak-receiver", listener_names)
        finally:
            res.unload()

    def test_muted_broadcast_skips_listeners(self) -> None:
        res = inject_capabilities(repo=ROOT)
        try:
            called = {"value": 0}

            def listener(_res_container, _broadcast):
                called["value"] += 1

            res.listen_capability(listener, name="mute-listener", weak=False)
            with res.muted_broadcast():
                lease = asyncio.run(res.request_async("compose.runtime"))
                self.assertEqual(lease.capability, "compose.runtime")
            self.assertEqual(called["value"], 0)
        finally:
            res.unload()

    def test_async_request_creates_lease_and_release_unloads_capability(self) -> None:
        res = inject_capabilities(repo=ROOT)
        try:
            lease = asyncio.run(
                res.request_async("compose.runtime", owner="test-owner", priority=1)
            )
            self.assertTrue(res.has_service("compose.runtime"))
            self.assertEqual(lease.capability, "compose.runtime")
            self.assertEqual(res.pending_requests(), ())

            released = res.release_lease(lease, eager=True)
            self.assertIn("kernel_compose_runtime:1.0", released)
            self.assertFalse(res.has_service("compose.runtime"))
        finally:
            res.unload()

    def test_shared_leases_keep_owner_alive_until_last_release(self) -> None:
        res = inject_capabilities(repo=ROOT)
        try:
            first = asyncio.run(res.request_async("compose.runtime", owner="first"))
            second = asyncio.run(res.request_async("compose.runtime", owner="second"))
            self.assertTrue(res.has_service("compose.runtime"))

            released_first = res.release_lease(first, eager=True)
            self.assertEqual(released_first, ())
            self.assertTrue(res.has_service("compose.runtime"))

            released_second = res.release_lease(second, eager=True)
            self.assertIn("kernel_compose_runtime:1.0", released_second)
            self.assertFalse(res.has_service("compose.runtime"))
        finally:
            res.unload()

    def test_collect_garbage_unloads_idle_owner(self) -> None:
        res = inject_capabilities(repo=ROOT)
        try:
            lease = asyncio.run(res.request_async("compose.runtime"))
            self.assertTrue(res.has_service("compose.runtime"))

            released = res.release_lease(lease, eager=False)
            self.assertEqual(released, ())
            self.assertTrue(res.has_service("compose.runtime"))

            collected = res.collect_garbage(max_idle_seconds=0.0)
            self.assertIn("kernel_compose_runtime:1.0", collected)
            self.assertFalse(res.has_service("compose.runtime"))
        finally:
            res.unload()

    def test_priority_controls_queue_order(self) -> None:
        res = inject_capabilities(repo=ROOT)
        try:
            observed: list[str] = []

            def inject(res_container, broadcast):
                observed.append(broadcast.capability)
                res_container.provide(broadcast.capability, broadcast.capability)
                return {"handled": True, "stop": True}

            res.listen_capability(inject, name="inject", priority=0, weak=False)

            async def run() -> tuple[str, str]:
                low = await res.submit_request("queue.low", priority=1)
                high = await res.submit_request("queue.high", priority=10)
                high_lease = await res.wait_request(high)
                low_lease = await res.wait_request(low)
                return high_lease.capability, low_lease.capability

            high_name, low_name = asyncio.run(run())
            self.assertEqual((high_name, low_name), ("queue.high", "queue.low"))
            self.assertEqual(observed[:2], ["queue.high", "queue.low"])
        finally:
            res.unload()

    def test_request_broadcast_carries_distributed_fields(self) -> None:
        res = inject_capabilities(repo=ROOT)
        try:
            captured = {}

            def inject(res_container, broadcast):
                captured["trace_id"] = broadcast.trace_id
                captured["idempotency_key"] = broadcast.idempotency_key
                captured["attempt"] = broadcast.attempt
                captured["max_attempts"] = broadcast.max_attempts
                res_container.provide("queue.trace", True)
                return {"handled": True, "stop": True}

            res.listen_capability(
                inject,
                name="trace",
                capability="queue.trace",
                weak=False,
            )
            lease = asyncio.run(
                res.request_async(
                    "queue.trace",
                    trace_id="trace-1",
                    idempotency_key="idem-1",
                    max_attempts=3,
                )
            )
            self.assertEqual(lease.capability, "queue.trace")
            self.assertEqual(captured["trace_id"], "trace-1")
            self.assertEqual(captured["idempotency_key"], "idem-1")
            self.assertEqual(captured["attempt"], 1)
            self.assertEqual(captured["max_attempts"], 3)
        finally:
            res.unload()

    def test_retry_and_dead_letter(self) -> None:
        res = inject_capabilities(repo=ROOT)
        try:
            called = {"value": 0}

            def failing(_res_container, _broadcast):
                called["value"] += 1
                raise RuntimeError("boom")

            res.listen_capability(
                failing,
                name="failing",
                capability="queue.fail",
                weak=False,
            )

            with self.assertRaises(RuntimeError):
                asyncio.run(
                    res.request_async(
                        "queue.fail",
                        max_attempts=3,
                        retry_backoff_seconds=0.0,
                    )
                )

            letters = res.dead_letters()
            self.assertEqual(called["value"], 3)
            self.assertEqual(len(letters), 1)
            self.assertEqual(letters[0].capability, "queue.fail")
            self.assertEqual(letters[0].attempt, 3)
            self.assertEqual(letters[0].reason, "RuntimeError")
        finally:
            res.unload()

    def test_cancel_pending_request(self) -> None:
        res = inject_capabilities(repo=ROOT)
        try:
            gate = asyncio.Event()

            async def inject(res_container, broadcast):
                if broadcast.capability == "queue.blocker":
                    await gate.wait()
                    res_container.provide("queue.blocker", True)
                    return {"handled": True, "stop": True}
                if broadcast.capability == "queue.waiting":
                    res_container.provide("queue.waiting", True)
                    return {"handled": True, "stop": True}
                return None

            res.listen_capability(inject, name="inject", priority=0, weak=False)

            async def run() -> None:
                blocker = await res.submit_request("queue.blocker", priority=10)
                waiting = await res.submit_request("queue.waiting", priority=1)
                blocker_task = asyncio.create_task(res.wait_request(blocker))
                await asyncio.sleep(0)
                cancelled = res.cancel_request(waiting, reason="manual-cancel")
                self.assertTrue(cancelled)
                with self.assertRaises(asyncio.CancelledError):
                    await res.wait_request(waiting)
                gate.set()
                await blocker_task

            asyncio.run(run())
        finally:
            res.unload()

    def test_submit_starts_worker_even_before_wait(self) -> None:
        res = inject_capabilities(repo=ROOT)
        try:
            def inject(res_container, broadcast):
                if broadcast.capability == "queue.auto":
                    res_container.provide("queue.auto", True)
                    return {"handled": True, "stop": True}
                return None

            res.listen_capability(
                inject,
                name="auto-worker",
                capability="queue.auto",
                weak=False,
            )

            async def run() -> None:
                ticket = await res.submit_request("queue.auto", priority=1)
                await asyncio.sleep(0.05)
                # Worker started by submit_request and already resolved capability.
                self.assertTrue(res.has_service("queue.auto"))
                lease = await res.wait_request(ticket)
                self.assertEqual(lease.capability, "queue.auto")

            asyncio.run(run())
        finally:
            res.unload()


class FileLoaderTest(unittest.TestCase):
    def test_file_loader_distinguishes_same_name_at_different_paths(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            for filename, marker in (("first.py", "first"), ("second.py", "second")):
                (repo / filename).write_text(
                    "PLUGIN_NAME = 'demo'\n"
                    f"MARKER = {marker!r}\n"
                    "def dispatch(*args, **kwargs):\n"
                    "    return MARKER\n",
                    encoding="utf-8",
                )
            loader = FileModuleLoader(repo)
            first = loader.load("socket:test", "demo", "first.py", required="dispatch")
            second = loader.load("socket:test", "demo", "second.py", required="dispatch")
            module_names = (first.__name__, second.__name__)
            self.assertIsNot(first, second)
            self.assertEqual((first.MARKER, second.MARKER), ("first", "second"))
            self.assertNotEqual(*module_names)
            loader.close()
        self.assertTrue(all(name not in sys.modules for name in module_names))

    def test_driver_load_failure_restores_previous_module(self) -> None:
        module_name = "_compose_test_restore"
        previous = ModuleType(module_name)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.py"
            path.write_text("PLUGIN_NAME = 'wrong'\n", encoding="utf-8")
            sys.modules[module_name] = previous
            try:
                with self.assertRaises(ValueError):
                    DriverManager.from_file(
                        "test",
                        "expected",
                        path,
                        module_name=module_name,
                    )
                self.assertIs(sys.modules[module_name], previous)
            finally:
                sys.modules.pop(module_name, None)


if __name__ == "__main__":
    unittest.main()
