# hypermedia

这个目录定义 Linope 交给客户端的资源表示和链接关系。它与 `kernel/process`、`kernel/resource` 平级。

进程和资源都不导入这里。这里可以导入资源规则。只有本机 HTTP 服务打开进程账本。

## HATEOAS 表示

文件资源通过本机 HTTP 服务返回资源表示。客户端不自己拼接下一步地址，而是读取链接的 `rel`，再跟随 `href`：

```json
{
  "type": "file",
  "id": "opaque-id",
  "state": "resident",
  "_links": {
    "self": {
      "rel": "self",
      "href": "http://127.0.0.1:49152/resources/opaque-id",
      "method": "GET",
      "type": "application/json"
    },
    "content": {
      "rel": "content",
      "href": "http://127.0.0.1:49152/resources/opaque-id/content",
      "method": "GET",
      "type": "text/plain; charset=utf-8"
    }
  }
}
```

菜单随页状态变化，客户端只跟随当前返回的关系：

- `resident`：`self`、`content`、`pin`、`swap`
- `pinned`：`self`、`content`。固定页不能换出，所以没有 `swap`
- `swapped`：`self`、`admit`。请回 `resident` 之后，下一份表示才重新出现 `content`

`pin`、`swap`、`admit` 和 `compress` 使用 POST。关系不在当前菜单上时，服务器返回 409，页状态不变。成功后响应就是新的表示。

`compress` 只在页还占着窗口、并且已经租到 `context.sliding_window`、`context.summary_compression` 或 `context.semantic_compression` 时出现。压缩是系统工具，不把自己记成一页。普通页被换出；摘要比原文短时，另记一页更小的长期页。固定页不会被 `swap` 换出，压缩只会把它裁短。

工具按结果分类，插件仍留在 `capability/tools`：

- 只给链接，进队列不占窗口：`firecrawl`、`tavily`、`exa`、`parallel`、`brave_free`、`searxng`、`ddgs`、`grep`、`glob`，以及查找和列表。
- 跟随之后才占窗口，或直接改资源：`read`、`write`、`edit`、`bash` 等。POST 正文里写 `{"keep": true, "text": "..."}` 才把结果记成新的长期页。
- 系统压缩：上面三个 context 能力。

MCP 工具用同一套三类。没有声明的名字默认只给链接。未租到的工具不会出现在菜单上。

信箱可以搬运一份观察：`operation` 为 `observe`，`href` 是 `self`，`representation` 是入队时的副本。取出或认领不改变页状态。动手前要重新 GET `self`，关系还在才按链接上的方法和地址执行。

进程之间的请求和回复记在信箱里，不另做一种调用资源。客户端和服务端只是这次通信里的角色：发出请求的一方是客户端，接收请求的一方是服务端。同一进程可以同时处于两种角色。

文件页的表示仍由页状态决定。客户端只保存 `self`，下一步只跟随当前 `_links` 里的 `href` 和 `method`。关系不在当前菜单上时返回 409，页状态不变。

账本仍是事实来源。表示只是这次读到的投影，不保存另一套请求状态。

浏览器、RAG、LLM 和 Linope CLI 使用同一个 HTTP `href`。内部 `Link.handle` 只用于账本查询和权限判断，不作为另一套公开协议。

## 文件链接生命周期

单机开发继续用本机模式。跨机器时用私网模式，链接写成其他机器能访问的内网地址，账本改用数据库：

```text
linope resource serve --mode local --port 0
linope resource serve --mode private --host 10.0.0.10 --port 49152 --public-base-url http://10.0.0.10:49152
```

不写 `--mode` 时仍是 `local`。私网模式不接受 `localhost` 作为链接地址。

先启动资源服务：

```powershell
linope resource serve --host 127.0.0.1 --port 0 --resource-store .linope\resources.json
```

操作系统会分配空闲端口，服务将实际端口写入 `.linope/http-server.json`。一个资源账本只有一个资源服务，多个文件共享端口、使用不同资源路径。

文件命令成功后打印完整 HTTP `href`。浏览器和 RAG 客户端都可以使用这个地址；服务端通过账本解析 opaque ID，不把用户提供的路径直接拼接到文件系统。
