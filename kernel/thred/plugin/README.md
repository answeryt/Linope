# kernel/thred/plugin

本目录是 Host 侧插件运行时。叶插件不 import 具体实现，只认插座、事件暗号和装配图。

## 通俗架构说明

`kernel/thred` 可以理解成一套“工作线程加工厂”：

- `definition` 负责写 Thred 说明书。
- `executor` 负责根据接口名称找到并执行对应 handler。
- `binding` 负责给 Thred 绑定资源。
- `runtime` 负责把上述能力编译成用户侧的 `lip_thred_runtime`。
- `context` 目前为空，运行上下文由外部系统提供。
- `plugin` 负责加载、组装和管理以上能力。

### 一、definition、executor、binding、runtime、context

#### 1. definition：Thred 说明书

文件：`kernel/thred/definition/thred_definition_plugin.py`

它主要说明“一个 Thred 是什么，以及它可以做什么”，负责：

- 定义 Thred 的名称和版本。
- 使用 `interfaces` 描述 Thred 对外公开的稳定接口。
- 使用 `handlers` 保存每个接口在当前 Python 运行时中的具体实现。
- 配置失败重试次数和重试间隔。
- 配置超时时间。
- 声明需要哪些资源。
- 配置资源生命周期和等待期间可以释放的资源。
- 把 Thred 登记到 `ThredRegistry`。

一份简单的说明书类似：

```python
{
    "name": "download",
    "version": "1.0",
    "kind": "thred",
    "interfaces": {
        "run": {
            "input_schema": "DownloadInput",
            "output_schema": "DownloadResult",
        }
    },
    "handlers": {"run": download_file},
    "retry": {"max_attempts": 3},
    "timeout": 30,
    "requires": ["network"],
    "lifetime": "execution",
}
```

`interfaces` 和 `handlers` 是两张使用相同名称的表：

- `interfaces["run"]` 是公开合同，说明调用名称、输入和输出等信息。
- `handlers["run"]` 是本地实现，保存真正执行的 Python 函数。
- 两张表的名称必须完全一致；有接口却没有 handler，或者有 handler 却没有接口，都会被拒绝。

这样 Process 只需要记录稳定的 `Thred 名称 + 版本 + 接口名称 + 输入`，不需要把 Python 函数保存到 Journal。运行时再通过 `ThredRegistry` 找到说明书，通过 `handlers` 找到实现。

主要接口：

- `define_thred()`：直接创建 Thred 说明书。
- `@thred()`：使用装饰器定义 Thred。
- `ThredRegistry`：Thred 登记簿，可以注册、查找和列出 Thred。

装饰器示例：

```python
@thred(
    name="download",
    version="1.0",
    interfaces={
        "run": {
            "input_schema": "DownloadInput",
            "output_schema": "DownloadResult",
        }
    },
    requires=["network"],
    timeout=30,
)
def run(value):
    url = value["url"]
    return download_file(url)
```

一个 Thred 也可以公开多个接口：

```python
definition = define_thred(
    "worker",
    {
        "run": run,
        "stop": stop,
    },
    interfaces={
        "run": {
            "input_schema": "RunInput",
            "output_schema": "RunResult",
        },
        "stop": {
            "input_schema": "StopInput",
            "output_schema": "StopResult",
        },
    },
    requires=["network"],
)
```

上面传给 `define_thred()` 的第二个参数是 handler 表，`interfaces` 是对外合同。Process 调用 `worker.run`，Executor 最后执行 `handlers["run"]`。

通俗地说，`definition` 就是填写工作单，写清楚：

> 叫什么、对外开放哪些接口、每个接口由谁实现、需要什么资源、失败后重试几次。

#### 2. executor：Thred 执行者

文件：`kernel/thred/executor/thred_executor_plugin.py`

`ThredExecutor.execute()` 会按照下面的顺序执行：

1. 读取 Thred 说明书。
2. 选择需要调用的公开接口。
3. 找到该接口对应的 handler，并根据其函数签名准备参数。
4. 申请本次执行需要的资源。
5. 调用同步或异步函数。
6. 检查是否超时。
7. 失败时按照说明书重试。
8. 执行结束后释放资源。
9. 返回执行结果。

它支持：

