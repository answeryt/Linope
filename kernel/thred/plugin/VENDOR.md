# Vendor libraries

本目录保存按仓库需求修改的上游源码。Host 必须按文件路径加载它们，不得静态 import vendor 包名。

## stevedore

- 来源：OpenStack stevedore，Apache-2.0。
- `DriverManager.from_file`：从仓库内的 `*_plugin.py` 加载具名驱动。
- `stevedore.lip.Lip`：解析 `(socket, name) → 文件`，校验 `PLUGIN_NAME` 和插座合同。
- 本仓库测试位于 `vendor/stevedore/tests/`。

## pluggy

- 来源：pytest-dev pluggy，MIT。
- `PluginManager.on`：监听字符串事件并返回幂等退订函数。
- `PluginManager.emit`：按订阅时序对稳定快照广播事件。
- 本仓库测试位于 `vendor/pluggy/tests/`。

更新任一上游副本时，应保留这些本地能力，并同时更新对应 vendor 测试。
