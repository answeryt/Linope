# Linope 最小聊天服务示例

这个示例使用一个模型进程组成最小聊天服务。当前架构没有 `agent create` 或 `service start`：先启动进程，再创建空服务，最后把进程绑定到服务。

先在两个 PowerShell 窗口中分别启动 TUI：

```powershell
.\linope.cmd terminal
```

进入蓝色 TUI 后，下面的命令直接输入，不要再输入 `.\linope.cmd` 前缀。

## 1. 启动模型进程

在第一个 TUI 窗口中执行：

```text
process start model.openai_chat_model --resource-store file:.linope/chat.json
```

进程会保持运行，并输出类似下面的进程号：

```text
process_id=模型进程号
```

记下真实的 `process_id`，不要关闭该窗口。

## 2. 创建聊天服务

执行：

```text
service create chat --resource-store file:.linope/chat.json
```

## 3. 绑定模型进程

把下面的 `实际进程号` 替换成第一步输出的真实 ID，不要输入尖括号或这四个中文占位字：

```text
service bind chat --process 实际进程号 --role model --resource-store file:.linope/chat.json
```

查看绑定结果：

```text
service status chat --resource-store file:.linope/chat.json
```

## 4. 发送聊天消息

```text
service call chat --role model --kind message --resource-store file:.linope/chat.json -- 你好，请介绍一下你自己。
```

继续发送一条消息：

```text
service call chat --role model --kind message --resource-store file:.linope/chat.json -- 请你介绍一下分布式系统。
```

每次回复都会写入：

```text
.linope/chat.json
```

请求和回复位于 `sections.mailbox.requests`。服务成员关系位于 `sections.process.bindings`。

## 账本记录

`.linope/chat.json` 是这个聊天服务的运行账本，不是模型配置文件。它保存四类数据：

- `resource`：资源页、租约和句柄
- `process`：进程 ID、能力名称、PID、状态和服务绑定
- `mailbox`：请求、认领状态、回复和用量
- `channel`：进程间通信方式和端点

账本不会保存 API Key 的值，但会保存聊天正文、模型回复、工作目录和环境变量键名。

## 5. 停止模型进程

把下面的 `实际进程号` 替换成同一个真实 ID：

```text
process stop 实际进程号 --resource-store file:.linope/chat.json
```

`service delete` 只删除服务和绑定关系，不负责停止进程。
