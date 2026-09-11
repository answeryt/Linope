# kernel — Durable Function Agent Runtime

## 文档状态

本文描述当前最小持久执行实现和后续能力边界。Signal、Timer、并行 Join、补偿及
外部数据库 Adapter 尚未实现，不能当作现有接口使用。

当前已经实现：

- `@process`、版本化 Process Registry 和稳定 Process/Run ID；
- Process Store、Activation 去重和终态拒绝；
- 按 `(process_id, run_id, command_index)` 保存的 Journal；
- Process Function 从固定初始输入重放，已完成 Task 不重复执行；
- 命令名称、版本或输入变化的非确定性检测；
- `@task`、同步/异步 Task Executor、重试、超时和资源 lease；
- durable child Process ID 与 Process Handle；
- 带 lease、fencing token、优先级和恢复能力的 Run Queue；
- Ingress、Worker 和 Agent = Service + Resources 装配；
- Resource definition、容量检查、lease 获取与释放；
- `complete` / `wait` 兼容返回模型。

下一阶段目标：

- durable signal、timer、sleep、并行 join、取消和补偿；
- SQLite、PostgreSQL、Redis 等 Store/Queue Adapter；
- pending Process 的跨进程恢复与 lease 续约；
- Process 等待时可以丢弃 Python coroutine 和计算资源，恢复后从 journal 重放；
- Context 的容量归 Resource 管，内容选择和压缩归 Context Policy 管。

## 定位

kernel 的最终装配关系保持为：

```text
Agent = Service + Resources
```

Service 描述输入如何进入系统、有哪些 Process、如何运行和恢复它们。Resources
描述容器与模型能够提供多少资源、资源归谁、活多久。用户不编写 Runtime 的固定
调度流程，只编写 Process 函数、Task 函数和 Policy，再由 Service 装配。

Agent 不是人格对象，也不是所谓 Main Agent。系统不需要 Main Agent / Sub Agent
层级，也不把 Agent Loop、Tool Loop 或 Event Loop 暴露成用户抽象：

```text
Agent
├── Service
│   ├── Ingress
│   ├── Durable Process Runtime
│   ├── Scheduler
│   ├── Journal / State Store
│   └── Process Definition × N
│       ├── Process Function
│       ├── Task Function × N
│       ├── Signal / Timer / Child Handle
│       └── Context Policy

```

## 为什么不能把执行制度写死在 handler 外面

迁移前 `ProcessRuntime.run_next()` 的执行边界是：

```text
取一个 Activation
→ 获取 Process 资源
→ 从头到尾执行一次 handler
→ handler 返回 complete / wait
→ Runtime 保存最终状态
```

这个旧模型适合短 handler，但不能自然表达：

- handler 中途发现上下文过长，执行压缩后继续；
- 启动另一个 Process，并持久等待它的结果；
- 同时启动多个 Process，等待全部或任意一个完成；
- 等待外部审批、Webhook、定时器或模型配额；
- 进程崩溃后从最后一个已完成副作用继续；
- 已完成支付后发货失败，按相反顺序执行补偿。

当前 Runtime 已改为从固定初始输入重放 Process Function，并让 `ctx.run()` 和
`ctx.start_process()` 生成稳定命令。`ctx.wait()` 仍保留兼容返回形式；后续将演化
为由 Journal Event 唤醒的 durable wait。Runtime 不保存 Python coroutine 调用栈。

## 从三个非 AI 持久执行项目得到的结论

本仓库包含 `restate-sdk-python/`、`dbos-transact-py/` 和
`temporal-sdk-python/` 三个参考项目。它们面向的是微服务、业务流程和分布式
执行；AI 只是可以运行在其上的一种负载。

三者共同采用：

```text
Workflow / Process Function
    只编排确定性控制流
            ↓
Task / Step / Activity
    承载 HTTP、数据库、模型、工具等副作用
            ↓
Journal / Step Result / Event History
    保存每个可恢复边界的输入、结果和错误
```

恢复时不是反序列化 live coroutine，而是重新执行 Process Function。已经完成的
Task 根据 journal 直接返回旧结果，未完成的 Task 才真正执行。

### Restate：durable async/await 和统一 Context

Restate 最值得借鉴的是让用户通过一个 Context 使用持久原语：

