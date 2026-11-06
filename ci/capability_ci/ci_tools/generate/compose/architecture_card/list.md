# compose: a Task function is the durable side-effect boundary

## Vocabulary

- **TaskDefinition**: Stable name, version, retry, timeout, and resource requirements.
- **TaskExecutor**: Runs a synchronous or asynchronous side effect and submits the result or error.
- **TaskBinding**: The runtime binding of a Task attempt to a resource lease.
- **ResourceLease**: The limited right to use a resource while a Task runs.

## Structure

```
Process
└── Task Command
    ├── Task Definition
    ├── Task Executor
    └── Resource Binding
```

## Place in the structure

The directory name stays compose; the public concept is Task Function. Plugin review (assembly_check / descriptor_check) checks capability-graph assembly. This card does not state a code contract.

## This layer owns

- `TaskDefinition`
- `TaskExecutor`
- `TaskBinding`

## Architecture requirements

1. A Task function carries side effects such as models, tools, HTTP, databases, and files.
2. A TaskDefinition must have a stable name and version.
3. A TaskExecutor supports synchronous and asynchronous execution, retry, and timeout.
4. A TaskBinding acquires a resource lease and releases leases in reverse order when the attempt ends.
5. Task results and errors are recorded in the Process journal. Replay does not run a completed Task again.
