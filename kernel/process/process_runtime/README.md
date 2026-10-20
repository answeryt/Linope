# process_runtime

这个目录准备进程里面要跑的程序。

`runtime.py` 的 `open_adapter` 会按激活信息装上插件并留到进程关闭。`serve_capability` 仍是装上后立刻关掉，给不停留的调用用。`linope process start` 走 `open_adapter`，之后的 `load` 交给这个适配器。

`adapter.py` 约定插件适配器要有三个动作：拿到句柄后初始化、处理一次业务请求、停止前清理。模型插件目前只提供档案函数和 `load`，启动命令还不会把一句话送到 `load`。

命令行在 `kernel/command`。
