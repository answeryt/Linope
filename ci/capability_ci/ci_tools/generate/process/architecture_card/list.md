# process: durable Process Runtime and replay

## Vocabulary

- **Process**: A durable function that can be replayed from the journal, not an OS process.
- **ProcessDefinition**: The stable name, version, and Python Process function.
- **ProcessActivation**: Input that creates or resumes a Process.
- **Journal**: Stores command results and errors by run id and command index.
- **ProcessHandle**: A stable reference for querying or waiting on a child Process across restarts.

## Structure

```
Process
├── Definition / Activation
├── Process Runtime
│   ├── Command Interpreter
│   └── Replay
├── Journal
├── Lifecycle / State
└── Durable Handle
```

## This layer owns

- `ProcessDefinition`
- `ProcessActivation`
- `ProcessRuntime`
- `Journal`
- `Lifecycle`
- `State`
- `ProcessHandle`

## Architecture requirements

1. A Process function replays from a fixed initial input and does not resume a live coroutine.
2. Each Task, child, or wait writes the journal at a stable command index.
3. A journal hit returns the old result; a miss is the only time a side effect runs.
4. A name, version, or input change at the same command index must be rejected as nondeterministic.
5. A Process expresses causality only through caused_by and does not form a parent-child agent tree.
6. The Process Runtime depends only on the Store, Queue, Journal, and Executor injected by the host.
