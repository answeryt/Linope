<p align="center">
  <img src="image.png" alt="LINOPE-KERNEL" width="720">
</p>

# Linope

[English](README.md) | 中文

Linope 是一个 Agent 内核。模型、搜索、文件处理和上下文处理都是能力。一种能力是一个平级进程，自己持有资源租约。进程之间没有父子关系。

内核创建和回收这些进程，检查权限，并在它们之间传递请求。当前该搜索、读文件，还是直接回答，由模型看着页面再选。内核里不写某一种 Agent 的业务流程。

换模型、工具、提示词和权限，同一套内核可以做不同的事。内核管理四种 Agent 资源：`memory`、`tool`、`sandbox`、`network`。CPU、磁盘和网络设备仍由宿主操作系统管理。

## 快速开始

需要 Python 3.11 或更高版本。Linope终端还需要 Node.js 20 或更高版本。

```sh
git clone https://github.com/answeryt/Linope.git
cd Linope
pip install .
```

这一次会装上模型接口、`litellm`、`ddgs` 和 `mcp`。装好后，在终端输入：

```sh
linope
```

Windows 上，这个命令来自当前 Python 的 `Scripts` 目录。终端找不到 `linope` 时，在仓库目录里可以用 `.\linope.cmd`。

进入窗口后，先指出密钥文件，再启动能力进程。最小搜索示例见 [example/README.md](example/README.md)。

```text
load env capability/.env
process start model.openai_chat_model --with memory=search
process start tools.ddgs
```

模型进程只从 `capability/.env` 读取自己卡片上写明的密钥名，例如 `OPENAI_API_KEY`。

## 了解设计

[技术报告](linope_technical_report.zh.md) 讲为什么能力是进程、为什么没有父子进程，以及 memory 和页面怎么配合。

哪些地方还没在真实环境里跑过，写在 [现状.md](现状.md)。

各目录的说明：

| 文档 | 内容 |
|---|---|
| [kernel/README.cn.md](kernel/README.cn.md) | 进程、资源、调度和命令 |
| [capability/README.cn.md](capability/README.cn.md) | 模型和工具插件 |
| [tui/README.cn.md](tui/README.cn.md) | 蓝色终端 |
| [example/README.md](example/README.md) | 一个模型和一个搜索进程 |