- 普通同步函数。
- `async` 异步函数。
- `function(input)`。
- `function(context, input)`。
- 无参数函数。
- 超时控制。
- 重试、重试间隔和退避倍率。
- 资源申请与释放。
- 在一个 Thred 公开多个接口时，通过 `interface` 指定需要调用的接口。

接口选择规则：

1. 调用方明确传入 `interface` 时，执行对应 handler。
2. 没有指定并且存在 `run` 时，默认执行 `run`。
3. 没有 `run` 但只有一个接口时，执行唯一接口的 handler。
4. 有多个接口并且无法确定时，要求调用方明确指定。

例如：

```python
result = await executor.execute(
    definition,
    input={"url": "https://example.com"},
    interface="run",
)
```

通俗地说：

> `executor` 是施工人员，拿到工作单后领取工具、开始工作、失败后重试，最后归还工具。

#### 3. binding：给 Thred 绑定资源

文件：`kernel/thred/binding/thred_binding_plugin.py`

主要接口：

- `build_binding()`：创建绑定记录。
- `bind_resources()`：申请并绑定资源。
- `release_resources()`：释放已经绑定的资源。

例如，一个 Thred 长时间需要：

- GPU。
- 数据库连接。
- 网络端口。
- 工作线程。

可以先绑定这些资源，等整个 Thred 工作结束后再释放。

如果申请多个资源时中途失败，`binding` 会把之前已经申请成功的资源退回去，避免资源泄漏。

通俗地说：

> `binding` 相当于给一个工作组长期预订办公室、电脑和设备。

它与 `executor` 的资源使用方式不同：

- `executor` 申请的是本次函数执行需要的资源，执行结束后立即释放。
- `binding` 申请的是整个 Thred 生命周期需要的资源，通常保持得更久。

#### 4. context：目前是空目录

当前 `kernel/thred/context` 没有脚本，因此不提供独立模块。

执行上下文由外部运行系统传给 `executor`，其中可以包含：

- 当前 `process_id`。
- 当前 `run_id`。
- 当前执行到第几个命令。
- 函数运行时需要的数据。

`plugin/host/lip.py` 中也有一个 `Context`，但它是插件装配上下文，负责：

- 保存已经加载的模块。
- 保存已经发布的服务。
- 管理事件。
- 管理插件卸载。

这两种上下文用途不同：

- 执行上下文服务于一次函数调用。
- Host `Context` 服务于整个插件系统。

### 二、plugin：工厂管理系统

`kernel/thred/plugin` 不负责具体业务，而是负责：

- 读取配置。
- 找到并加载模块。
- 检查模块格式。
- 按正确顺序组装模块。
- 对外发布服务。
- 管理事件。
- 卸载插件并清理资源。

#### 1. composition.yaml：组装清单

文件：`kernel/thred/plugin/composition.yaml`

它记录：

- 有哪些 Socket 工具。
- 有哪些业务叶模块。
- 有哪些 Recipe 组装插件。
- 每个模块对应哪个 Python 文件。

目前登记的四个核心叶模块是：

- `kernel_thred_definition`
- `kernel_thred_executor`
- `kernel_thred_binding`
- `kernel_thred_runtime`

通俗地说：

> `composition.yaml` 是工厂的设备清单和组装图纸。

插件系统不会自动使用目录中新出现的 Python 文件。模块必须在配置中登记，系统才会加载。

#### 2. runtime：由用户编译 lip_thred_runtime

主要文件：`kernel/thred/runtime/thred_runtime_plugin.py`

它提供 `compile_runtime()`，把用户选择的能力编译成轻量的 `lip_thred_runtime`：

- `definition`：定义和登记 Thred。
- `executor`：执行 Thred 导出的函数。
- `binding`：可选，绑定和释放资源。
- `extensions`：可选，在基础能力上扩展 Runtime。

编译后的 Runtime 直接复用 definition 的接口；调用 Runtime 本身等价于 `@thred()` 装饰器：

- `define_thred()`：创建 Thred 定义。
- `thred()`：Definition 装饰器，也可通过调用 Runtime 本身使用。
- `define()`：定义并登记 Thred。
- `register()`：登记已有 Thred。
- `get()`、`require()`、`all()`：查询已登记的 Thred。
- `execute()`：执行 Thred 的函数。
- `build_binding()`：创建资源绑定。
- `bind()`：绑定资源。
- `release()`：释放资源。

