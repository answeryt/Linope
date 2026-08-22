# thred：Thread 是 Process 内的等待上下文，不是 Work Unit

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

## 在结构图中的位置

结构图不把 Thread 画成与 Process / Execution 平行的节点。Thread 附着在 Process 下，解释某个 Execution 为何等待。

## 本层拥有

无。Thread 不是结构图上的独立节点。

## 架构要求

1. 结构图不把 Thread 画成 Work Unit。Thread 不是第四种与 Process / Execution 平行的主体。
2. Thread 是 Process 内部的等待与并发上下文，可以附着在某个 Execution 上。
3. Thread 不是 OS thread，也不是部署边界。等待不占用内核线程。
4. Thread 没有独立目标。目标属于 Task / Process。
5. Scheduler 挑选的是 Execution，不是 Thread。Thread 只解释该 Execution 为何等待，或占用哪类资源。
6. Process 结束时，其下 Thread 一并结束。
7. Thread 不能替代 Process 的生命周期，也不能替代 Execution 的可调度性。
