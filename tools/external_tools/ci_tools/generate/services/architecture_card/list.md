# services：Microservice 是 Agent 本体，也是部署边界

## 词汇

- **Microservice**：部署边界。微服务指 Agent 本体。
- **Process**：一个具有独立目标、状态、资源和生命周期的 Agent Work Unit。
- **Execution**：Process 内部可被 Scheduler 独立调度的最小执行单元。
- **Task**：用户/Agent 想要完成的目标。
- **Loop**：Execution 使用的控制机制。
- **Event**：Runtime 中发生的状态变化。

## 结构

```
Microservice
                      │
                   Process
                      │
          ┌───────────┼───────────┐
          │           │           │
        State      Resources    Memory
                      │
                  Scheduler
                      │
            ┌─────────┼─────────┐
            ↓         ↓         ↓
        Execution  Execution  Execution
            │         │         │
          Agent      Tool      Event
           Loop       Loop      Loop
```

## 本层拥有

- `Microservice`
- `Task`

## 架构要求

1. Microservice 是 Agent 本体，也是唯一部署边界。一个可部署的 worker 就是一个 Agent。
2. Process、Execution、Thread 都不是可独立部署的单元；它们活在同一个 Agent 本体内。
3. Microservice 收下 Task（用户/Agent 的目标），并为该目标创建 Process。
4. Microservice 不调度。调度权属于 Process 资源上的 Scheduler。
5. Task 是目标，不是 Work Unit，也不是可调度单元。一条 Task 不能当成一个 Execution。
6. 一次 Task 的多轮 Loop 发生在同一个 Process 内，不在部署边界上为每一轮再开一个 Agent。
7. Event 不会在部署边界上变成新的 Agent 会话。
