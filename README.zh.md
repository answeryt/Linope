<p align="center">
  <img src="image.png" alt="LINOPE-KERNEL" width="720">
</p>

# Linope

[English](README.md) | 中文

Linope 是一个 Agent 内核。模型、工具和上下文处理都是能力，由内核调度，而不是写进一个 Agent 实例的工作流里。

它的基本关系是 **Agent = 内核 + 能力**。一种能力是一个平级进程，并持有自己的资源租约。内核负责进程生命周期、资源、权限和进程之间的通信。模型根据当前页面，在仍然可用的能力之间做选择。

内核管理四种 Agent 资源：`memory`、`tool`、`sandbox`、`network`。CPU、磁盘和网络设备仍由宿主操作系统管理。

## 当前状态

Linope 仍在开发中，版本是 `0.0.1`。命令、资源记录和页面格式都可能调整。

## 运行

需要 Python 3.11 或更高版本。Linope终端还需要 Node.js 20 或更高版本。

### 从源码运行

```sh
git clone https://github.com/answeryt/Linope.git
cd Linope
pip install -e .
```

Windows 上打开终端：

```powershell
.\linope.cmd terminal
```

其他系统：

```sh
node tui/bin.js terminal
```

进入窗口后，先指出密钥文件，再启动能力进程。最小搜索示例见 [example/README.md](example/README.md)。

```text
load env capability/.env
process start model.openai_chat_model --with memory=search
process start tools.ddgs
```

`tools.ddgs` 使用单独安装的 [`ddgs`](https://pypi.org/project/ddgs/) 包。模型进程只从 `capability/.env` 读取自己卡片上写明的密钥名，例如 `OPENAI_API_KEY`。

## 文档

| 文档 | 内容 |
|---|---|
| [kernel/README.cn.md](kernel/README.cn.md) | 进程、资源、调度和命令 |
| [capability/README.cn.md](capability/README.cn.md) | 模型和工具插件 |
| [tui/README.cn.md](tui/README.cn.md) | 蓝色终端 |
| [example/README.md](example/README.md) | 一个模型和一个搜索进程 |
