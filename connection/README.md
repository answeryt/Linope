# Shared connection layer

`connection` is the semantic gateway shared by Linope frontends.

It accepts versioned JSONL action requests, validates them, compiles them into
the existing kernel command lines, and relays versioned kernel events. The
gateway does not modify the `kernel/` package.

Supported actions:

- `chat.send`: compile to `model run -- <text>`.
- `process.send`: compile to `load message <pid> -- <text>`.
- `process.create`: compile to `process start ...`.
- `environment.load`: remember an environment file reference.
- `model.configure`: compile model core/card commands.
- `command.execute`: legacy command compatibility for the TUI.

Run it from the repository root with:

```text
python -m connection.gateway
```

Each input line is an action object from
`connection/protocol/actions.schema.json`. Each output line is a version 1
event from `connection/protocol/events.schema.json`.
