# file

English | [中文](README.cn.md)

`create` writes a file on this machine. `load env` remembers an env file for the next `process start` in the same window.

## Contract

`create.py` implements `linope create <path> [-- name=value]`.

The path is resolved from the working directory when it is relative. Parent directories are created. With no assignment, a missing file is created empty and an existing file is left as it is. One `name=value` after `--` replaces that name in the file or appends it. The value is not printed. The command prints the resolved path.

`env.py` implements `linope load env <path>`. The path must already be a file. The command prints `env_file=<path>`. When a clerk window is bound, `note_env` remembers that path. A later `process start` in the same window uses it when `--env-file` is omitted. Secret values stay in the file.

In the TUI and `linope session`, `create <path>` and `linope create <path>` run in the same window.

## Known Limitations and Deferred Work

- **One assignment per `create`** — a line with more than one token after `--` is a usage error.
