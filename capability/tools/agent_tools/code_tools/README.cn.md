# code_tools

[English](README.md) | 中文

运行一个调用其他代理工具的 Python 程序。

## 契约

`run_code_plugin.py` 的 `PLUGIN_NAME` 是 `run_code`。`load` 接受种类 `tool`。默认超时是 60000 毫秒。

程序在一组受限制的内建名字下运行：常用构造器和迭代器，加上 `Exception`、`IndexError`、`KeyError`、`RuntimeError`、`StopIteration`、`TypeError` 和 `ValueError`。工具调用通过插件得到的宿主桥出去。本插件不导入那些工具插件。

`capability_profile` 是一次启动的进程声明。命令类工具由 [`kernel/process/profiles.py`](../../../../kernel/process/profiles.py) 分成 `command`。

## 模型体验

### 工具 schema

#### 模型看到什么

`run_code` 的 `tool_schemas()`：一个 Python 程序，不是 shell 命令。shell 工具在 [`shell_tools`](../shell_tools/README.cn.md)。

#### Token 影响

工具可见时是一份固定 schema。结果是程序返回的文本，受超时限制。

#### KV Cache 影响

插件不变时 schema 的前缀稳定。结果追加。

## 已知限制与暂缓事项

- **内建集合是封闭的** — 安全名单以外的名字不存在。文件和进程访问走注入的工具桥，不走程序里敞开的 `os` 模块。