Runtime 编译器不依赖 Host，也不会固定发布服务。用户可以自行决定变量名和服务名：

```python
compiler = lip.module("kernel_thred_runtime")
lip_thred_runtime = compiler.compile_runtime(
    definition=lip.module("kernel_thred_definition"),
    executor=lip.module("kernel_thred_executor"),
    binding=lip.module("kernel_thred_binding"),
)

@lip_thred_runtime(
    retry={"max_attempts": 3},
    timeout=30,
    requires=["gpu"],
)
async def generate(input):
    return input
```

#### 3. host：插件系统总管

`plugin/host` 负责真正加载和管理插件：

- `loader.py`：读取 `composition.yaml`，加载 Recipe，并按依赖顺序执行 `apply()`。
- `lip.py`：提供统一入口，用于获取模块、发布服务、监听事件和卸载插件。
- `file_loader.py`：从指定 Python 文件加载模块，并处理缓存和清理。
- `module_loader.py`：加载 definition、executor、binding 等普通叶模块。
- `recipe_loader.py`：加载用户自行提供的组装 Recipe。
- `socket_loader.py`：加载 Socket 工具，并检查是否存在 `dispatch()`。
- `board.py`：统一管理和查找 Socket、普通模块。
- `protocol.py`：检查 Recipe 是否具有 `PLUGIN_NAME` 和 `apply()`。
- `events.py`：创建事件管理器。

通俗地说：

> `host` 是工厂总管，负责开门、搬入设备、安排车间、登记服务，关门时清理现场。

#### 4. manager：底层模块加载工具

`plugin/manager` 主要来自 stevedore，提供通用插件加载能力：

- `extension.py`：插件对象和插件管理器的基础实现。
- `driver.py`：加载一个指定驱动，当前文件加载主要使用它。
- `named.py`：只加载指定名称的插件。
- `enabled.py`：按照条件筛选插件。
- `dispatch.py`：根据条件把调用分发给不同插件。
- `hook.py`：让多个插件共同响应一次调用。
- `cache.py`：缓存 Python entry point 信息。
- `sphinxext.py`：生成插件文档时使用。

当前主要使用：

```text
DriverManager.from_file()
```

它根据配置中的路径直接加载 Python 文件。其他能力属于通用基础设施，目前没有全部用到。

#### 5. signals：事件广播系统

`plugin/signals` 主要来自 pluggy，负责事件和 Hook：

- `manager.py`：订阅、触发和取消订阅事件。
- `hooks.py`：定义 Hook 规范和 Hook 实现。
- `callers.py`：真正调用多个 Hook。
- `result.py`：保存调用结果或异常。
- `tracing.py`：跟踪 Hook 调用。
- `warnings.py`：处理 Hook 警告。
- `compat.py`：兼容上游发行版元数据接口。

简单事件流程：

```text
lip.on("事件名称", 处理函数)
        ↓
lip.emit("事件名称", 数据)
        ↓
依次调用所有处理函数
```

通俗地说：

> `signals` 类似工厂广播。例如广播“Thred 开始执行”，所有关注这个消息的部门都可以响应。

README 中约定了 `thred/run` 事件名称，但当前 `executor` 还没有真正发送这个事件。

#### 6. exception.py 和包入口

- `plugin/exception.py`：定义插件找不到、找到多个等异常。
- `plugin/__init__.py`：标记这是一个 Python 包。
- `host/__init__.py`：对外暴露 `Context`、`LoadError` 和 `load_composition`。

### 三、它们之间的关系

完整组装关系：

```text
composition.yaml
       ↓
host/loader.py 读取配置并加载叶模块
       ↓
用户调用 compile_runtime()
       ├── definition：Thred 说明书
       ├── executor：执行 Thred 函数
       └── binding：绑定资源（可选）
       ↓
得到 lip_thred_runtime
```

一次执行的关系：

```text
definition 定义并登记 Thred
            ↓
lip_thred_runtime 查找 Thred 和公开接口
            ↓
executor 找到接口 handler 并申请执行资源
            ↓
执行函数，处理超时和重试
            ↓
释放执行资源并返回结果
```

长期资源绑定是另一条流程：

