# system

[English](README.md) | 中文

linope 代理的系统提示词文本。

| 文件 | 职责 |
|---|---|
| [`identity.md`](identity.md) | 一行身份：linope 终端里的 linope 代理 |
| [`system_02_tools.md`](system_02_tools.md) | 文件、shell、网页、目标和子代理调用的路由文本 |

## 模型体验

### 系统提示词

#### 模型看到什么

`identity.md` 和 `system_02_tools.md` 是稳定的提示词文本。`system_02_tools.md` 里的工具 JSON 形状点名能力 id，例如 `tools.read` 和 `tools.pwsh`。进程实际暴露的工具 schema 在 [`capability/tools/agent_tools`](../../../tools/agent_tools/README.cn.md) 下的每个插件上。

#### Token 影响

宿主插入这两份文件时，是它们的全文。本目录不截断它们。

#### KV Cache 影响

两份文件都不改时，前缀稳定。编辑其中任一文件，从前缀的该处起发生变化。

## 已知限制与暂缓事项

- **本目录没有加载器** — 这里没有东西把 Markdown 抄进模型请求或记忆的 `system` 行。
- **有些点名的工具在这里没有插件** — `system_02_tools.md` 让模型调用 `tools.job_output`、`tools.job_kill`、`tools.get_goal`、`tools.create_goal` 和 `tools.update_goal`。这些插件不在 `agent_tools` 里。
