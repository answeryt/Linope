# kernel/thred/plugin

本目录是 Host 侧插件运行时。叶插件不 import 具体实现，只认插座、事件暗号和装配图。

```text
kernel/thred/plugin/
├── README.md                 本文件：目录说明与架构
├── VENDOR.md                 上游来源：stevedore / pluggy
├── composition.yaml          装哪些插件、各自配置
├── __init__.py               包标记
├── exception.py              插座查找错误：NoMatches 等
├── manager/                  插座板与驱动加载（源自 stevedore）
│   ├── driver.py             DriverManager.from_file：按文件加载插头
│   ├── extension.py          ExtensionManager
│   ├── named.py              按名字加载
│   ├── hook.py               同名多扩展协调
│   ├── dispatch.py           运行时再过滤
│   ├── enabled.py            按检查函数启用
│   ├── cache.py              entry point 缓存
│   └── sphinxext.py          Sphinx 文档扩展
├── signals/                  事件暗号 on / emit（源自 pluggy）
│   ├── manager.py            PluginManager.on / emit
│   ├── hooks.py              hook 标记与调用
│   ├── callers.py            1:N 调用循环
│   ├── result.py             wrapper 结果
│   ├── tracing.py            调试跟踪
│   ├── warnings.py           警告类型
│   └── compat.py             发行版元数据兼容
└── host/                     装配与门面（本仓库自写）
    ├── __init__.py           公共门面：Context, load_composition
    ├── protocol.py           叶插件合同：PLUGIN_NAME / apply
    ├── lip.py                运行时：provide / get / on / emit / effect
    ├── loader.py             读 composition.yaml 装配
    ├── board.py              socket → name → 文件 查表
    └── events.py             把 signals 接到 lip.on / emit
```

三层分工：`manager/` 管插座（按名加载插头），`signals/` 管暗号（`on` / `emit`），`host/` 只做装配和门面，把前两层接到 `lip`。改行为时 **以修改 `manager/`、`signals/` 为主**（插座加载改 `DriverManager.from_file`，事件暗号改 `PluginManager.on` / `emit`），不要在 `host/` 再写一套。

## 标准

### 1. 用插座，不 import 实现

想用「执行命令」，不要 import bash 那个包。从公共插座板按名字拿：

```python
plug = lip.get("exec_command", "bash")
plug.dispatch("bash", spec)
```

相当于：用电去插墙上的插座（`lip.get("exec_command", name)`），不要跑到发电厂去搬发电机（`import bash_plugin`）。插座背后是 bash 还是 pwsh，调用方不管。

插座由合同规定，不由任何一家实现规定：

```python
# 凡是占着 exec_command 的插头，必须有 dispatch
# 查表在 host/board.py，文件加载在 manager/driver.py
```

调用方只认合同。bash 整包重写或换掉，用 `exec_command` 的代码一行不用改，只要顶上去的实现合同合规。

这和 `bind_resources(binding, pool, ...)` 把 `pool` 当参数注入、自己不 import 某个 pool 实现，是同一招。

### 2. 插件之间不直接调，靠事件暗号

插件之间不互相 import，只监听约定好的暗号：

```python
lip.on("process/activate", handler)   # Activation 进入运行
lip.on("task/run", handler)           # Task 即将执行
```

发的人不知道谁在听，听的人不知道谁在发。暗号写在下面的事件地图里。一边坏了、换了，另一边不受影响，只要暗号不变。这层做在 `signals/manager.py` 的 `on` / `emit` 上，经 `host/events.py` 接到 `lip`。

| 暗号 | 何时发出 |
| --- | --- |
| `process/activate` | Process Activation 进入 Worker |
| `task/run` | Task Executor 即将跑一个 Task |

### 3. 装哪些插件只写配置，代码里不写死

代码不写「加载 bash 这个包」。装谁、挂到哪个插座、怎么配，只写 `composition.yaml`：

```yaml
sockets:
  exec_command:
    bash: tools/agent_tools/shell_tools/bash_plugin.py

plugins:
  - name: bash
    socket: exec_command
    config:
      timeout_ms: 60000
```

`sockets` 是 `(socket, name) → 文件` 的插座表，`plugins` 是实际启用并调用 `apply(lip, config)` 的装配清单。只提供 `dispatch` 的命令插件可以登记在 `sockets` 中供 `lip.get` 使用，不必列入 `plugins`。

想换实现：改插座表和装配清单中的 `name`（例如换成 `pwsh`）。某个插件坏了：从 yaml 卸掉或换掉。其它脚本不知道发生过什么。改配置 ≠ 改几十个脚本。

## 隔离

- 叶插件不得 import `manager`、`signals`、`host` 内部模块。能力从 `apply(lip, config)` 的 `lip` 进来（`lip.get` / `lip.on` / `lip.effect`）。
- `host/` 是唯一装配入口；叶插件不直接碰 `manager/` 或 `signals/`。
- `PLUGIN_NAME` 与插座表插头名一致，全局唯一。