```text
definition 定义 Thred
            ↓
binding 创建绑定
            ↓
绑定 Thred 长期需要的资源
            ↓
外部系统使用 Thred
            ↓
binding 释放资源
```

需要注意：`execute()` 不会自动调用 `binding`。函数执行和长期资源绑定是两条相关但相对独立的流程，调用方需要根据资源生命周期明确选择。

### 最简单的总结

- `definition`：写 Thred 说明书。
- `executor`：按照说明书执行 Thred 函数。
- `binding`：给整个 Thred 长期预订资源。
- `context`：目前为空，执行上下文由外部系统提供。
- `plugin/host`：负责加载和管理。
- `plugin/manager`：提供底层插件加载工具。
- `plugin/signals`：提供事件广播。
- `runtime`：把用户选择的叶模块编译成 `lip_thred_runtime`。
- `composition.yaml`：告诉系统应该加载哪些模块。
- `plugin/recipes`：可选，留给用户自行编写 Host 装配 Recipe。

## 插件目录与装配细节

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
├── recipes/                  可选：用户自行编写的 Host 装配 Recipe
└── host/                     装配与门面（本仓库自写）
    ├── __init__.py           公共门面：Context, load_composition
    ├── protocol.py           Host 装配合同：PLUGIN_NAME / apply
    ├── lip.py                运行时：provide / get / on / emit / effect
    ├── loader.py             读 composition.yaml 并安排 Recipe 生命周期
    ├── file_loader.py        公共的仓库内文件加载与缓存
    ├── socket_loader.py      只负责通过 socket 挑选工具
    ├── module_loader.py      只负责加载原始业务叶模块
    ├── recipe_loader.py      只负责通过 path 加载组装 Recipe
    ├── board.py              对外提供 socket/module 查询
    └── events.py             把 signals 接到 lip.on / emit
