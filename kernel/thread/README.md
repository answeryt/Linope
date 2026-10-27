# thread

English | [中文](README.cn.md)

`kernel/thread` runs work inside one capability process. Async plugins are awaited on the process's event loop. Sync plugins, blocking SDKs, file operations, and external commands go to a worker pool so the loop can keep moving.

`process_id` is the identity outside the process. These scripts do not take a resource lease and do not read resource entity ids. The environment, resource handles, adapter, and `call_params` are the ones the process already prepared. Admission of the loop is [`run_runtime`](../scheduler/README.md) in `kernel/scheduler/threads.py`. The worker pool is [`kernel/load_balancing/workers.py`](../load_balancing/workers.py).

## Scripts

| Script | Role |
|---|---|
| `__init__.py` | Exports the public names when they are first used |
| `contracts.py` | The limits, one claimed request, and the inbox the runtime calls |
| `limiter.py` | How many requests may run at the same time |
| `runtime.py` | Runs one request: await an async plugin, or hand a sync plugin to the pool |

`__init__.py` exports `ThreadPolicy`, `ClaimedRequest`, `ThreadInbox`, and `ThreadRuntime` through `__getattr__`. The first use imports the module that defines the name, so importing this package does not pull the runtime into the process import graph.

`contracts.py` is the shapes.

`ThreadPolicy` is the set of numbers for one process. The defaults are one concurrent task and one sync worker. A value outside the allowed range is refused when the policy is built.

| Field | Default | Meaning |
|---|---|---|
| `max_concurrent_tasks` | 1 | How many requests may be in progress at once, async and sync together |
| `min_concurrent_tasks` | 1 | Stored with the policy. It must be at least 1 and no higher than the max. Admission in this directory uses the max and the ledger's inflight ceiling |
| `max_sync_workers` | 1 | How many OS threads the sync pool may use |
| `claim_lease_seconds` | 120 | Passed to `inbox.claim` as the lease time for one claim |
| `shutdown_timeout_seconds` | 5 | How long to wait for in-progress requests when the process is stopping |
| `poll_interval_seconds` | 0.05 | How long the loop sleeps when the inbox has nothing to claim |
| `session_affinity` | false | When true, requests with the same `session_id` run one after another |

`ClaimedRequest` is one request taken from the inbox: `request_id`, `process_id`, `body`, a new `claim_token`, and the `worker_id` that claimed it. `ThreadInbox` is the three calls the runtime uses. `claim` takes the next request for this process, or returns nothing. `complete` writes the reply back with that `claim_token`. `lookup` reads one request by id. The inbox implementation must make `claim` atomic for a process id. `ThreadAdapter` is the optional plugin shape: `handle` for a sync plugin.

`limiter.py` is `AsyncTaskLimiter`. It is an asyncio semaphore. `slot` takes one place before a request runs and gives it back when the request finishes. `expand_to` raises the cap. A lower number does not shrink the semaphore. `available` is how many places are free right now. The runtime builds it with `max_concurrent_tasks`.

`runtime.py` is `ThreadRuntime`. `run` hands the loop to `kernel.scheduler.threads.run_runtime`. That loop claims from the inbox, and calls back into this file to run each request, to align the caps, and to drain when the process asks to stop.

One request goes through `_execute_request`. It takes a limiter slot, then `_dispatch`:

| The message | What happens |
|---|---|
| `operation` is `ping` | Returns `pong` with this process's pid, the `seq`, and the `channel`. A `pid` in the message that is not this process is an error. |
| The adapter is async | `handle_async`, or `handle` when that is missing, is awaited on the loop. Waiting on the network does not take an OS worker. |
| The adapter is sync | `adapter.handle` runs on the `WorkerPool`. The pool must already be started. |
| There is no adapter | Returns an error, `This process has no load`. |

An async adapter is one with `is_async` set, or a coroutine `handle_async`. A sync adapter that is not marked `sync_thread_safe` gets at most one worker. An async adapter gets no sync workers.

After the first claim, `_align` reads `worker_ceiling` and `inflight_ceiling` from the process ledger. The inflight number, when it is at least 1, raises the limiter through `expand_to`. The worker number is applied with `set_max_workers`, after the sync-plugin cap above.

When `session_affinity` is on, requests that carry the same `session_id` share one lock, so the next one waits until the current one finishes.

`_drain` waits up to `shutdown_timeout_seconds` for the requests already running. Whatever is still running after that is cancelled, and the sync pool is shut down without waiting.
