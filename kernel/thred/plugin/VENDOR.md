# Vendor libraries

本目录保存按仓库需求修改、已经内化到运行时目录的上游源码。项目不再依赖缺失的 `vendor/` 包树；Host 直接使用本目录中的 `manager/` 和 `signals/`。

## stevedore

- 来源：OpenStack stevedore，Apache-2.0。
- `DriverManager.from_file`：从仓库内的 `*_plugin.py` 加载具名驱动。
- `manager/`：保留扩展发现和驱动管理能力。
- `host/socket_loader.py`、`module_loader.py`、`recipe_loader.py`：分别实现工具选择、叶模块加载和 Path Recipe 加载，经共享的 `host/file_loader.py` 委托 `DriverManager.from_file`。

## pluggy

- 来源：pytest-dev pluggy，MIT。
- `PluginManager.on`：监听字符串事件并返回幂等退订函数。
- `PluginManager.emit`：按订阅时序对稳定快照广播事件。
- `signals/`：保留 hook、wrapper、追踪和本地字符串事件能力。

更新任一上游来源时，应保留这些本地能力，并运行 `tests/kernel/lip_board_test.py` 与 `tests/kernel/thred_composer_test.py`。
