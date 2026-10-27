# file

[English](README.md) | 中文

`create` 在本机写一个文件。`load env` 记住一份环境文件，供同一窗口里下一次 `process start` 使用。

## 契约

`create.py` 实现 `linope create <path> [-- name=value]`。

相对路径从工作目录解析。父目录会被创建。没有赋值时，缺失的文件被创建为空文件，已有文件保持原样。`--` 后面的一个 `name=value` 替换文件中的该名字，或追加它。值不会被打印。命令打印解析后的路径。

`env.py` 实现 `linope load env <path>`。路径必须已经是文件。命令打印 `env_file=<path>`。绑定了书记员窗口时，`note_env` 记住该路径。同一窗口里稍后的 `process start` 在省略 `--env-file` 时使用它。秘密值留在文件里。

在 TUI 和 `linope session` 里，`create <path>` 与 `linope create <path>` 在同一窗口运行。

## 已知限制与暂缓事项

- **一次 `create` 只有一条赋值** — `--` 后面多于一个词是用法错误。
