# Current Status

Return to the [English homepage](README.md).

Development has been done on Windows. The code described below exists, but has not yet been run in a real environment on the corresponding machines, with a terminal opened, processes started, and an actual result observed.

## macOS and Linux

Neither platform has been tested in a real environment yet.

On Linux, the sandbox is designed to use `bwrap` followed by Landlock. On macOS, it is designed to use Seatbelt. See [capability/sandbox/sandbox-local](capability/sandbox/sandbox-local/README.md).

To determine whether a process is still alive, Linux reads `/proc/<pid>/stat` and uses it to match the start time. When this file is unavailable, the code can only tell whether the process exists; it cannot confirm that it is the original process. macOS usually does not have this file. See [kernel/process/process_manager/liveness.py](kernel/process/process_manager/liveness.py).

## Services and gRPC

The current “service” implementation records the pids of several already-running processes in `.linope/services.json`. It is a list, not a network connection. See [kernel/services/collection.py](kernel/services/collection.py).

The [bindings](bindings) directory also contains gRPC, NATS, and ZeroMQ transports. The kernel does not open them when starting services, and the code does not import `bindings` from `kernel`. When the corresponding libraries are not installed locally, [bindings/tests/test_transports.py](bindings/tests/test_transports.py) is skipped. A real one-message exchange between two processes over gRPC has not yet been completed.

`pip install linope` does not install `grpcio`, `nats-py`, or `pyzmq`. To use these three transports, install them separately and enable them yourself.

## Other Notes

A Docker workspace additionally requires `aiodocker`, and Docker must be installed on the machine. The default installation does not include it.

`memory` is context for the current run. When a process exits and its references are gone, the contents are unloaded. The ledger records the pid, resource type, and handle, but not message bodies. It is not yet a database that persists across sessions. The “Memory Lifecycle” section of the technical report describes this behavior.
