# compose 目录说明

`kernel/compose` 负责一件事：把一个可执行任务（Capability）从「怎么描述」走到「真正跑起来」。

| 目录 | 作用 |
| --- | --- |
| `definition/` | 任务长什么样：名称、版本、接口、重试和超时。 |
| `executor/` | 真正去执行：选接口、注入参数、超时与重试。 |
| `binding/` | 执行前向资源池借东西，结束后还回去。 |
| `runtime/` | 把上面三块接到一起，对外只留一个入口。 |
| `capability/` | 系统里有哪些可插拔能力，怎么选、怎么拼、怎么装起来。 |

## definition

写下任务说明书，并按「名称 + 版本」登记，方便以后查找和复用。

- `definition/compose_definition_plugin.py`：`define_compose` / `@compose` 装饰器，以及 `ComposeRegistry`。

## executor

按说明书执行任务：选哪个接口、参数怎么灌进去、失败是否重试、超时怎么停。执行前后会配合 binding 借资源和还资源。

- `executor/compose_executor_plugin.py`：执行器实现。

## binding

任务需要磁盘、网络、模型等资源时，向资源池申请；失败则全部回滚。释放可以重复调用，不会出错。

- `binding/compose_binding_plugin.py`：申请与释放资源租约。

## runtime

不自己发明逻辑，只把 definition、executor、binding 组装成 `ComposeRuntime`，外面只跟这一个对象打交道。

- `runtime/compose_runtime_plugin.py`：运行时门面。

## capability

能力系统回答四个问题，按目录分开：

| 目录 | 阶段 | 回答的问题 |
| --- | --- | --- |
| `capability/capability.py` | 能力声明 | 开发者如何写一个 Capability 子类？ |
| `capability/assembly/cap_bus.py` | 能力总线 | 注入后谁订阅、发布时谁接收？ |
| `capability/negotiation/` | 能力协商 | 名字有没有人提供、有没有冲突？ |
| `capability/graph/composition.py` | 能力图解析 | 依赖怎么排序，Composition 怎么 inject？ |
| `capability/assembly/` | 能力组装 | 资源盒子、服务登记、生命周期。 |

### 发布订阅

扫描已经去掉。接收者通过 `inject(capability, composition)` 进入广播系统：

```text
inject → Capability.on_injected() → cap_bus.subscribe
publish / request_async → Capability.on_request() → provide
```

开发者只写 `class MyCapability(Capability)`。宿主 import 插件包后，子类自动进入登记表，再 inject。内核四件启动时直接 inject，不再当磁盘插件扫。

- `capability.py`：基类、`inject`、`__init_subclass__` 登记。
- `assembly/cap_bus.py`：`subscribe` / `publish`，复用容器已有监听表。
- `discovery/loader.py`：`inject_capabilities` 对已 import 的类做 inject。
- `discovery/contracts.py`：说明书数据结构（`CapabilityRecord`、依赖条件）。
- `graph/composition.py`：需求 → 已登记类匹配 → 依赖图 → `Composition.inject`。

### negotiation（能力协商）

- `negotiation/capabilities.py`：能力登记表，负责注册、查询、别名、缺项检查。
- `negotiation/exception.py`：找不到、找到太多等运行时错误。

### assembly（能力组装）

- `assembly/context.py`：资源盒子 `ResourceContainer`，管生命周期、租约、广播和卸载。
- `assembly/file_loader.py`：仍可用于按路径加载模块，能力发现不再依赖它。