```

三层分工：`manager/` 管插座（按名加载插头），`signals/` 管暗号（`on` / `emit`），`host/` 只做装配和门面，把前两层接到 `lip`。改行为时 **以修改 `manager/`、`signals/` 为主**（插座加载改 `DriverManager.from_file`，事件暗号改 `PluginManager.on` / `emit`），不要在 `host/` 再写一套。

## 合同与当前插件分类

Linope 中的“插件”有三层合同，不能把它们混成一条规则：

| 合同 | 适用对象 | 必须满足 |
| --- | --- | --- |
| CI 叶插件合同 | 项目内所有业务 `*_plugin.py` | 顶层声明 `PLUGIN_NAME`、`PLUGIN_VERSION`，遵守目录、命名、隔离和注入规则 |
| Socket 插头合同 | 需要通过 `lip.get(socket, name)` 查找的能力实现 | 满足对应 socket 的行为合同；例如 `exec_command` 必须提供 `dispatch` |
| Host 装配合同 | 列入 `composition.yaml` 的 `plugins`、由 Host 管理生命周期的装配插件 | 声明 `PLUGIN_NAME`，实现 `apply(lip, config)`；可选声明 `PLUGIN_INJECT`、`PLUGIN_CONFIG` |

普通业务叶插件只需要满足 CI 合同，不要求实现 `apply`。它可以自由暴露函数、类、工厂或数据定义。只有主动成为 Host 装配单元的模块，才需要满足 Host 装配合同。Socket 插头也不等于 Host 装配插件：只登记在 `sockets` 中的实现不需要 `apply`。

### 当前状态

以下结果来自对 Linope 业务源码的静态扫描，不包含 `temporal-sdk-python` 等仓内第三方项目的 `_plugin.py`：

| 分类 | 数量 | 插件 |
| --- | ---: | --- |
| 仅满足 CI 叶插件合同 | 113 | 除下面三个命令插头外的所有业务插件 |
| 同时满足 CI 与 Socket 插头合同 | 3 | `bash_plugin.py`、`pwsh_plugin.py`、`bash_persistent_plugin.py` |
| Host 装配插件 | 0 | 当前默认 composition 不加载固定 Recipe |
| 同时满足 CI 叶插件与 Host 装配合同 | 0 | 业务叶插件不承担装配职责 |

三个命令插头已经登记在 `composition.yaml` 的 `sockets.exec_command` 中并提供 `dispatch`，但没有实现 `apply`，所以不能列入 `plugins` 装配清单。

`kernel_thred_runtime` 是业务叶插件，不是 Host Recipe。它只提供 `compile_runtime()`；调用方自行选择 definition、executor、binding，并把结果保存为 `lip_thred_runtime`。叶模块自身仍不知道 Host。

### 业务插件清单

| 分类 | 目录 | 插件 |
| --- | --- | --- |
| 仅 CI | `adapter_layer/` | `function_call_plugin.py` |
| 仅 CI | `kernel/resource/definition/` | `resource_definition_plugin.py` |
| 仅 CI | `kernel/resource/pool/` | `resource_pool_plugin.py` |
| 仅 CI | `kernel/thred/binding/` | `thred_binding_plugin.py` |
| 仅 CI | `kernel/thred/definition/` | `thred_definition_plugin.py` |
| 仅 CI | `kernel/thred/executor/` | `thred_executor_plugin.py` |
| 仅 CI | `kernel/thred/runtime/` | `thred_runtime_plugin.py` |
| 仅 CI | `kernel/process/activation/` | `process_activation_plugin.py` |
| 仅 CI | `kernel/process/definition/` | `process_definition_plugin.py` |
| 仅 CI | `kernel/process/runtime/` | `process_runtime_plugin.py` |
| 仅 CI | `kernel/process/journal/` | `journal_plugin.py` |
| 仅 CI | `kernel/process/lifecycle/` | `process_lifecycle_plugin.py` |
| 仅 CI | `kernel/process/state/` | `process_state_plugin.py` |
| 仅 CI | `kernel/process/handle/` | `process_handle_plugin.py` |
| 仅 CI | `kernel/process/continuation/` | `continuation_plugin.py`、`expression_plugin.py` |
| 仅 CI | `kernel/services/app/` | `service_plugin.py`、`registrator_plugin.py` |
| 仅 CI | `kernel/services/ingress/` | `ack_middleware_plugin.py`、`ack_policy_plugin.py`、`activation_envelope_plugin.py`、`activation_ingress_plugin.py`、`broker_plugin.py`、`exception_plugin.py`、`logging_plugin.py`、`middleware_plugin.py`、`ping_plugin.py`、`usecase_plugin.py` |
| 仅 CI | `kernel/services/queue/` | `run_queue_plugin.py`、`stream_subscriber_plugin.py` |
| 仅 CI | `kernel/services/scheduler/` | `continuation_scheduler_plugin.py` |
| 仅 CI | `kernel/services/store/` | `continuation_store_plugin.py`、`process_store_plugin.py` |
| 仅 CI | `kernel/services/worker/` | `app_plugin.py`、`application_plugin.py`、`cli_plugin.py`、`multiprocess_plugin.py`、`process_worker_plugin.py`、`watchfiles_plugin.py` |
| 仅 CI | `tools/agent_tools/file_tools/` | `edit_plugin.py`、`file_plugin.py`、`glob_plugin.py`、`grep_plugin.py`、`read_image_plugin.py`、`read_plugin.py`、`str_replace_editor_plugin.py`、`write_plugin.py` |
| 仅 CI | `tools/agent_tools/terminal_tools/` | `terminal_plugin.py`、`terminal_open_plugin.py`、`terminal_close_plugin.py`、`terminal_close_session_plugin.py`、`terminal_focus_plugin.py`、`terminal_list_plugin.py`、`terminal_preview_plugin.py`、`terminal_read_plugin.py`、`terminal_read_session_plugin.py`、`terminal_send_plugin.py`、`terminal_signal_plugin.py` |
| CI + Socket | `tools/agent_tools/shell_tools/` | `bash_plugin.py`、`bash_persistent_plugin.py`、`pwsh_plugin.py` |
| 仅 CI | `tools/agent_tools/subagent_tools/` | `interrupt_agent_plugin.py`、`list_agents_plugin.py`、`send_message_plugin.py`、`subagent_fork_plugin.py`、`subagent_plugin.py`、`subagent_report_plugin.py` |
| 仅 CI | `tools/agent_tools/session_query_tools/` | `session_event_read_plugin.py`、`session_event_search_plugin.py`、`session_event_trace_plugin.py`、`session_search_plugin.py`、`session_trace_plugin.py` |
| 仅 CI | `tools/agent_tools/workflow_tools/` | `ralph_plugin.py`、`workflow_plugin.py` |
| 仅 CI | `tools/agent_tools/vision_tools/` | `video_generation_plugin.py`、`vision_plugin.py` |
| 仅 CI | `tools/agent_tools/web_search_tools/` | `web_fetch_plugin.py`、`web_search_plugin.py` |
| 仅 CI | `tools/agent_tools/interaction_tools/` | `ask_user_plugin.py` |
| 仅 CI | `tools/agent_tools/plan_tools/` | `plan_mode_plugin.py` |
| 仅 CI | `tools/agent_tools/todo_tools/` | `todo_plugin.py` |
| 仅 CI | `tools/agent_tools/job_tools/` | `jobs_plugin.py` |
| 仅 CI | `tools/agent_tools/goal_tools/` | `goal_plugin.py` |
| 仅 CI | `tools/agent_tools/schedule_tools/` | `schedule_plugin.py` |
| 仅 CI | `tools/external_tools/mcp/` | `mcp_auth_security_plugin.py`、`mcp_config_plugin.py`、`mcp_content_plugin.py`、`mcp_host_manager_plugin.py`、`mcp_interaction_plugin.py`、`mcp_protocol_plugin.py`、`mcp_resilience_plugin.py`、`mcp_tool_manager_plugin.py` |
| 仅 CI | `sandbox/sandbox/src/` | `escalation_plugin.py`、`roots_plugin.py`、`sandbox_plugin.py` |
| 仅 CI | `sandbox/sandbox-local/src/` | `profiles_plugin.py`、`sandbox_local_plugin.py` |
| 仅 CI | `sandbox/sandbox-policy/src/` | `sandbox_policy_plugin.py`、`session_mode_plugin.py` |
| 仅 CI | `sandbox/sandbox-windows-acl/src/` | `acl_plugin.py`、`errors_plugin.py`、`ffi_plugin.py`、`grant_plugin.py`、`path_boundary_plugin.py`、`runner_plugin.py`、`spawn_plugin.py`、`token_plugin.py`、`win32_abi_plugin.py`、`windows_acl_plugin.py`、`workspace_sid_plugin.py` |
| 仅 CI | `ui/api/` | `ui_shell_plugin.py` |
| 仅 CI | `ui/cli/` | `ui_cli_plugin.py` |
| 仅 CI | `ui/open/` | `ui_open_plugin.py` |
| 仅 CI | `ui/server/` | `ui_server_plugin.py` |
| 仅 CI | `ui/startup/` | `ui_startup_plugin.py` |
| 仅 CI | `ui/static/` | `ui_static_plugin.py` |

`manager/`、`signals/`、`recipes/`、`host/` 是插件运行时基础设施，不是业务 `*_plugin.py`，因此不进入这张业务插件分类表。`runtime/` 是业务叶插件，由调用方编译，不由 Host 自动发布服务。

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
lip.on("thred/run", handler)          # Thred 即将执行
```

