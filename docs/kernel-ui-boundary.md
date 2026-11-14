# Kernel and UI boundary

The kernel owns process lifecycle, resource leases, scheduling, command
execution, and structured facts. It does not own terminal text, ANSI layout,
input locking, or transcript rendering. A process occupies the model scheduler
slot only when its declaration sets `settings.slot` to `model`. A context limit
is the integer in `settings.context_limit`; the kernel does not load a model
catalog to discover either fact. A sliding-window cut is asked from
`python -m capability.queries tail-cut`, not by importing a capability module.

`kernel.command.events.KernelEvent` is the host protocol. Events are versioned
and carry `request_id`, `turn_id`, `pid`, and `seq` where applicable. Command
values and failures are structured data. The command entry point serializes
these facts as JSONL; kernel services only depend on `EventSink`.

Capability stdout is an internal RPC stream. Capability notices, including
model deltas, are framed RPC events. Capability stderr is diagnostic input and
never becomes model transcript content.

The TUI validates the JSONL protocol, folds events through a pure reducer, and
passes the resulting state to the renderer. Replacing the TUI with a headless,
JSON, or web host does not require changing kernel scheduling or process
management.

The following are forbidden in kernel command code:

- terminal strings, ANSI escapes, or human-facing `print` calls;
- stdout capture used to recover nested command results;
- parsing `pid=` or other display text;
- uncorrelated completion or busy markers;
- forwarding capability stderr into the host transcript.