- `RestateDurableFuture` / `RestateDurableCallFuture`：调用结果可以直接
  `await`，但 Future 的完成状态由 journal 支撑；
- `run_typed()`：把任意同步或异步副作用变成有名字、有序列化和重试策略的
  durable action；
- `service_call()` / `workflow_call()`：调用并持久等待结果；
- `service_send()` / `workflow_send()`：只发送，不等待；
- `signal()`、`awakeable()` 和 Workflow `promise()`：等待外部输入；
- `sleep()`：不占住 live worker 的 durable timer；
- `random()`、`uuid()`、`time()`：把非确定性值稳定记录下来；
- Workflow key、状态和幂等键：保证同一逻辑实例的身份稳定。

对应源码：

- `restate-sdk-python/python/restate/context.py`
  - `RestateDurableFuture`
  - `RestateDurableCallFuture`
  - `Context.run_typed`
  - `Context.service_call` / `workflow_call`
  - `Context.signal` / `awakeable` / `sleep`
  - `WorkflowContext.promise`
- `restate-sdk-python/python/restate/workflow.py`
  - `Workflow.main`
  - `Workflow.handler`
- `restate-sdk-python/python/restate/service.py`
  - `Service.handler`
  - journal retention、幂等 retention、超时和 invocation retry 配置

kernel 需要借鉴它的 Context 形态和 durable call/send 区分，但不照搬
Service/Object/Workflow 三套用户概念。kernel 保留 Service 与 Process 两层，
对象状态、模型调用和工具调用都由 Task、State Store 与 Resource 表达。

### DBOS：普通函数、Step 结果和 PostgreSQL 恢复

DBOS 最值得借鉴的是很薄的函数式 API：

```python
@DBOS.step()
def step_one():
    ...

@DBOS.workflow()
def workflow():
    step_one()
```

关键能力包括：

- `@DBOS.workflow()` 与 `@DBOS.step()` 区分编排函数和副作用函数；
- Step 结果按 workflow ID 和执行序号保存，恢复时跳过已完成 Step；
- Workflow Handle 可以查询状态并等待结果；
- 子 Workflow、Queue、优先级、并发、限流和超时；
- `sleep`、`send` / `recv`、event 和 stream；
- 启动恢复时重新入队 pending workflow，避免多个恢复者重复执行；
- workflow fork、取消、恢复和执行历史管理。

对应源码：

- `dbos-transact-py/dbos/_dbos.py`
  - `DBOS.workflow` / `DBOS.step`
  - `start_workflow`、`sleep`、event、stream 和 queue 的公开入口
- `dbos-transact-py/dbos/_core.py`
  - `decorate_workflow` / `decorate_step`
  - `WorkflowHandleFuture`
  - `WorkflowHandlePolling`
  - `WorkflowHandleAsyncTask`
  - Step 执行、结果读取和确定性检查
- `dbos-transact-py/dbos/_recovery.py`
  - `_recover_workflow`
  - `recover_pending_workflows`
- `dbos-transact-py/dbos/_queue.py`
  - Queue 并发、限流和 worker 调度
- `dbos-transact-py/dbos/_sys_db.py`
  - Workflow 状态、operation result、message 与 event 持久化
- `dbos-transact-py/dbos/_workflow_commands.py`
  - `get_workflow`
  - `fork_workflow`
  - `delete_workflow`

kernel 需要借鉴它的低门槛装饰器、Step result 和 Handle，但不把 PostgreSQL
绑定进 kernel。Journal、Process Table 和 Queue 必须是 Host 注入的协议，可以
由内存、SQLite、PostgreSQL、Redis 或远程服务实现。

### Temporal：Workflow/Activity 隔离和确定性重放

Temporal 最值得借鉴的是对执行语义的严格分层：

- Workflow code 只做确定性编排；
- Activity 承载网络、数据库、文件、模型和工具等副作用；
- Workflow activation 驱动确定性 event loop；
- Activity、timer 和 child Workflow 都产生 command，并由历史事件完成；
- Signal 用于异步输入，Update 用于有结果的交互，Query 只读状态；
- Child Workflow Handle 支持等待、取消和 parent-close policy；
- `continue_as_new` 截断过长历史；
- sandbox、patch/version API 防止部署新代码后破坏旧历史重放；
- Worker 和 task queue 属于部署层，不进入业务 Process 定义。