发的人不知道谁在听，听的人不知道谁在发。暗号写在下面的事件地图里。一边坏了、换了，另一边不受影响，只要暗号不变。这层做在 `signals/manager.py` 的 `on` / `emit` 上，经 `host/events.py` 接到 `lip`。

| 暗号 | 何时发出 |
| --- | --- |
| `process/activate` | Process Activation 进入 Worker |
| `thred/run` | Thred Executor 即将运行一个 Thred |

### 3. 装哪些插件只写配置，代码里不写死

代码不写「加载某个业务实现」。Socket 插头和原始叶模块都写在 `composition.yaml`：

```yaml
sockets:
  exec_command:
    bash: plugins/tools/agent_tools/shell_tools/bash_plugin.py

modules:
  kernel_thred_definition: kernel/thred/definition/thred_definition_plugin.py
  kernel_thred_executor: kernel/thred/executor/thred_executor_plugin.py
  kernel_thred_binding: kernel/thred/binding/thred_binding_plugin.py
  kernel_thred_runtime: kernel/thred/runtime/thred_runtime_plugin.py

plugins: []
sources: []
```

三部分职责不同：

- `sockets`：`(socket, name) → 文件`，由 `lip.get(socket, name)` 获取，并检查 socket 行为合同。
- `modules`：`PLUGIN_NAME → 文件`，由调用方使用 `lip.module(name)` 获取，只检查身份，不要求 `apply`。
- `plugins`：Host 生命周期清单。每项必须用 `path` 指向独立 Recipe，并实现 `apply(lip, config)`。这里禁止填写 `socket`。默认 composition 为空，因为 Thred Runtime 由用户编译，而不是由固定 Recipe 发布。
- `sources`：动态发现源，可选择 manifest 目录、旧 Python 目录、静态快照或
  Python Entry Points；默认留空，部署方显式决定允许加载的目录。

