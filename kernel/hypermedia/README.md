# hypermedia

这里提供资源状态的只读 HATEOAS 投影和本地 HTTP 服务。资源 URI 使用不透明句柄，不暴露文件系统路径。

文件页面只提供这些关系：

- `resident`：`self`、`content`、`pin`、`swap`；
- `pinned`：`self`、`content`；
- `swapped`：`self`、`admit`。

动作只在当前菜单提供时才可执行；失效关系返回 `409`。本地服务只监听回环地址。压缩、工具菜单、观察消息、私网 HTTP、动态鉴权、CAS/ETag 和 MCP 菜单已删除。