对应源码：

- `temporal-sdk-python/temporalio/workflow/__init__.py`
  - Workflow 公开 API 汇总
- `temporal-sdk-python/temporalio/workflow/_definition.py`
  - `@workflow.defn` 与 `@workflow.run`
- `temporal-sdk-python/temporalio/workflow/_activities.py`
  - `execute_activity` / `start_activity`
- `temporal-sdk-python/temporalio/workflow/_workflow_ops.py`
  - `start_child_workflow`
  - `execute_child_workflow`
  - `continue_as_new`
- `temporal-sdk-python/temporalio/workflow/_handlers.py`
  - Signal / Update / Query 定义
- `temporal-sdk-python/temporalio/activity.py`
  - `@activity.defn`
  - Activity context、heartbeat 和取消
- `temporal-sdk-python/temporalio/worker/_workflow_instance.py`
  - activation、command、Future resolution 和 Workflow instance
- `temporal-sdk-python/temporalio/worker/workflow_sandbox/_runner.py`
  - Workflow sandbox 与受限执行

kernel 需要借鉴 Workflow/Activity 的隔离、activation/command 和版本语义，但
不在第一阶段实现 Temporal Server、跨语言协议、完整 sandbox 或自定义 asyncio
event loop。

## kernel 需要的功能

### 1. Process 与 Task 函数注册

需要：

```python
@process(...)
async def research(ctx, request):
    ...

@task(...)
async def search(ctx, query):
    ...
```

原因：

- Process Function 只表达控制流；
- Task Function 是副作用、资源申请、重试和结果持久化边界；
- Runtime 不再把所有 Agent 的流程固定成一个 handler 模板。

对应参考：DBOS `decorate_workflow` / `decorate_step`、Temporal
`workflow.defn` / `activity.defn`、Restate `Workflow.main` /
`Context.run_typed`。

现有 `Composition Plugin` 不删除。目标语义是：Composition 仍然是一组函数、资源要求、
生命周期和 hooks，但每次 Composition Function 调用都产生 durable Task Call，而
不是在 `ProcessRuntime.invoke()` 中直接裸调用函数。

### 2. Journal 与确定性重放

每个 Process 至少需要记录：

```text
process_id
process_type
definition_version
activation history
command sequence
task input / result / error
child process id / result
signal / timer
state snapshot
resource ownership metadata
```

`process_id` 表示长期稳定的逻辑 Process 身份，`run_id` 表示它的一次执行。
首次创建会同时生成两者；已终止的 Process 可以保留 `process_id` 并用新的
`run_id` 启动下一次执行。Store 必须保留 `(process_id, run_id)` 对应的历史
Run，并另外记录当前 `run_id`，不能用新 Run 覆盖旧 Run。

原因：Python coroutine 不能可靠序列化。Process 在等待时必须允许 worker
退出；恢复时重跑 Process Function，并按命令序号复用 journal 中的结果。

建议命令身份由以下字段组成：

```text
process_id + run_id + command_index + explicit_key? + definition_version
```

任何直接产生非确定性的操作都必须禁止或通过 Context 记录，包括当前时间、
随机数、UUID 和未包装的 I/O。

### 3. Durable Task Call

目标接口：

```python
result = await ctx.run(search_web, query)
```

Runtime 行为：

```text
生成 TaskCall
→ 检查 journal 是否已有结果
→ 没有结果时申请 Task 所需资源
→ 执行或派发 Task
→ 原子保存结果
→ 释放 execution/task scope 资源
→ 唤醒 Process
```

原因：模型、工具、HTTP、数据库和 Sandbox 都可能失败或产生外部副作用，不能
因为 Process 重放而无条件重复执行。

### 4. Child Process Handle

目标接口：

```python
handle = await ctx.start(search_process, request, key="search:42")
result = await handle.result()
```

Handle 至少提供：

- `process_id`
- `result()`
- `status()`
- `cancel()`
- `signal(name, value)`

原因：仅有 `caused_by` 只能追踪因果关系，不能表达等待、取消和结果传播。
Process 仍然不是“子 Agent”；Handle 只表示一个被调用的 Process 实例。

### 5. Signal、Promise 与 Timer

目标接口：