个性化组装写在调用方的普通 Python 代码中，通过 `compile_runtime()` 完成；不塞进 YAML，也不强迫业务叶插件采用统一构造方式。想换实现时修改 `modules` 映射，再重新编译 `lip_thred_runtime`。

Socket 和 Path 不互相兼容，也不互相替代：Socket 只负责“从同类工具中选择一个”，Path 只负责“找到并执行组装 Recipe”。

## 隔离

- 业务叶插件不得 import `manager`、`signals`、`host` 内部模块；需要组合时，由 Host 装配插件取得并注入能力。
- Host 装配插件从 `apply(lip, config)` 的 `lip` 取得能力（`lip.get` / `lip.on` / `lip.effect`）。
- `host/` 是唯一装配入口；业务叶插件和 Socket 插头不直接碰 `manager/` 或 `signals/`。
- `PLUGIN_NAME` 与插座表插头名一致，全局唯一。

这里的单脚本隔离约束只适用于业务叶插件。`manager/`、`signals/` 和
`host/` 是有明确依赖方向的运行时 package，允许包内相对 import：

```text
exception / protocol → manager / signals → host loaders → Context → loader
```

反向依赖不允许：`manager/`、`signals/` 不得 import `host/`，叶插件也不得
import 任何运行时内部模块。CI allow list 必须在 JSON、YAML、TOML 和
Markdown 四种卡片格式中统一豁免 `kernel/thred/plugin`，避免检查结果随
`--format` 改变。

## 通用能力装配

Host 统一的是插件的安装语义，而不是猜测任意业务函数的参数语义：

```text
ArtifactSource → PluginDescriptor → Assembler
                                     ↓
                           apply(Context, config)
                                     ↓
                     Capability + Effect + Fiber
```

- `contracts.py`：定义 Artifact、Capability、Requirement、Descriptor 和生命周期状态。
- `capabilities.py`：保存可替换能力，并在 provider 变化时通知消费者。
- `fiber.py`：管理 `PENDING → LOADING → ACTIVE → UNLOADING → DISPOSED`
  生命周期；必需能力消失时自动卸载，重新出现时自动激活。
- `sources.py`：提供 composition、静态快照、Entry Point、manifest 目录和旧
  `*_plugin.py` AST 索引。发现阶段不 import 插件。
- `assembler.py`：把任意发现源接到统一 Host。
- `services.py`：提供工具注册、模型 Adapter/Waterfall 和带依赖排序的 Pipeline。
- `bridges.py`：隔离旧 `tool_schemas/dispatch`、`call_api` 和转换函数 ABI；
  新插件不需要继续扩充这些启发式规则。

用户目录推荐显式提供 `plugin.toml`：

```toml
[plugin]
name = "my_tools"
version = "1.0"
kind = "tool"
source = "plugin.py"
requires = ["tools"]
```

部署方在 `composition.yaml` 中启用该目录：

```yaml
sources:
  - type: manifest
    roots: [plugins]
    recursive: true
    strict: true
```

运行时只依赖 `ArtifactSource.discover()`。CI 可以生成 descriptor JSON，再由
`StaticSnapshotSource` 读取；内核不会 import `ci_tools`。当前没有 manifest 的
旧插件可由 `PythonPluginSource` 静态识别，作为迁移兼容层。

插件依赖的是稳定能力名而不是具体插件路径：

```python
def apply(ctx, config):
    adapter = MyAdapter(config)
    ctx.get("llm").register_adapter(["my-provider"], adapter)
```

所有通过 Context 或领域 Service 完成的注册都归属于当前 Fiber，卸载时逆序
撤销。FSM 只管理插件生命周期；服务依赖、Middleware、Pipeline 和业务状态机
仍保持各自独立的语义。
