# file_tools

[English](README.md) | 中文

一个能力进程的文件工具。`load` 接受种类 `tool` 和一个映射。路径由插件调用的文件系统后端解析。房间的写入模式在 [`kernel/environment`](../../../../kernel/environment/README.cn.md)。

| 插件 | Schema 名 | 职责 |
|---|---|---|
| `read_plugin.py` | `read` | 带行号的 UTF-8 文本。`offset` 默认 1。`limit` 默认 2000。 |
| `write_plugin.py` | `write` | 创建或整文件替换一份 UTF-8 文件。需要 `file_path` 和 `content`。 |
| `edit_plugin.py` | `edit` | 把字面的 `old_string` 换成 `new_string`。没有 `replace_all` 时，旧文本必须恰好出现一次。 |
| `str_replace_editor_plugin.py` | `str_replace_editor` | 查看、创建、唯一字面替换和按行插入。 |
| `glob_plugin.py` | `glob` | 路径匹配某个 glob 的文件。 |
| `grep_plugin.py` | `grep` | 用正则表达式匹配的文件内容。 |
| `read_image_plugin.py` | `read_image` | 给模型的 PNG、JPEG、WebP 或 GIF 元数据。 |
| `file_plugin.py` | `read_file`、`write_file`、`patch`、`search_files` | 合并模块。`PLUGIN_NAME` 是 `file_ops`。 |

## 模型体验

### 工具 schema

#### 模型看到什么

每个插件上的 `tool_schemas()`。点名 `tools.read`、`tools.write`、`tools.edit`、`tools.glob` 和 `tools.grep` 的路由文本在 [`system_02_tools.md`](../../../prompt/prompt_card/system/system_02_tools.md)。

#### Token 影响

每个可见工具一份固定 schema，加上返回的文本。`read` 把一次调用限制在 `limit` 行，默认 2000。

#### KV Cache 影响

插件及其可见性不变时，schema 的前缀稳定。工具结果追加在该前缀之后。

## 已知限制与暂缓事项

- **`read` 是 UTF-8 文本** — 二进制文件不在这个插件里。图片走 `read_image`。
- **`file_ops` 是第二套文件面** — `file_plugin.py` 是与上面那些单一用途文件分开的插件。
