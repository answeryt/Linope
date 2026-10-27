# Linope 最小搜索服务示例

这个示例用一个模型进程和一个搜索进程组成一份服务，然后只用服务编号跟它对话。没有 `service create`、`service bind`、`service call`。

先启动 TUI：

```powershell
.\linope.cmd terminal
```

进入蓝色 TUI 后，下面的命令直接输入，不要再输入 `.\linope.cmd` 前缀。

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

## 3. 登记成一份服务

把两个号换成上一步打出的真实进程号：

```text
service start <模型进程号> <搜索进程号>
```

成功时先打 `service=<编号>`，再打每一行 `pid=` 和 `capability=`。

## 4. 跟服务对话

```text
service load 1 -- 今天北京天气怎么样
```

`1` 是上一步打出的服务编号。这一行会交给服务里唯一还开着的模型进程，跟 `load message <模型进程号> -- 今天北京天气怎么样` 完全一样。之后搜什么、什么时候回答，都由模型自己一步步决定。

服务里没有还开着的模型进程，或者不止一个，这一行会被拒绝，并列出相关进程号。

## 5. 结束

```text
exit
```

窗口里的进程一起停掉。`.linope/services.json` 里的名单还在，但这些号不再是还开着的进程。
