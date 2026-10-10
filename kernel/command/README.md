# command

`kernel/command` 是内核的命令行。仓库根目录的 `linope.cmd` 用 Python 打开它。双击 `linope.cmd` 等同于 `linope terminal`。进入自己的终端后，命令在这个进程里执行，不再交给本机的 PowerShell：

```text
linope terminal
```

终端打开后先扫描仓库里的 `.env`。扫到了只显示路径和键名，并问用不用；没有，或回答不用，就提示用 `env init` 自己建。选定后才进入命令。终端打开后不退出。人在里面一行一行输入。`exit` 离开。`start` 拉起的进程保持开着，离开终端时才停下。之后的 `load` 把一张条子送给已经开着的进程：种类、正文，以及正文里的文件资源地址。资源本身仍在账本里。正文如果只是 `file once` 或 `file lasting` 给出的地址，条子里就只有这个地址，模型再用文件门把字读出来。空看信箱不会把整本账换掉。进程之间要先把话送到，先选 `channel zeromq`。

模型或工具的输出里，如果单独有一整行是命令，终端会执行它，并把结果交回刚才那个模型。包在句子里的话不执行。一轮里接着执行的次数有限，超过就停住并显示还没跑的行。

```text
channel zeromq
start model.openai_chat_model
resources serve --host 127.0.0.1 --port 0
file lasting 调度.txt -- 你是调度。任务写在这里。
load model.openai_chat_model prompt http://127.0.0.1:<actual-port>/resources/<id>
load model.openai_chat_model prompt 你是规划的人。需要查目录时，单独写一行命令。
channels
channel zeromq
channel off
share model.openai_chat_model
start model.openai_chat_model --ping model change - gpt-4o temperature change - 0.2
layout numbered
start model.openai_chat_model 10
share off
resources serve --host 127.0.0.1 --port 0 --resource-store .linope/resources.json
file once 笔记.md -- # 今天
file lasting scripts/main.py -- print("hi")
ask model.anthropic_model http://127.0.0.1:<actual-port>/resources/<id> -- 请问你是谁
room
room <process_id>
thread show model.openai_chat_model
thread idle model.openai_chat_model
env init D:/secrets/linope.env
env use D:/secrets/linope.env
load model.anthropic_model prompt 请你介绍一下你自己
services
service start model model.openai_chat_model model change - gpt-4o
service start agent model.openai_chat_model tools.bash tools.read
service start mcp
exit
```

`services` 列出已登记的服务种类。`service start` 按种类打开一组平级进程：`model` 要一个 `model.*`，`agent` 要一个 `model.*` 再加若干 `tools.*` 或 `context.*`，`mcp` 不写成员时用 `tools.mcp_tool_manager`。末尾的整数仍是份数，`主题 change - 值` 给第一个成员。

`start`、`load`、`call`、`ask`、`file` 和 `service` 都经过 `kernel/services`。命令只提交请求和等待回复，不自己打开资源池，也不自己拉起进程。

账本可以通过定位串切换：

```text
stores
store current
store use file:.linope/resources.json
store check
store init postgresql://user:password@host/database
store migrate mysql://user:password@host/database
```

`start`、`load`、`call`、`file`、`ask` 和 `resources` 也支持
`--resource-store <定位串>`。没有指定时使用项目配置中的默认存储，未配置则继续使用
`.linope/resources.json`。

先启动一次资源 HTTP 服务。`--port 0` 让操作系统选择空闲端口，实际端口会写入 `.linope/http-server.json`。同一个账本下的所有文件共享这个端口。

`linope file once` 在当前目录写出全文，并记一页还在窗口里的长期页。`linope file lasting` 同样落盘，并把这一页钉住。命令输出一个 HTTP `href`。`linope ask` 跟随这个 HTTP 地址，把文件全文和 `--` 后面的话交给点名的模型。浏览器、RAG、LLM 和 Linope CLI 使用同一个资源地址。

它只把能力名和 `主题 change - 值` 交给能力自己的档案函数。没有这个函数时，命令在创建进程之前结束。进程不读取 JSON、YAML 或 TOML。

先用 `linope channel` 选出通信方法，不选就用账本信箱。`linope channels` 列出已登记的名字。`linope channel nats` 使用 `nats://127.0.0.1:4222`，后面可以再写一个服务器地址。`linope channel off` 回到账本信箱。

先用 `linope share` 点名要共用资源的能力，再选好 `numbered`、`counted` 或 `named`。创建命令末尾的整数是这次要开的份数。不写就是 1。`主题 change - 值` 里面的数字仍是档案参数，不会被当成份数。点了名的能力，多份进程共用身份相同的资源；没点名的，每个进程一份。

`linope start` 还可以写 `--cwd <目录>` 和 `--max-runtime-seconds <秒>`。不写工作目录就用当前目录。不写墙钟就不限时长。`--max-concurrent-tasks`、`--min-concurrent-tasks`、`--max-sync-workers` 仍是启动时的接单人数。运行中改上限用 `linope thread add` 和 `linope thread remove`。`linope thread show` 看每个进程的信箱和上限。`linope thread idle` 只要求空闲进程停下，并至少留下一个。

`linope room` 不带进程号时列出还在跑的进程。带进程号时打印那间屋子：工作目录、环境变量名字、允许的目录、读写档位、内存页、外网名单、墙钟和启动等待。不打印密钥的值。

密钥文件由开发者自己指定，不必放在 `capability` 下面。`linope env init` 建一个空文件并记下路径，里面写什么由开发者自己填。`linope env use` 只改记下的路径，不改文件。路径写在 `.linope/config.json` 的 `env_file`。之后 `start`、`load`、`call`、`ask` 不用再写 `--env-file` 和 `--env`。这次命令上写了 `--env-file` 就用这次的；没写就用记下的路径。都没有就不带密钥文件。模型只从文件里拿走卡片上的那一个键，值留在文件里，不进启动包。

## 文件

- `__main__.py`：唯一命令行入口，转给 `dispatch.main`。
- `protocol.py`：每个命令都是 `run(argv) -> int`。别名带自己的运行函数。
- `catalog.py`：登记命令的唯一位置。新命令在这里加一行。
- `dispatch.py`：按名字查表，不为某个命令写分支。
- `parser.py`：各命令按需使用的参数片段，包括环境文件、资源存储、change 子句、成员名和份数。
- `service.py`：`service start` 打开一个已登记的服务种类，`services` 列出种类。
- `terminal.py`：一直开着的终端。自己读一行、执行一行，认出输出里的命令，并把条子送给还开着的服务。
- 其余模块：一个命令一个文件。
