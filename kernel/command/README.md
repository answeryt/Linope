# command

`kernel/command` 是内核的命令入口。命令按事情分开放：`process/` 管启动和对进程说话，`file/` 管建文件和指出环境文件，`screen/` 管屏幕上看到的资源服务。认命令只有 `dispatch.py` 一份。`linope terminal` 和 `linope session` 打开同一个窗口。

现在能执行的有：

```text
linope create <路径> [-- 名字=值]
linope load env <路径>
linope process start <能力> [--change 主题=值] [--count 份数] [--share 资源种类] [--with 种类=身份] [--once] [--ping]
linope resource serve [--host 127.0.0.1] [--port 0]
linope terminal
```

`create` 在这台机器上建文件。`--` 后面写一行 `名字=值`，就是往这份文件里加一个环境变量。`load env` 记住这份文件，之后同一终端里的 `process start` 没写 `--env-file` 就用它。密钥值留在文件里，不打印出来。TUI 和 `linope session` 里直接写 `create <路径>`，也可以写 `linope create <路径>`，不必另开窗口。

`process start` 按能力档案申请资源，为每个操作系统 `pid` 打开一份资源记录，然后停在当前进程里。不写 `--once` 就一直留到进程退出或 `Ctrl+C`。写了 `--once`，做完这一次就关闭记录并返回。`--share` 只让点到的资源种类在这次启动里共用。`--with` 在档案已有的资源之外再领一种，例如 `--with memory=chat`；档案里已经有的种类不能用它改掉。`--ping` 问这个进程自己，等它回 `pong`，不调用模型。没答上就关闭记录，命令失败。

进程领了记忆时，`load message <进程号> -- 文件路径` 可以把一份 `.txt`、`.md` 或 `.json` 的全文记进 `system`，不调用模型。再加载另一份文件会留在后面，不换掉已经记下的文件。份数从 1 开始，写在路径前面，例如 `load message <进程号> -- 1 文件路径`，这份文件就插到那个位置，原来的依次往后挪。不写份数时，新文件排到最后；同一路径再加载只更新这一份，没写份数就留在原位。下一次提问把这些文件按这个顺序拼成一段 `system` 送出。人说的话、模型的输出、工具的输出，以及交任务回来的结果，也写进同一份 memory，跟 `system` 放在一起，按发生的时间往后排。这些正文不写入进程账本。这个进程没有记忆时，这样的文件路径会被拒绝。

进程还留着的时候，同一终端里可以再写：

```text
load message -- 你好
load tool -- {"query": "分布式系统"}
ask <对方进程号> -- 要做的事
ping
ping <pid>
```

`load message` 和 `load tool` 交给这个进程已经打开的适配器。指向提示词文件的那一次除外，它只写入 memory 里的 `system`。`load env` 不送进进程。`message` 只给模型进程，`tool` 只给工具进程。有多份进程时要写上操作系统 `pid`。自己对自己说 `load message`，这个进程记成自己在干。

进程还留在这个窗口里时，`show <进程号>` 会把这份 memory 里的系统提示词和对话正文一起打出来。没领 memory 就没有这一段。关掉窗口之后，这些字已经不在，再 `show` 只能看到进程账，看不到对话。

`ask` 把一件事交给还留着的另一个进程。送过去的只有这件事，不附上发送方的 memory。对方用自己的 memory 来做。结果写回发送方的 memory。这时两边都记成正在跟对方一起干，做完回到闲着。除了对方，还要正好有一个还活着的进程当发送方。

没有 `process list`、`process status`、`process stop`，也没有 `service create|bind|call`。

命令层不读模型卡片、不执行工具、不跟随输出里的命令，也不选择传输后端。
