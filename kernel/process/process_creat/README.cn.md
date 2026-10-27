# process_creat

[English](README.md) | 中文

本目录找到要启动的能力，并把它打包成一份激活。打开资源记录的是 [`reconcile.py`](../reconcile.py)。本目录不决定是否允许共享，也不停止或回收。

## 契约

`instances.py` 把一个能力名，例如 `model.openai_chat_model`，解析成一份 `CapabilityDefinition`：插件路径、入口 `load`，以及画像写明的资源需求。一个能力只有一个入口。本目录不猜测缺失的需求。

`activation.py` 把该定义、资源授予、pid、房间、宿主策略、线程策略和设置打包成一份 `ProcessActivation`。pid 必须是正的操作系统进程号。授予与需求不符时，启动在这里被拒绝。

## 已知限制与暂缓事项

- **查找是一个名字对应一个插件入口** — 激活上没有第二个入口选择器。
