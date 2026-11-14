# model_scheduler

[English](README.md) | 中文

这里调度模型这一类 CPU 式计算资源，不调度模型进程。`Book` 维护
一条共享的 ready、using、waiting task 队列；同时最多有配置数量的
task 可以执行 `model run`，每条占一个模型核。还没有拿到核的 task
不预先绑定核，哪个核先空出来就把 ready 队头给哪个核。

读文件、搜索、跑命令、启动工具都是等待。task 进入等待后，模型让给
队头的另一条 task；等待结束的 task 回到共享 ready 队尾。模型调用
已经开始后，必须让它完成。连续的 `model run` 仍留在原核，直到
进入等待或回合结束。

模型核数量由 `model cores <数量>` 设置，默认是一核。模型卡片由
`model use` 安装到每一个核，真正执行由 `model.py` 调用
`capability.model.model_runtime`。模型没有 pid，也不进入进程资源账本。
