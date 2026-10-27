# web_search_tools

[English](README.md) | 中文

每个搜索提供者一个插件。`load` 接受种类 `tool` 和一个带 `query` 的映射。`capability_profile` 声明进程。插件互不导入。

| 插件 | `PLUGIN_NAME` | 提供者 |
|---|---|---|
| `ddgs_plugin.py` | `ddgs` | 已安装的 `ddgs` 包。`limit` 是 1–10，默认 5。返回标题、URL 和描述。 |
| `brave_free_plugin.py` | `brave_free` | Brave Search API |
| `exa_plugin.py` | `exa` | Exa |
| `tavily_plugin.py` | `tavily` | Tavily |
| `firecrawl_plugin.py` | `firecrawl` | Firecrawl |
| `parallel_plugin.py` | `parallel` | Parallel |
| `searxng_plugin.py` | `searxng` | 一个 SearXNG 实例 |

## 模型体验

### 工具 schema

#### 模型看到什么

每个插件的 `tool_schemas()`。[`system_02_tools.md`](../../../prompt/prompt_card/system/system_02_tools.md) 让模型用 `query` 和可选的 `limit` 调用 `tools.ddgs`，并在 `success` 为假时解释 `error`。

#### Token 影响

每个可见提供者一份固定 schema。结果是插件格式化的提供者载荷，包括标题和 URL。

#### KV Cache 影响

该插件保持可见时，schema 的前缀稳定。搜索结果追加。不同的提供者是不同的 schema。

## 已知限制与暂缓事项

- **靠 API 的插件需要自己的凭据** — `ddgs` 使用已安装的包。其他插件在端点或密钥缺失时调用失败。
- **提示词只点名 `ddgs`** — 其他提供者在被启动时作为自己的进程可用。系统提示词不列出它们。
