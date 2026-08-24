from __future__ import annotations

import importlib.util
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


state = load("kernel/process/state/process_state_plugin.py")
lifecycle_module = load("kernel/process/lifecycle/process_lifecycle_plugin.py")
definition = load("kernel/process/definition/process_definition_plugin.py")
journal_module = load("kernel/process/journal/journal_plugin.py")
runtime_module = load("kernel/process/runtime/process_runtime_plugin.py")
handle_module = load("kernel/process/handle/process_handle_plugin.py")
continuation_module = load(
    "kernel/process/continuation/continuation_plugin.py"
)
expression_module = load(
    "kernel/process/continuation/expression_plugin.py"
)
store_module = load("kernel/services/store/process_store_plugin.py")
continuation_store_module = load(
    "kernel/services/store/continuation_store_plugin.py"
)
queue_module = load("kernel/services/queue/run_queue_plugin.py")
scheduler_module = load(
    "kernel/services/scheduler/continuation_scheduler_plugin.py"
)
worker_module = load("kernel/services/worker/process_worker_plugin.py")
service_module = load("kernel/services/app/service_plugin.py")
task_definition = load("kernel/thred/definition/task_definition_plugin.py")
task_executor_module = load("kernel/thred/executor/task_executor_plugin.py")


class ProcessRuntimeTest(unittest.IsolatedAsyncioTestCase):
    def make_runtime(
        self,
        handler: Any,
        *,
        process_name: str = "research",
        store: Any = None,
        journal: Any = None,
        queue: Any = None,
        eager: bool = True,
        with_scheduler: bool = False,
        clock: Any = None,
        policy: Any = None,
    ) -> Any:
        process_store = (
            store if store is not None else store_module.MemoryProcessStore()
        )
        process_journal = (
            journal if journal is not None else journal_module.InMemoryJournal()
        )
        lifecycle = lifecycle_module.ProcessLifecycle(
            process_store,
            transition=state.transition,
            build_process_run=state.build_process_run,
        )
        process = definition.define_process(process_name, handler)
        runtime = runtime_module.ProcessEngine(
            processes=[process],
            store=process_store,
            lifecycle=lifecycle,
            journal=process_journal,
            queue=queue,
            task_executor=task_executor_module.TaskExecutor(),
            handle_factory=handle_module.ProcessHandle,
            continuation_builder=(
                continuation_module.build_continuation
                if clock is None
                else lambda *args, **kwargs: continuation_module.build_continuation(
                    *args, clock=clock, **kwargs
                )
            ),
            eager=eager,
        )
        if with_scheduler:
            continuation_store = continuation_store_module.MemoryContinuationStore()
            runtime.scheduler = scheduler_module.ContinuationScheduler(
                continuations=continuation_store,
                processes=process_store,
                dispatch=runtime.schedule_activation,
                policy=policy,
                **({} if clock is None else {"clock": clock}),
            )
        return runtime

    async def test_process_function_gets_id_state_and_result(self) -> None:
        async def handler(ctx: Any, input_value: Any) -> dict[str, Any]:
            self.assertTrue(ctx.process_id)
            self.assertTrue(ctx.run_id)
            self.assertEqual("running", ctx.state["state"])
            return {"answer": input_value}

        runtime = self.make_runtime(handler)
        done = await runtime.activate(
            {
                "activation_id": "start-1",
                "process_type": "research",
                "input": "finished",
            }
        )

        self.assertEqual("terminated", done["state"])
        self.assertEqual("completed", done["outcome"])
        self.assertEqual({"answer": "finished"}, done["result"])
        self.assertTrue(done["process_id"])
        self.assertTrue(done["run_id"])

    async def test_new_run_keeps_process_identity_and_run_history(self) -> None:
        calls: list[str] = []

        async def handler(ctx: Any, input_value: Any) -> str:
            calls.append(str(input_value))
            return f"result:{input_value}"

        runtime = self.make_runtime(handler)
        first = await runtime.activate(
            {
                "activation_id": "first-run",
                "process_type": "research",
                "input": "one",
            }
        )
        first_handle = handle_module.ProcessHandle(
            first["process_id"],
            first["run_id"],
            store=runtime.store,
            engine=runtime,
        )

        second = await runtime.start_run(
            first["process_id"],
            "two",
            activation_id="second-run",
        )

        self.assertEqual(first["process_id"], second["process_id"])
        self.assertNotEqual(first["run_id"], second["run_id"])
        self.assertEqual(["one", "two"], calls)
        self.assertEqual("result:one", first_handle.result())
        self.assertEqual("result:two", runtime.store.require(first["process_id"])["result"])
        self.assertEqual(2, len(runtime.store.list_runs(first["process_id"])))
        self.assertEqual(
            second["run_id"],
            runtime.store.identity(first["process_id"])["current_run_id"],
        )

    async def test_new_run_rejects_active_process(self) -> None:
        async def handler(ctx: Any, input_value: Any) -> Any:
            return ctx.wait("approval")

        runtime = self.make_runtime(handler)
        waiting = await runtime.activate(
            {
                "activation_id": "waiting-run",
                "process_type": "research",
                "input": "one",
            }
        )

        with self.assertRaisesRegex(RuntimeError, "terminated"):
            await runtime.start_run(waiting["process_id"], "two")

    async def test_completed_task_is_replayed_without_reexecution(self) -> None:
        calls: list[str] = []

        @task_definition.task(name="model.call", version="1")
        async def model_call(value: Any) -> str:
            calls.append(str(value))
            return f"result:{value}"

        async def handler(ctx: Any, input_value: Any) -> str:
            return await ctx.run(model_call, input_value)

        store = store_module.MemoryProcessStore()
        journal = journal_module.InMemoryJournal()
        runtime = self.make_runtime(handler, store=store, journal=journal)
        first = await runtime.activate(
            {
                "activation_id": "replay-1",
                "process_type": "research",
                "input": "prompt",
            }
        )
        self.assertEqual(["prompt"], calls)

        def simulate_crash(record: dict[str, Any]) -> dict[str, Any]:
            execution = dict(record["executions"][0])
            execution.update(status="running", outcome=None, result=None, error=None)
            record.update(
                state="ready",
                outcome=None,
                result=None,
                error=None,
                active_execution=execution,
                executions=[],
                next_command_index=0,
                pending_activations=[],
                mailbox=[],
            )
            return record

        store.update(first["process_id"], simulate_crash)
        recovered = self.make_runtime(handler, store=store, journal=journal)
        replayed = await recovered.run_next(first["process_id"])

        self.assertEqual("terminated", replayed["state"])
        self.assertEqual("result:prompt", replayed["result"])
        self.assertEqual(["prompt"], calls)

    async def test_changed_command_is_rejected_as_nondeterministic(self) -> None:
        async def old_task(value: Any) -> str:
            return str(value)

        async def new_task(value: Any) -> str:
            return str(value)

        async def handler(ctx: Any, input_value: Any) -> str:
            return await ctx.run(new_task, input_value)

        runtime = self.make_runtime(handler)
        process = runtime.lifecycle.create(
            "research",
            definition_version="1",
            initial_input="value",
        )
        activation = {
            "activation_id": "nondeterminism-1",
            "process_id": process["process_id"],
            "process_type": "research",
            "input": "value",
        }
        runtime.lifecycle.activate(process["process_id"], activation)
        runtime.journal.append_command(
            process["process_id"],
            process["run_id"],
            0,
            "task",
            runtime._task_name(old_task),
            "1",
            "value",
        )
        runtime.journal.complete_command(
            process["process_id"], process["run_id"], 0, "old"
        )

        failed = await runtime.run_next(process["process_id"])
        self.assertEqual("failed", failed["outcome"])
        self.assertEqual("NonDeterminismError", failed["error"]["type"])

    async def test_duplicate_activation_does_not_advance_process(self) -> None:
        calls: list[str] = []

        async def handler(ctx: Any, input_value: Any) -> dict[str, Any]:
            calls.append(str(input_value))
            return ctx.wait("approval")

        runtime = self.make_runtime(handler)
        waiting = await runtime.activate(
            {
                "activation_id": "duplicate-1",
                "process_type": "research",
                "input": "start",
            }
        )
        duplicate = await runtime.activate(
            {
                "activation_id": "duplicate-1",
                "process_id": waiting["process_id"],
                "process_type": "research",
                "input": "start",
            }
        )

        self.assertEqual("waiting", duplicate["state"])
        self.assertEqual(["start"], calls)

    async def test_immediate_continuation_creates_next_execution(self) -> None:
        inputs: list[Any] = []

        async def handler(ctx: Any, input_value: Any) -> Any:
            inputs.append(input_value)
            if input_value == "start":
                return ctx.continuation(
                    {"round": 2},
                    reason="continue_research",
                )
            return {"finished": input_value}

        run_queue = queue_module.InMemoryRunQueue()
        runtime = self.make_runtime(
            handler,
            queue=run_queue,
            eager=False,
            with_scheduler=True,
        )
        ready = await runtime.activate(
            {
                "activation_id": "autonomous-start",
                "process_type": "research",
                "input": "start",
            }
        )
        worker = worker_module.ProcessWorker(
            queue=run_queue,
            runtime=runtime,
            worker_id="continuation-worker",
        )

        self.assertTrue(await worker.run_once())
        between = runtime.store.require(ready["process_id"])
        self.assertEqual("ready", between["state"])
        self.assertEqual(1, len(between["executions"]))
        continuation = runtime.scheduler.continuations.list()[0]
        self.assertEqual("dispatched", continuation["status"])

        self.assertTrue(await worker.run_once())
        done = runtime.store.require(ready["process_id"])
        self.assertEqual("terminated", done["state"])
        self.assertEqual(["start", {"round": 2}], inputs)
        self.assertEqual(2, len(done["executions"]))
        self.assertEqual(
            "consumed",
            runtime.scheduler.continuations.list()[0]["status"],
        )

    async def test_delayed_continuation_waits_for_scheduler_clock(self) -> None:
        now = [1_000.0]

        def clock() -> float:
            return now[0]

        async def handler(ctx: Any, input_value: Any) -> Any:
            if input_value == "start":
                return ctx.continuation(
                    "later", when=expression_module.after(10)
                )
            return input_value

        run_queue = queue_module.InMemoryRunQueue()
        runtime = self.make_runtime(
            handler,
            queue=run_queue,
            eager=False,
            with_scheduler=True,
            clock=clock,
        )
        ready = await runtime.activate(
            {"process_type": "research", "input": "start"}
        )
        worker = worker_module.ProcessWorker(
            queue=run_queue,
            runtime=runtime,
            worker_id="delay-worker",
        )
        self.assertTrue(await worker.run_once())
        self.assertEqual("waiting", runtime.store.require(ready["process_id"])["state"])
        self.assertEqual([], await runtime.scheduler.dispatch_ready())

        now[0] += 10
        dispatched = await runtime.scheduler.dispatch_ready()
        self.assertEqual(1, len(dispatched))
        self.assertTrue(await worker.run_once())
        self.assertEqual("later", runtime.store.require(ready["process_id"])["result"])

    async def test_event_continuation_requires_matching_event(self) -> None:
        async def handler(ctx: Any, input_value: Any) -> Any:
            if input_value == "start":
                return ctx.continuation(
                    "task-finished",
                    when=expression_module.once(
                        expression_module.task(
                            "task-123", state="completed"
                        )
                    ),
                )
            return input_value

        run_queue = queue_module.InMemoryRunQueue()
        runtime = self.make_runtime(
            handler,
            queue=run_queue,
            eager=False,
            with_scheduler=True,
        )
        ready = await runtime.activate(
            {"process_type": "research", "input": "start"}
        )
        worker = worker_module.ProcessWorker(
            queue=run_queue,
            runtime=runtime,
            worker_id="event-worker",
        )
        self.assertTrue(await worker.run_once())
        self.assertEqual(
            [],
            await runtime.scheduler.notify(
                {
                    "type": "task.completed",
                    "task_id": "other",
                    "state": "completed",
                }
            ),
        )
        dispatched = await runtime.scheduler.notify(
            {
                "type": "task.completed",
                "task_id": "task-123",
                "state": "completed",
            }
        )
        self.assertEqual(1, len(dispatched))
        self.assertTrue(await worker.run_once())
        self.assertEqual(
            "task-finished",
            runtime.store.require(ready["process_id"])["result"],
        )

    async def test_scheduler_policy_has_final_execution_authority(self) -> None:
        allowed = [False]

        def policy(_continuation: Any, _process: Any) -> bool:
            return allowed[0]

        async def handler(ctx: Any, input_value: Any) -> Any:
            if input_value == "start":
                return ctx.continuation("approved")
            return input_value

        run_queue = queue_module.InMemoryRunQueue()
        runtime = self.make_runtime(
            handler,
            queue=run_queue,
            eager=False,
            with_scheduler=True,
            policy=policy,
        )
        ready = await runtime.activate(
            {"process_type": "research", "input": "start"}
        )
        worker = worker_module.ProcessWorker(
            queue=run_queue,
            runtime=runtime,
            worker_id="policy-worker",
        )
        self.assertTrue(await worker.run_once())
        self.assertEqual("waiting", runtime.store.require(ready["process_id"])["state"])
        self.assertEqual(
            "pending",
            runtime.scheduler.continuations.list()[0]["status"],
        )

        allowed[0] = True
        self.assertEqual(1, len(await runtime.scheduler.dispatch_ready()))
        self.assertEqual([], await runtime.scheduler.dispatch_ready())
        self.assertTrue(await worker.run_once())
        self.assertEqual(
            "approved",
            runtime.store.require(ready["process_id"])["result"],
        )

    async def test_composed_expression_uses_once_and_negated_event(self) -> None:
        async def handler(ctx: Any, input_value: Any) -> Any:
            if input_value == "start":
                when = (
                    expression_module.after(10)
                    & expression_module.once(
                        expression_module.event("market.updated")
                    )
                    & ~expression_module.event("user.cancelled")
                )
                return ctx.continuation("go", when=when)
            return input_value

        now = [1_000.0]
        run_queue = queue_module.InMemoryRunQueue()
        runtime = self.make_runtime(
            handler,
            queue=run_queue,
            eager=False,
            with_scheduler=True,
            clock=lambda: now[0],
        )
        ready = await runtime.activate(
            {"process_type": "research", "input": "start"}
        )
        worker = worker_module.ProcessWorker(
            queue=run_queue,
            runtime=runtime,
            worker_id="expr-worker",
        )
        self.assertTrue(await worker.run_once())
        now[0] += 10
        self.assertEqual([], await runtime.scheduler.dispatch_ready())
        self.assertEqual(
            [],
            await runtime.scheduler.notify({"type": "user.cancelled"}),
        )
        self.assertEqual(
            [],
            await runtime.scheduler.notify({"type": "market.updated"}),
        )

        runtime_ok = self.make_runtime(
            handler,
            queue=run_queue,
            eager=False,
            with_scheduler=True,
            clock=lambda: now[0],
        )
        # Recreate an isolated process that has not seen cancel.
        ready = await runtime_ok.activate(
            {"process_type": "research", "input": "start"}
        )
        worker = worker_module.ProcessWorker(
            queue=run_queue,
            runtime=runtime_ok,
            worker_id="expr-worker-2",
        )
        self.assertTrue(await worker.run_once())
        now[0] += 10
        dispatched = await runtime_ok.scheduler.notify(
            {"type": "market.updated"}
        )
        self.assertEqual(1, len(dispatched))
        self.assertTrue(await worker.run_once())
        self.assertEqual(
            "go",
            runtime_ok.store.require(ready["process_id"])["result"],
        )

    async def test_then_expression_waits_for_ordered_events(self) -> None:
        async def handler(ctx: Any, input_value: Any) -> Any:
            if input_value == "start":
                return ctx.continuation(
                    "filled",
                    when=expression_module.then(
                        expression_module.event("open"),
                        expression_module.event("fill"),
                    ),
                )
            return input_value

        run_queue = queue_module.InMemoryRunQueue()
        runtime = self.make_runtime(
            handler,
            queue=run_queue,
            eager=False,
            with_scheduler=True,
        )
        ready = await runtime.activate(
            {"process_type": "research", "input": "start"}
        )
        worker = worker_module.ProcessWorker(
            queue=run_queue,
            runtime=runtime,
            worker_id="then-worker",
        )
        self.assertTrue(await worker.run_once())
        self.assertEqual(
            [],
            await runtime.scheduler.notify({"type": "fill"}),
        )
        self.assertEqual(
            [],
            await runtime.scheduler.notify({"type": "open"}),
        )
        dispatched = await runtime.scheduler.notify({"type": "fill"})
        self.assertEqual(1, len(dispatched))
        self.assertTrue(await worker.run_once())
        self.assertEqual(
            "filled",
            runtime.store.require(ready["process_id"])["result"],
        )

    async def test_continuation_executions_use_distinct_command_indexes(self) -> None:
        @task_definition.task(name="round.task", version="1")
        async def run_round(value: Any) -> Any:
            return value

        async def handler(ctx: Any, input_value: Any) -> Any:
            result = await ctx.run(run_round, input_value)
            if result == 1:
                return ctx.continuation(2)
            return result

        run_queue = queue_module.InMemoryRunQueue()
        journal = journal_module.InMemoryJournal()
        runtime = self.make_runtime(
            handler,
            journal=journal,
            queue=run_queue,
            eager=False,
            with_scheduler=True,
        )
        ready = await runtime.activate(
            {"process_type": "research", "input": 1}
        )
        worker = worker_module.ProcessWorker(
            queue=run_queue,
            runtime=runtime,
            worker_id="command-worker",
        )
        self.assertTrue(await worker.run_once())
        self.assertTrue(await worker.run_once())

        done = runtime.store.require(ready["process_id"])
        commands = journal.list_commands(done["process_id"], done["run_id"])
        self.assertEqual([0, 1], [item["command_index"] for item in commands])
        self.assertEqual(2, done["result"])

    async def test_non_eager_activation_runs_through_leased_queue_worker(self) -> None:
        async def handler(ctx: Any, input_value: Any) -> str:
            return f"queued:{input_value}"

        run_queue = queue_module.InMemoryRunQueue()
        runtime = self.make_runtime(handler, queue=run_queue, eager=False)
        ready = await runtime.activate(
            {
                "activation_id": "queue-1",
                "process_type": "research",
                "input": "work",
            }
        )
        worker = worker_module.ProcessWorker(
            queue=run_queue,
            runtime=runtime,
            worker_id="worker-1",
        )

        self.assertEqual("ready", ready["state"])
        self.assertTrue(await worker.run_once())
        done = runtime.store.require(ready["process_id"])
        self.assertEqual("terminated", done["state"])
        self.assertEqual("queued:work", done["result"])
        self.assertEqual("ACKED", run_queue.list()[0]["state"])

    async def test_agent_is_service_plus_resources(self) -> None:
        async def handler(ctx: Any, input_value: Any) -> Any:
            return input_value

        runtime = self.make_runtime(handler)
        process = definition.define_process("research", handler)
        service = service_module.define_service(
            "research-service",
            processes=[process],
            runtime=runtime,
        )
        resources = object()
        agent = service_module.assemble_agent(
            service=service,
            resources=resources,
        )
        result = await agent.activate(
            {"process_type": "research", "input": "ok"}
        )

        self.assertEqual("ok", result["result"])
        self.assertIs(resources, agent.resources)


if __name__ == "__main__":
    unittest.main()