```python
approval = await ctx.signal("approval", timeout="24h")
await ctx.sleep("30s")
```

原因：人类审批、Webhook、工具回调、限流恢复和定时任务都不应该占用 live
coroutine、CPU、模型并发或 Sandbox。

Signal 可以多次投递；Promise/Event 默认一次完成；Timer 由 Scheduler 或 Host
持久化唤醒。

### 5.1 Continuation 与自主执行

`wait()` 表示当前 Execution 无法继续，`continuation()` 表示 Process 明确请求
下一次 Execution。Process 只能持久化这个意图，最终执行权属于 Scheduler：

```python
when = (
    after(600)
    & once(event("market.updated"))
    & ~event("user.cancelled")
)
return ctx.continuation(
    {"previous_result": result},
    when=when,
    reason="continue_monitoring",
)
```

`continuation()` 只登记“当这个表达式成立时再次激活我”。`when` 是可组合的
Expression Tree：`&` / `|` / `~` 做逻辑组合，`once` 锁存第一次成立，
`within` 限制时间窗口，`then` 按事件游标要求先后顺序。新的主动事实通过
Primitive Registry 注册，不必修改 Continuation 或 Scheduler 主流程。

一个 Run 可以包含多个 Execution。每个 Execution 消费一个 Activation，并使用
该 Activation 的 input；`initial_input` 仍可通过 Process Context 单独读取。

### 6. 并行、join 与结构化取消

目标接口：

```python
handles = [await ctx.start(fetch, item) for item in items]
results = await ctx.gather(handles)
```

需要支持：

- all / any；
- fan-out / fan-in；
- parent 取消时对子 Process 的可配置策略；
- Process 完成前处理未完成的 child/task；
- 并行结果在 journal 中保持确定顺序。

原因：普通 `asyncio.gather()` 的 Future 不能跨 worker 重启，必须由 durable
handle 和 journal 实现。

### 7. Retry、Timeout、Cancellation 与 Compensation

Task 和 Process 分别配置：

```text
max_attempts
initial_interval
backoff
max_interval
schedule_timeout
execution_timeout
non_retryable_errors
cancellation_policy
```

分布式业务流程还需要 Saga 补偿：

```python
reservation = await ctx.run(reserve_inventory, order)
ctx.defer(release_inventory, reservation)
```

如果后续支付失败，Runtime 按相反顺序执行已注册补偿。原因是多个微服务之间
不存在一个可以包住全部副作用的本地数据库事务。

### 8. State、Context Store 与 Context Policy

Resource 负责容量、所有权、scope 和 lease；它不负责理解消息内容。

Context 应拆成：

```text
Context Resource
    token 容量、模型配额、scope、lease

Context Store
    messages、artifacts、summary、memory references

Context Policy
    select、estimate、compact、redact、retain
```

目标接口：

```python
if await ctx.context.should_compact():
    await ctx.run(compact_context, ctx.context.snapshot())
```

压缩通常调用模型，是副作用，因此也必须经过 Task journal。这样用户可以自己
编写压缩函数，也可以装配默认 Policy。

### 9. 原子提交、幂等与恢复竞争

必须避免：

```text
外部副作用已经成功
→ worker 崩溃
→ Task 结果尚未保存
→ 恢复后重复副作用
```

kernel 不能对任意外部系统承诺天然 exactly-once，只能组合：

- 稳定 idempotency key；
- transactional outbox/inbox；
- Task result 与本地事务原子提交；
- lease/claim 超时与 fencing token；
- 至少一次执行 + 幂等 Task。

恢复 pending Process 时必须先原子 claim，不能让多个 worker 同时恢复同一 run。
这一点对应 DBOS `_recovery.py` 的重新入队设计，也对应 Temporal/Restate 将执行
决定交给持久引擎。

### 10. 版本、历史长度与可观测性

Process 定义升级后，旧 journal 必须仍然可以重放。至少需要：

- `definition_version`
- Task/Process 稳定名称
- patch/version marker
- journal retention
- continue-as-new 或 history compaction
- Process/Task/Resource trace
- 查询、取消、重试、fork 和 replay 工具

否则修改函数中的分支或 Task 调用顺序，会让正在运行的 Process 得到不同命令
序列。

## 目标执行模型

