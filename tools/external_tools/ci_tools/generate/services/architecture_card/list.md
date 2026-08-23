# services：Agent = Service + Resources

## 词汇

- **Agent**：Service 与 Resources 的最终装配结果。
- **Service**：唯一部署边界；接收 ProcessActivation 并运行 Process。
- **Ingress**：把外部输入规范化为可序列化 Activation。
- **RunQueue**：使用 lease 与 fencing token 调度 Process/Task 工作。
- **ProcessStore**：Host 注入的 Process Run 持久化接口。
- **Resources**：容器资源与模型资源组成的统一容量池。

## 结构

```
Agent
├── Service
│   ├── Ingress
│   ├── Worker
│   ├── Run Queue
│   ├── Process Store
│   └── Agent Assembly
└── Resources
    ├── Container Resources
    └── Model Resources
```

## 本层拥有

- `App`
- `Ingress`
- `Worker`
- `RunQueue`
- `ProcessStore`

## 架构要求

1. Agent 严格等于 Service + Resources，不是人格或进程层级。
2. Service 是唯一部署边界，一个 Service 可以运行多个 Process。
3. Ingress 只传可序列化 ProcessActivation，不传 live Process。
4. Worker 使用 queue lease 和 fencing token 驱动 Process Runtime。
5. Store、Queue 和 Ingress 是 Host adapter，不进入 Process 定义。
6. OS process、worker、队列和部署框架只能出现在 services。
