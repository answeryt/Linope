<p align="center">
  <img src="image.png" alt="LINOPE-KERNEL" width="720">
</p>

# Linope

[English](README.md) | 中文

Linope 是一个 Agent 内核。模型、搜索、文件处理和上下文处理都是能力。一种能力是一个平级进程，自己持有资源租约。进程之间没有父子关系。

内核创建和回收这些进程，检查权限，并在它们之间传递请求。当前该搜索、读文件，还是直接回答，由模型看着页面再选。内核里不写某一种 Agent 的业务流程。

换模型、工具、提示词和权限，同一套内核可以做不同的事。内核管理四种 Agent 资源：`memory`、`tool`、`sandbox`、`network`。CPU、磁盘和网络设备仍由宿主操作系统管理。

[技术报告](<linope-agent-kernel.pdf>) 讲为什么能力是进程、为什么没有父子进程，以及 memory 和页面怎么配合。

哪些地方还没在真实环境里跑过，写在 [现状.md](现状.md)。

如果你想学习 Linope 的命令行，请阅读[命令行文档](kernel/command/README.cn.md)。

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

## 配置模型和 API 地址

本示例启动的是 `model.openai_chat_model`。它使用 OpenAI Chat 兼容接口。模型名称和 API 地址写在下面这份卡片里：

```text
capability/model/model_provider/openai_chat_model/openai_chat_model.json
```

主要修改这两个字段：

```json
{
  "model": "deepseek-flash",
  "base_url": "https://api.deepseek.com"
}
```

上面是当前项目的默认值。更换模型时，`model` 填服务商提供的模型 id，`base_url` 填对应的 API 访问地址，以服务商文档为准。`api_key_env` 是环境变量名，默认是 `OPENAI_API_KEY`，通常不用改。

注意：当前项目的进程声明和实际调用分别会读取卡片 JSON 与对应插件里的 `CARD_CONFIG`。因此，修改模型名称或 `base_url` 时，请同步修改：

```text
capability/model/model_provider/openai_chat_model/openai_chat_model_plugin.py
```

也就是把这两个文件中的 `model`、`base_url` 和 `api_key_env` 保持一致。若使用 Responses 接口，则对应修改：

```text
capability/model/model_provider/openai_response_model/openai_response_model.json
capability/model/model_provider/openai_response_model/openai_response_model_plugin.py
```

## 创建环境变量

环境变量写在：

```text
capability/.env
```

如果这个文件不存在，就在仓库根目录下创建它。文件内容是一行一个变量，例如：

```dotenv
OPENAI_API_KEY=你的API密钥
```

变量名必须和模型卡片中的 `api_key_env` 一致。进入 Linope 终端后，先执行：

```text
load env capability/.env
```

然后再启动模型和工具进程。`.env` 里保存的是密钥，不要把真实密钥写进文档、提交到 Git，或发给其他人。

各目录的说明：

| 文档 | 内容 |
|---|---|
| [kernel/README.cn.md](kernel/README.cn.md) | 进程、资源、调度和命令 |
| [capability/README.cn.md](capability/README.cn.md) | 模型和工具插件 |
| [tui/README.cn.md](tui/README.cn.md) | Linope终端 |
| [example/README.md](example/README.md) | 一个模型和一个搜索进程 |

如果你觉得这个项目的设计思想有意思，对你有启发，欢迎satr，提交issue和PR。
也欢迎且感谢大家在别的网站宣传Linope项目或者技术报告。