```text
Ingress
→ ProcessActivation 去重
→ 创建或恢复 Process Run
→ 从头执行 Process Function
→ 遇到 ctx.run / start / signal / sleep
→ 生成确定性 Command
→ journal 有结果：立即重放结果
→ journal 无结果：挂起 Process 并调度工作
→ 工作完成后追加 Event
→ 新 Activation 恢复并重放 Process Function
→ return 时保存结果并终止
```

固定的是可靠性制度，不是用户业务流程：

```text
kernel 固定
    identity / journal / replay / scheduling / lease / retry / cancellation

用户决定
    Task 顺序 / 分支 / 并行 / 子 Process / 等待 / 压缩 / 补偿
```

## 目标用户 API：最终 Agent 如何拼装

下面代码是目标 API，用来约束后续实现，不表示当前模块已经提供这些装饰器。

```python
from kernel import (
    Agent,
    ContextPolicy,
    ProcessContext,
    RetryPolicy,
    compose_agent,
    compose_resources,
    define_resource,
    process,
    service,
    task,
)


# ---------- Resources ----------

cpu = define_resource(
    "cpu",
    kind="container",
    capacity=8,
    scope="service",
    persistence="persistent",
)

model = define_resource(
    "model",
    kind="model",
    capacity=4,
    scope="service",
    persistence="persistent",
)

task_context = define_resource(
    "task-context",
    kind="model",
    capacity=128_000,
    scope="process",
    persistence="persistent",
)

sandbox = define_resource(
    "sandbox",
    kind="container",
    capacity=4,
    scope="task",
    persistence="ephemeral",
)

resources = compose_resources(cpu, model, task_context, sandbox)


# ---------- User Task Functions ----------

@task(
    name="search-web",
    requires=["cpu", "sandbox"],
    retry=RetryPolicy(max_attempts=3, backoff=2),
)
async def search_web(ctx, query: str) -> list[dict]:
    # HTTP、浏览器、数据库、模型和工具调用只能放在 Task 中。
    return await ctx.tools.web_search(query)


@task(
    name="compact-context",
    requires=["model", "task-context"],
)
async def compact_context(ctx, messages: list[dict]) -> dict:
    return await ctx.models.summarize(messages)


@task(
    name="write-answer",
    requires=["model", "task-context"],
)
async def write_answer(ctx, payload: dict) -> str:
    return await ctx.models.generate(payload)


# ---------- User Process Functions ----------

@process(name="search", version="1")
async def search_process(ctx: ProcessContext, query: str) -> list[dict]:
    return await ctx.run(search_web, query, key=f"search:{query}")


@process(name="research", version="1")
async def research_process(ctx: ProcessContext, request: dict) -> str:
    # Child Process 是 durable handle，不是内存里的 asyncio.Task。
    searches = [
        await ctx.start(search_process, query, key=f"query:{index}")
        for index, query in enumerate(request["queries"])
    ]
    documents = await ctx.gather(searches)

    # Context 内容策略由用户函数决定，token 容量仍由 Resource 管理。
    if await ctx.context.should_compact(threshold=0.8):
        summary = await ctx.run(
            compact_context,
            ctx.context.messages(),
            key="compact:before-answer",
        )
        await ctx.context.replace_with(summary)

    if request.get("requires_approval"):
        approval = await ctx.signal("approval", timeout="24h")
        if not approval["accepted"]:
            return "request rejected"

    return await ctx.run(
        write_answer,
        {"request": request, "documents": documents},
        key="final-answer",
    )


# ---------- Policies, Service, Agent ----------

context_policy = ContextPolicy(
    resource="task-context",
    retain_recent=12,
    preserve_task_pairs=True,
    compactor=compact_context,
)

research_service = service(
    "research-service",
    ingress=ingress,
    processes=[research_process, search_process],
    journal=journal_store,
    state=process_store,
    queue=task_queue,
    policies=[context_policy],
)

agent: Agent = compose_agent(
    service=research_service,
    resources=resources,
)

await agent.run()
```

用户只需要编写：

- `@task` 函数：模型、工具、HTTP、数据库、Sandbox 和其他副作用；
- `@process` 函数：顺序、条件、并行、等待、子 Process 和补偿；
- Resource 与 Policy 定义；
- 最终 `service(...)` 和 `compose_agent(...)`。

