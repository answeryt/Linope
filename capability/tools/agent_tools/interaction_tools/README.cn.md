# interaction_tools

[English](README.md) | 中文

向用户提一个问题，并等待宿主注入的回答。

## 契约

`ask_user_plugin.py` 的 `PLUGIN_NAME` 是 `ask_user`。schema 名是 `ask_user_question`。`load` 接受种类 `tool`。

正文是 `questions`，一个列表。每一项有稳定的 `id` 和 `question`。可选字段包括 `header` 和 `options`。如果某个选项是推荐选择，schema 让模型把它放在第一项，并在该标签后加上 `(Recommended)`。

回答由宿主注入的提供者产生。本插件自己不读终端。

## 模型体验

### 工具 schema

#### 模型看到什么

`tool_schemas()`：一个或多个问题，每个都按 `id` 回显。这个工具用于确认、选择或缺失的信息。它不是子代理的 `ask`。子代理移交在 [`kernel/command/process`](../../../../kernel/command/process/README.cn.md)。

#### Token 影响

插件可见时是一份固定 schema。结果是宿主返回的回答对象。

#### KV Cache 影响

插件不变时 schema 的前缀稳定。模型返回之后，回答追加。

## 已知限制与暂缓事项

- **没有注入的提供者就没有回答** — 插件等待宿主函数。缺少提供者时调用失败，而不是去读 stdin。
