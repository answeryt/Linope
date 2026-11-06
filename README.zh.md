<p align="center">
  <img src="image.png" alt="LINOPE-KERNEL" width="720">
</p>

# Linope

[English](README.md) | 中文

Linope 是一个灵活、通用的轻量级 Agent 内核。模型、搜索、文件处理和上下文处理都是能力。一种能力是一个平级进程，自己持有资源租约。进程之间没有父子关系。

Linope 借鉴传统操作系统内核的开发思想来构建 Agent 内核。模型会不断更新换代，许多Agent架构里面的逻辑和机制都要变化，这是很多开发者的苦恼，Linope想通过维护一个灵活且稳定的内核来避免这种情况。稳定的机制放在内核里，未来的开发主要是维护这一套内核。

[技术报告](<linope-agent-kernel.pdf>) 讲为什么能力是进程、为什么没有父子进程，以及 memory 和页面怎么配合。

哪些地方还没在真实环境里跑过，写在 [现状.md](现状.md)。

如果你想学习 Linope 的命令行，请阅读[命令行文档](kernel/command/README.cn.md)。

## 快速开始

需要 Python 3.11 或更高版本。Linope终端还需要 Node.js 20 或更高版本。

```sh
pip install linope
linope
```

安装一次之后，下一次使用直接在终端中输入 `linope` 即可。

## 创建环境变量并发送消息

进入窗口后，先创建密钥文件，再加载它，然后启动进程。一次只写一个变量，名字用 `OPENAI_API_KEY`。接口地址和模型名写在启动那一行。

```text
create capability/.env -- OPENAI_API_KEY=你的API密钥
load env capability/.env
process start agent_loop
```

你需要记下 agent_loop 进程号（如果忘记，可以用 list 命令来查看）。

运行时会自动提供模型所需的核心协议。

```text
load message <agent_loop进程号> -- 你的消息
```

各目录的说明：

| 文档 | 内容 |
|---|---|
| [kernel/README.cn.md](kernel/README.cn.md) | 进程、资源、调度和命令 |
| [capability/README.cn.md](capability/README.cn.md) | 模型和工具插件 |
| [tui/README.cn.md](tui/README.cn.md) | Linope终端 |
| [example/README.md](example/README.md) | 一个模型和一个搜索进程 |

如果你觉得这个项目的设计思想有意思，对你有启发，欢迎satr，提交issue和PR。
也欢迎且感谢大家在别的网站宣传Linope项目或者技术报告。
