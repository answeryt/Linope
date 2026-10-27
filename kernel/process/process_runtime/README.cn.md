# process_runtime

[English](README.md) | 中文

进程里面真正跑能力插件的地方。激活里写了要加载哪个文件，本目录把它装上，接到工作目录、环境变量和资源句柄，然后一直接请求，直到关掉。人敲的命令在 [`kernel/command`](../../command/README.cn.md)。`process start` 留在启动它的那个进程里；之后的 `load message` 和 `load tool` 打到这里已经打开的适配器上。

## 每个脚本

`adapter.py`

插件要做成的样子，名叫 `CapabilityAdapter`。句柄到了调用 `initialize`。一条请求走 `handle`，或者不占着线程干等时走 `handle_async`。停止前调用 `shutdown`。`is_async` 说它能不能异步。`sync_thread_safe` 说 [`kernel/thread`](../../thread/README.cn.md) 能不能给它开多个同步帮手。

`runtime.py`

`open_adapter` 先换上这次启动定好的工作目录，并核对要读的环境变量名字。代码里这一步叫 `apply()`，作用的对象是 [`kernel/environment`](../../environment/README.cn.md) 里的 `KernelEnvironment`。然后再按激活里的路径加载模块。某个模块有 `create_adapter` 时，用它造适配器并 `initialize`。没有的话，工作目录已经换好，但返回的是没有适配器。打开中途失败会先关掉已经造好的适配器，再把错误抛出去。

`close_adapter` 调用 `shutdown`。再关一次也没有事。

`serve_capability` 在同一次调用里打开再关掉，并在结束时用 pid 回调 `on_exit`。适合跑完就走的一次。

`serve_stdio` 是这个进程自己的循环。先读一行启动 JSON，里面必须有 `activation`。然后每来一行请求就交给适配器，把回复写回标准输出，直到管道关掉。它不决定调用方要不要只跑一件事。

`__main__.py`

作为程序入口时调用 `serve_stdio`。什么时候退出由拉起它的一方决定。

`__init__.py`

对外仍给出 `CapabilityProcess`、`ProcessActivation`、`ProcessStatus`。这三个名字真正定义在 `process_manager` 和 `process_creat`，这里晚点导入，避免两边互相导入。