用户不需要编写：

- Process 状态机切换；
- mailbox pump；
- journal replay；
- worker claim；
- retry timer；
- child result correlation；
- Resource lease 获取与释放。

## 与当前代码的迁移关系

已完成：

- [x] Journal record 与稳定 command index；
- [x] `@task`、Task result/error 和重放；
- [x] `@process`、版本化定义与 Process Function replay；
- [x] Child Process 的确定性 ID 与 durable Handle；
- [x] Process Store、Run Queue、Ingress 与 Worker Host Adapter；
- [x] Queue lease、fencing token、优先级和过期 claim 恢复；
- [x] Runtime 从 `kernel/async` 迁移到 `kernel/process/runtime`；
- [x] Task 定义与 Executor 迁移到 `kernel/compose/definition|executor`；
- [x] 删除 PCB、table、mailbox 和旧 scheduler 的重复内存事实来源。

后续计划：

- [ ] Signal、Timer 和 durable sleep；
- [ ] gather/any、取消与补偿；
- [ ] Context Store / Context Policy；
- [ ] SQLite、PostgreSQL、Redis Adapter；
- [ ] version marker、continue-as-new 和运维查询。

## 目录合同

```text
kernel/
├── services/
│   ├── app/                 Agent 装配
│   ├── ingress/             Activation 输入
│   ├── worker/              Worker 生命周期
│   ├── queue/               持久 Queue Adapter
│   ├── store/               Process Store Adapter
│   └── scheduler/           Continuation 表达式裁决
├── process/
│   ├── definition/          @process 与注册表
│   ├── activation/          Activation schema
│   ├── runtime/             Process Engine 与 command interpreter
│   ├── journal/             Command/Event 与 Replay
│   ├── lifecycle/           Process 状态转换
│   ├── state/               ProcessRun schema
│   ├── handle/              durable child handle
│   └── continuation/        Continuation Record 与 Expression
├── compose/
│   ├── definition/          @compose、重试与资源需求
│   ├── executor/            执行和结果提交
│   ├── binding/             Resource lease
│   ├── runtime/             ComposeRuntime 门面
│   └── capability/          能力图与 Composition
└── resource/
    ├── definition/
    └── pool/
```

行为测试分层与夹具约定见 [`tests/README.md`](../tests/README.md)。

目录名为 `compose`，避免与 Python `threading` 和 OS thread 混淆。对用户公开
的概念是可执行组装单元（`@compose`）与能力图上的 `Composition`。副作用仍通过
Process journal 记为 Task Call，对应 Restate action、DBOS step 和 Temporal
activity。

## 架构约束

1. Agent 严格等于 Service + Resources。
2. Service 是唯一部署边界。
3. Process 是可重放的 durable function，不是 OS process。
4. Task Function 是副作用、重试、资源和 journal 的最小边界。
5. Process Function 不得直接执行未记录的 I/O、时间、随机数或 UUID。
6. Scheduler 只决定何时运行，不决定用户业务流程。
7. Process 等待时必须释放不需要保留的计算资源。
8. Resource 管容量和所有权；Context Policy 管内容选择和压缩。
9. Ingress 传可序列化 Activation，不传 live Process 或 coroutine。
10. Process 之间使用 durable handle 与 `caused_by`，不引入主从 Agent 人格。
11. Host 注入 Store、Queue、Clock、Worker 和资源实现；叶插件不直接依赖部署 API。
12. 所有可重放定义和命令必须有稳定名称及版本。
13. kernel 对外部副作用默认提供 at-least-once；exactly-once 依赖幂等键或事务集成。
14. `PLUGIN_NAME` 必须以 `kernel_` 开头并全局唯一。

## 不采用的方向

- 不让用户手写 `ready/running/waiting/terminated` 状态机；
- 不尝试 pickle 或序列化 live coroutine；
- 不把整个 handler 当成一个不可恢复的大 Task；
- 不把 Context 压缩逻辑塞进通用 ResourcePool；
- 不把父子 Process 命名成 Main Agent / Sub Agent；
- 不在 kernel 叶模块中绑定 PostgreSQL、Redis、Temporal Server 或特定 Web 框架；
- 不用普通 `asyncio.Task/Future` 表示跨重启等待。
