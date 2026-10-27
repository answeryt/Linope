# terminal_tools

[English](README.md) | 中文

持久终端会话，以及只有在宿主注入回调时才运行的桌面窗格工具。

`load` 接受种类 `tool`。会话工具与终端后端对话。宿主没有注入发射器或关闭器时，窗格工具返回错误。

| 插件 | 职责 |
|---|---|
| `terminal_open_plugin.py` | 创建一个按所有者隔离的会话。需要 `type`。`name` 和 `cwd` 可选。 |
| `terminal_send_plugin.py` | 向一个会话发送文本。 |
| `terminal_read_session_plugin.py` | 读取保留的输出，不发送输入。 |
| `terminal_list_plugin.py` | 列出当前代理拥有的会话。 |
| `terminal_close_session_plugin.py` | 关闭一个会话，并等到它的进程树消失。 |
| `terminal_signal_plugin.py` | 向前景进程组发送一个允许的信号。 |
| `terminal_plugin.py` | 合并的终端插件，`PLUGIN_NAME` 为 `terminal`。 |
| `terminal_read_plugin.py` | 宿主注入回调时，读取应用内窗格。 |
| `terminal_preview_plugin.py` | 宿主注入发射器时，在预览窗格打开 URL 或文件。 |
| `terminal_focus_plugin.py` | 宿主注入发射器时，聚焦一个桌面窗格。 |
| `terminal_close_plugin.py` | 宿主注入关闭器时，关闭一个后台进程标签。 |

沙箱或持久终端资源是 [`kernel/resource`](../../../../kernel/resource/README.cn.md) 里的 `sandbox` 种类。这些插件自己不打开那份租约。`capability_profile` 打开。

## 模型体验

### 工具 schema

#### 模型看到什么

每个插件上的 `tool_schemas()`。`terminal_open` 告诉模型会话会跨工具调用存活。窗格插件告诉模型它们需要宿主回调。

#### Token 影响

每个可见工具一份固定 schema。会话读取返回插件收集到的保留输出；除非插件自己的限制这么说，否则不是终端的整个生存期。

#### KV Cache 影响

插件不变时 schema 的前缀稳定。后来的调用返回会话输出时，输出追加。

## 已知限制与暂缓事项

- **窗格工具需要注入的宿主回调** — `terminal_read`、`terminal_preview`、`terminal_focus` 和 `terminal_close` 自己到不了桌面。
- **`terminal_plugin.py` 是第二套终端面** — 它放在那些单一用途的会话插件旁边。
