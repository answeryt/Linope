# 内核与 UI 边界

内核负责进程生命周期、资源租约、模型调度、命令执行和结构化事实，
不负责终端文本、ANSI 布局、输入锁定或 transcript 渲染。模型调度由
`model_scheduler` 的模型状态负责，不再通过 `settings.slot` 识别模型进程。
上下文上限来自当前模型卡片；滑动窗口的裁切下标通过
`python -m capability.queries tail-cut` 询问，不导入能力模块。

`kernel.command.events.KernelEvent` 是宿主协议。事件带版本，并在需要时携带 `request_id`、`turn_id`、`pid` 和 `seq`。命令值和失败都使用结构化数据。命令入口负责把事实序列化为 JSONL，内核服务只依赖 `EventSink`。

能力进程的 stdout 是内部 RPC 通道。能力通知（包括模型增量）都使用带帧的 RPC 事件。能力进程 stderr 只用于诊断，不能进入模型 transcript。

TUI 校验 JSONL 协议，通过纯 reducer 折叠事件，再把结果状态交给 renderer。将 TUI 替换为 headless、JSON 或 Web 宿主时，不需要修改内核调度和进程管理。

内核命令代码禁止以下行为：

- 终端文案、ANSI 转义或面向人的 `print`；
- 通过 stdout 捕获恢复嵌套命令结果；
- 解析 `pid=` 或其他显示文本；
- 发送无关联 id 的完成或忙闲标记；
- 把能力进程 stderr 转发到宿主 transcript。
