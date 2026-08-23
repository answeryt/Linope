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
store_module = load("kernel/services/store/process_store_plugin.py")
queue_module = load("kernel/services/queue/run_queue_plugin.py")
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
            eager=eager,
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

        replay_activation = {
            "activation_id": "replay-after-crash",
            "process_type": "research",
            "process_id": first["process_id"],
            "input": "ignored-on-replay",
        }

        def simulate_crash(record: dict[str, Any]) -> dict[str, Any]:
            record.update(
                state="ready",
                outcome=None,
                result=None,
                error=None,
                pending_activations=[replay_activation],
                mailbox=[replay_activation],
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
