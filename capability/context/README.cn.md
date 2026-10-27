# context/ — 进程可以加载的压缩函数

[English](README.md) | 中文

`load_in_directory` 在一个文件夹里选出签名恰好接受正文字段、且不多接受字段的那一个公开函数。零个匹配或多于一个匹配抛出 `ValueError`。`capability_profile` 和 `load` 不是候选。字符串正文变成一条用户消息。

每个压缩包声明一份 `memory` 资源，其 `scope` 是能力 id。`--change` 的值不会应用到该声明上。

| 目录 | 职责 |
|---|---|
| [`context_compression/`](context_compression/README.cn.md) | 语义、摘要和滑动窗口函数 |
