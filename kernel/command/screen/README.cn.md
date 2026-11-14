# screen

[English](README.md) | 中文

`resource.py` 是 `linope resource` 命令。它在本机起一个 HTTP 服务，开发者可以用浏览器打开资源页。

页面上有哪些链接、过期链接为什么返回 `409`、HTTP 怎么处理请求，都在 [`kernel/hypermedia`](../../hypermedia/README.cn.md)。本目录只负责启动那个服务。命令返回结构化事实，由宿主决定怎么显示。

## `resource.py`

[`dispatch.py`](../dispatch.py) 把 `run` 登记成 `resource` 命令。唯一的子命令是 `serve`：

```text
linope resource serve [--host 127.0.0.1] [--port 0]
```

`run` 读第一个词。没有参数，或者第一个词不是 `serve`，就抛出 `UsageError`。终端宿主把它变成退出码 2。

`_serve` 解析 `--host` 和 `--port`，然后调用 `kernel/hypermedia/http_server.py` 里的 `serve_resources`。传入的存储路径是空字符串。空路径的意思是：设了 `LINOPE_RESOURCE_STORE` 就用它，否则用项目配置里的 `resource_store`，再否则用 `file:.linope/resources.json`。

这次调用会停在 `serve_forever`，直到进程被停掉。服务起来时发出结构化 `resource.started` 事实（`host`、`port`），并在存储文件旁边写 `http-server.json`，里面是 host、port、pid 和存储定位。进程退出时删掉这个文件。

| 标志 | 默认 | 含义 |
|---|---|---|
| `--host` | `127.0.0.1` | 绑定地址。`serve_resources` 只接受 `127.0.0.1`、`localhost` 和 `::1`。 |
| `--port` | `0` | TCP 端口。`0` 让操作系统分配一个空闲端口。不在 `0`–`65535` 里是用法错误。终端宿主以退出码 2 结束。 |

下面这些情况会抛出异常。终端宿主打印这条消息，并以退出码 2 结束：

- `--host` 不是上面三个回环名字（`ValueError`）
- 解析出来的存储是 `memory:` 存储（`ValueError`）
- `http-server.json` 里已经记着这份存储有服务在跑（`RuntimeError`）
- 套接字打不开（`OSError`）

## 宿主事件

服务启动时返回结构化 `resource.started` 事实。内核不把进程标准错误复制到窗口，命令结果以结构化值交给宿主。
