# web_search_tools

English | [中文](README.cn.md)

One plugin per search provider. `load` accepts kind `tool` and a mapping with `query`. `capability_profile` declares the process. Plugins do not import each other.

| Plugin | `PLUGIN_NAME` | Provider |
|---|---|---|
| `ddgs_plugin.py` | `ddgs` | Installed `ddgs` package. `limit` is 1–10, default 5. Returns titles, URLs, and descriptions. |
| `brave_free_plugin.py` | `brave_free` | Brave Search API |
| `exa_plugin.py` | `exa` | Exa |
| `tavily_plugin.py` | `tavily` | Tavily |
| `firecrawl_plugin.py` | `firecrawl` | Firecrawl |
| `parallel_plugin.py` | `parallel` | Parallel |
| `searxng_plugin.py` | `searxng` | A SearXNG instance |

## Model Experience

### Tool schema

#### What the model sees

Each plugin's `tool_schemas()`. [`system_02_tools.md`](../../../prompt/prompt_card/system/system_02_tools.md) tells the model to call `tools.ddgs` with `query` and optional `limit`, and to explain `error` when `success` is false.

#### Token effect

One fixed schema per visible provider. The result is the provider payload the plugin formats, including titles and URLs.

#### KV Cache effect

A schema is prefix-stable while that plugin stays visible. A search result appends. A different provider is a different schema.

## Known Limitations and Deferred Work

- **API-backed plugins need their own credentials** — `ddgs` uses the installed package. The other plugins fail the call when their endpoint or key is missing.
- **The prompt names `ddgs` only** — the other providers are available as their own processes when started. The system prompt does not list them.
