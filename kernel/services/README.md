# services

服务是若干已经在跑的进程的名单，自己不是进程。

`linope service start <进程号> [<进程号> ...]` 核对进程账本后，把这些号记到 `.linope/services.json`。它不启动进程，也不关闭进程。
