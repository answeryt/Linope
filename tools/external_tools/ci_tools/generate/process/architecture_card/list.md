# process：持久 Process Runtime 与 Replay

## 词汇

- **Process**：可从 journal 重放的 durable function，不是 OS 进程。
- **ProcessDefinition**：稳定名称、版本与 Python Process Function 的定义。
- **ProcessActivation**：创建或恢复 Process 的输入。
- **Journal**：按 run ID 与 command index 保存命令结果和错误。
- **ProcessHandle**：跨重启查询或等待子 Process 的稳定引用。

## 结构

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

## 本层拥有

- `ProcessDefinition`
- `ProcessActivation`
- `ProcessRuntime`
- `Journal`
- `Lifecycle`
- `State`
- `ProcessHandle`

## 架构要求

1. Process Function 从固定初始输入开始重放，不恢复 live coroutine。
2. 每个 Task、child 或 wait 使用稳定 command index 写入 Journal。
3. Journal 命中时返回旧结果，未命中时才执行副作用。
4. 同一 command index 的名称、版本或输入变化必须拒绝为非确定性。
5. Process 只通过 caused_by 表达因果关系，不形成主从 Agent 树。
6. Process Runtime 只依赖 Host 注入的 Store、Queue、Journal 和 Executor。
