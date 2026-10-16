# command

`kernel/command` 是内核的命令行。仓库根目录的 `linope.cmd` 用 Python 打开它。双击 `linope.cmd` 等同于 `linope terminal`。进入自己的终端后，命令在这个进程里执行，不再交给本机的 PowerShell：

```text
linope terminal
```

终端打开后先扫描仓库里的 `.env`。扫到了只显示路径和键名，并问用不用；没有，或回答不用，就提示用 `env init` 自己建。选定后才进入命令。终端打开后不退出。人在里面一行一行输入。`exit` 离开。`start` 拉起的进程保持开着，离开终端时才停下。之后的 `load` 把一张条子送给已经开着的进程：种类、正文，以及正文里的文件资源地址。资源本身仍在账本里。正文如果只是 `file once` 或 `file lasting` 给出的地址，条子里就只有这个地址，模型再用文件门把字读出来。空看信箱不会把整本账换掉。进程之间要先把话送到，先选 `channel zeromq`。

模型或工具的输出里，如果单独有一整行是命令，终端会执行它，并把结果交回刚才那个模型。包在句子里的话不执行。一轮里接着执行的次数有限，超过就停住并显示还没跑的行。

```text
channel use zeromq
process start model.openai_chat_model
resource serve --host 127.0.0.1 --port 0
resource file lasting 调度.txt -- 你是调度。任务写在这里。
capability load model.openai_chat_model message http://127.0.0.1:<actual-port>/resources/<id>
service create planner
service bind planner --process <进程号> --role model
service call planner --role model --kind message -- 请你给出修改计划
channel off
process share model.openai_chat_model
layout use numbered
process start model.openai_chat_model --count 10
process share off
resource file once 笔记.md -- # 今天
process list
process status <process_id>
process workers idle model.openai_chat_model
env init D:/secrets/linope.env
env use D:/secrets/linope.env
capability load model.anthropic_model message 请你介绍一下你自己
service create chat
service bind chat --process <进程号> --role model
exit
```

`process start` 拉起一个能力进程，并在这条命令退出时停下它。`service create` 只创建一个空服务。`service bind` 把已经启动的进程绑进去，同一条命令可以再绑下一个进程。`service unbind` 和 `service delete` 只去掉关系，不停止进程。停止进程用 `process stop`。`--change 主题=值` 覆盖能力档案。`--count` 是份数。

`process start`、`capability load`、`capability call` 和 `resource file` 拉起进程并提交请求。`service call` 把请求交给已经绑定的进程，不另起进程。

账本可以通过定位串切换：

```text
store current
store use file:.linope/resources.json
store check
store init sqlite:///.linope/ledger.db
store migrate postgresql+psycopg://user@host/database
```

`start`、`load`、`call`、`file` 和 `resources` 也支持
`--resource-store <定位串>`。没有指定时使用项目配置中的默认存储，未配置则继续使用
`.linope/resources.json`。

先启动一次资源 HTTP 服务。不写 `--mode` 就是 `local`：只监听本机回环，`--port 0` 让操作系统选择空闲端口，实际端口会写入 `.linope/http-server.json`。同一个账本下的所有文件共享这个端口。

跨机器时显式选择私网模式，不把服务暴露到公网。公开地址写成内网 IP 或 VPN 域名，端口要固定，账本改用数据库，其他机器只保存并跟随返回的链接：

```text
linope resource serve --mode private --host 10.0.0.10 --port 49152 --public-base-url http://10.0.0.10:49152
```

`local` 仍用原来的 localhost。私网模式下 ZeroMQ 和 gRPC 公布配置的私网主机，不把 `0.0.0.0` 写进账本；NATS 要写成私网地址。可选环境变量 `LINOPE_RESOURCE_TOKEN` 作为访问令牌，不会出现在链接里。

`linope file once` 在当前目录写出全文，并记一页还在窗口里的长期页。`linope file lasting` 同样落盘，并把这一页钉住。命令输出一个 HTTP `href`。浏览器、RAG、LLM 和 Linope CLI 使用同一个资源地址。

它只把能力名和 `主题 change - 值` 交给能力自己的档案函数。没有这个函数时，命令在创建进程之前结束。进程不读取 JSON、YAML 或 TOML。

先用 `linope channel use` 选出通信方法，不选就用账本信箱。`linope channel use nats` 使用 `nats://127.0.0.1:4222`，后面可以再写一个地址。`linope channel off` 回到账本信箱。

先用 `linope process share` 点名要共用资源的能力，再选 `linope layout use numbered`、`counted` 或 `named`。`linope process start <能力> --count <份数>` 决定这次开几份。不写就是 1。`--change 主题=值` 里面的数字仍是档案参数，不会被当成份数。点了名的能力，多份进程共用身份相同的资源；没点名的，每个进程一份。

`linope process start <能力>` 还可以写 `--cwd <目录>` 和 `--max-runtime-seconds <秒>`。不写工作目录就用当前目录。不写墙钟就不限时长。`--max-concurrent-tasks`、`--min-concurrent-tasks`、`--max-sync-workers` 仍是启动时的接单人数。运行中改上限用 `linope process workers add <能力>` 和 `linope process workers remove <能力>`。`linope process workers idle <能力>` 只要求空闲进程停下，并至少留下一个。

`linope process list` 列出还在跑的进程。`linope process status <进程号>` 打印那间屋子：工作目录、环境变量名字、允许的目录、读写档位、内存页、外网名单、墙钟和启动等待。不打印密钥的值。`linope process scale <能力> --count <份数>` 按已选择的布局调整份数。

密钥文件由开发者自己指定，不必放在 `capability` 下面。`linope env init` 建一个空文件并记下路径，里面写什么由开发者自己填。`linope env use` 只改记下的路径，不改文件。路径写在 `.linope/config.json` 的 `env_file`。之后启动和调用不用再写 `--env-file` 和 `--env`。这次命令上写了 `--env-file` 就用这次的；没写就用记下的路径。都没有就不带密钥文件。模型只从文件里拿走卡片上的那一个键，值留在文件里，不进启动包。

## 写法

命令是 `对象 子命令 [选项] [参数]`。选项使用 `--名字 值`。可以重复的选项包括 `--change`。`--change` 的值写成 `主题=值`。`--` 后面是自由正文，例如文件全文、提问和 chord 的最后一个操作。

全局选项 `--resource-store`、`--env-file`、`--env` 和 `--json` 可以写在子命令后面。`--json` 让结果以 JSON 输出。参数错误退出码是 2，运行失败是 1，成功是 0。

对象有 `service`、`process`、`resource`、`capability`、`store`、`channel`、`layout`、`env` 和 `terminal`。`capability call`、`chain`、`group` 和 `chord` 分别是一次调用、顺序调用、并行调用和汇合调用。

## 文件

- `__main__.py`：唯一命令行入口，转给 `dispatch.main`。
- `dispatch.py`：按对象名查表，再把剩余参数交给该对象。
- `convention.py`：一次解析结果，包含参数、选项、账本、环境文件和 `--json`。
- `parser.py`：长选项、重复选项、`--change 主题=值` 和 `--` 后面的正文。
- `service.py`：创建空服务，绑定或解除已有进程，并向服务发送一次请求。
- `process.py`：启动单个能力，以及列表、状态、停止、份数、共享资源和工人数。
- `terminal.py`：一直开着的终端。自己读一行、执行一行，认出输出里的命令，并把条子送给还开着的服务。
- 其余模块：一个对象一个文件。
