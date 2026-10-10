# process：平级 OS Process Runtime

## 词汇

- **Process**：一个 capability 的独立 OS 运行实例，由 `process_id` 寻址。
- **ProcessDeclaration**：一次进程所需的 capability 和资源声明。
- **ProcessActivation**：进程启动包，包含 capability、资源句柄、环境和线程策略。
- **ProcessRuntime**：加载 capability adapter、绑定环境、消费 Channel、调用 ThreadRuntime。
- **ProcessHandle**：调用方使用的 submit/wait/send 视图。
- **ProcessMonitor**：无父子语义的启动、停止、存活检查和回收视图。

## 结构

```text
ProcessDeclaration
└── ProcessActivation
    └── Peer Process
        └── ThreadRuntime
```

## 本层拥有

- `ProcessDeclaration`
- `ProcessActivation`
- `ProcessRuntime`
- `ProcessHandle`
- `ProcessMonitor` / `ProcessReaper`
- Process lifecycle and communication

## 架构要求

1. `process_id` 是唯一公开的 OS Process 身份。
2. Process 只接收可序列化 Activation，不接收 live Agent 或 Thread。
3. Process 内部使用 `kernel/thread` 执行异步任务和同步阻塞代码。
4. ResourcePool 管理租约和句柄；Process Runtime 不拥有全局资源实体。
5. Durable workflow/replay 如未来需要，应另建 `kernel/run` 或 `kernel/workflow`，不覆盖当前 OS Process 语义。
