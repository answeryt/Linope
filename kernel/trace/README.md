# trace

English | [中文](README.cn.md)

Two append-only files. The scheduler and the model page do not read either of them.

## Contract

| File | What it stores | Command |
|---|---|---|
| `.linope/activity.jsonl` | Whether a process is `sleeping`, `self`, `with`, or `closed`, in the order it happened. `with` may name a counterpart and a way such as `task`. | `trace <pid>` prints that process |
| `.linope/log/session.jsonl` | The turn journal: each line a person typed, and the original text and verdict each time the model finishes a write. A typed line has no pid. | `log` prints every line in time order. `log <pid>` prints only rows whose `pid` matches. |

`activity.py` is `ActivityLog`. `journal.py` is `Journal`. `journal_path` is `.linope/log/session.jsonl` under the working directory. `journal_beside` is the journal next to a ledger file.

`kernel/command/log.py` prints the journal. A missing file prints `No turn log yet` and exits 1. A pid that appears in no row exits 1. A non-numeric pid exits 1.

`trace` with no living window reads the saved activity file. The command entry is [`kernel/command/process`](../command/process/README.md).

## Known Limitations and Deferred Work

- **No span tree** — a diagnostic record is optional and holds `trace_id`, the error text, and where the error is. It is not a second completion status and it does not persist task state.
