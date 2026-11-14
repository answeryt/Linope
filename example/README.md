# Linope 最小搜索服务示例

这个示例用一个模型进程和一个搜索进程组成一份服务，然后只用服务编号跟它对话。没有 `service create`、`service bind`、`service call`。

[英文命令规则](linope.md) | [中文命令规则](linope.cn.md)

## 命令行规则

人直接操作 Linope 命令时，完整的命令参考在：

- [中文命令参考](../kernel/command/README.cn.md)
- [English command reference](../kernel/command/README.md)

下面两个文档是给模型加载的操作规则，包含页面格式、可用指针、命令写法和安全边界：

- [中文模型操作规则](linope.cn.md)
- [English model operation rules](linope.md)

模型进程启动并且拥有 `memory` 后，可以把命令规则加载为它的系统记忆：

```text
load message <模型进程号> -- example/linope.cn.md
```

如果模型使用英文提示词，也可以加载：

```text
load message <模型进程号> -- example/linope.md
```

加载后，模型会熟悉 Linope 的命令协议、页面格式和安全边界，能够根据当前页面自主选择和组合可用能力，更灵活地完成任务，而不需要人一步一步替它拼写命令。加载规则不会额外授予权限，模型仍然只能执行当前页面提供的命令。

先启动 TUI：

```sh
linope
```

进入蓝色 TUI 后，下面的命令直接输入，不要再输入 `linope` 前缀。

## 1. 指出环境文件

```text
load env capability/.env
```

`model.openai_chat_model` 从这份文件里只拿 `OPENAI_API_KEY`。

## 2. 启动两个进程

```text
process start model.openai_chat_model --with memory=search
process start tools.ddgs
```

每一份都会打出一行：

```text
pid=<数字> capability=<能力名>
```

记下这两个数字。

## 3. 让模型熟悉命令规则

先把模型进程的 pid 换成真实数字，再加载命令规则。中文模型加载中文文档：

```text
load message <模型进程号> -- example/linope.cn.md
```

如果模型使用英文提示词，也可以加载英文文档：

```text
load message <模型进程号> -- example/linope.md
```

这一步会把 Linope 的命令协议、页面格式和安全边界放进模型的 `memory.system`，不会立即向模型发送问题。之后模型可以根据当前页面自主选择和组合可用能力，更灵活地完成任务；但它仍然只能执行页面中提供的命令，不能绕过权限检查。

## 4. 登记成一份服务

把两个号换成上一步打出的真实进程号：

```text
service start <模型进程号> <搜索进程号>
```

成功时先打 `service=<编号>`，再打每一行 `pid=` 和 `capability=`。

## 5. 跟服务对话

```text
service load 1 -- 今天北京天气怎么样
```

`1` 是上一步打出的服务编号。这一行会交给服务里唯一还开着的模型进程，跟 `load message <模型进程号> -- 今天北京天气怎么样` 完全一样。之后搜什么、什么时候回答，都由模型自己一步步决定。

服务里没有还开着的模型进程，或者不止一个，这一行会被拒绝，并列出相关进程号。

## 6. 结束

```text
exit
```

窗口里的进程一起停掉。`.linope/services.json` 里的名单还在，但这些号不再是还开着的进程。
