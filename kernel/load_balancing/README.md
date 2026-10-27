# load_balancing

English | [中文](README.cn.md)

A request names a resource kind and an identity. It does not name a pid or a thread. This directory reads the ledger for who still holds that resource and who can still take new work, then picks one. It does not take a lease. The call that sends the request is `route` in [`kernel/scheduler`](../scheduler/README.md). That function uses the choice, the extra worker, and the new process from here.

## Each script

`hints.py`

Lists the processes that still hold this resource, read from the ledger. The code calls one such row a `Seat`. It is that process's load right now: how many items are waiting, how many are already claimed, whether the context window is full, how long the last round trip took, and whether this resource may be shared. There is no second busy table. `one_resource` requires these processes to hold the same resource. Separate copies cannot be treated as one pool of work.

`pick.py`

Picks one process that can still take new work. Two or fewer candidates keep the one with less work on hand. More than two draws two at random and keeps the one with less work on hand. The order is claimed items, waiting items, latest round-trip time, then process id.

`process_scale.py`

Opens another peer process, or asks an idle peer to stop. `open_peer` calls the reconciler to open one, and refuses once the process count is at the ceiling. `close_idle` asks idle processes to stop and leaves at least the floor count. A process that still has work stays. A process that belongs to a service stays. `reconciler_opener` wraps one `reconciler.start` as the function that opens another process.

`workers.py`

A pool of peer threads. The ceiling can change while the pool is running. A thread is not written into the ledger address. Whoever is idle takes the work. `raise_on_process` raises one process's worker ceiling, up to the given cap. `raise_ceiling` and `lower_ceiling` move that ceiling by capability name.

`inflight.py`

How many model replies may be waited on at once. `sample` records one round trip and keeps the next allowance between the minimum and the maximum. A longer round trip tightens it. A shorter one lets it rise.

`relieve.py`

When [`kernel/calculate`](../calculate/README.md) reports pressure, raises that process's `worker_ceiling` by one. Several reasons at once still add only one. A missing record stays at 1.

`route.py`

Re-exports `kernel.scheduler.route`. The choice is not written in this file.

`__init__.py`

Exports `route` only.

## Known Limitations and Deferred Work

- **`relieve` has no helper cap of its own** — each time pressure holds, it adds one. The worker ceiling is enforced by `workers.raise_on_process` and `scheduler.route`.
