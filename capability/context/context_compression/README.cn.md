# context_compression/ — 三个压缩包

[English](README.md) | 中文

每个包由自己的 `load` 加载，它对那个包的文件夹调用 [`load_in_directory`](../README.cn.md)。一个包里的函数不导入另一个包。token 计数由调用方注入。本目录不发现一条唯一的流水线。

| 目录 | 职责 |
|---|---|
| [`semantic_compression/`](semantic_compression/README.cn.md) | 对工具结果、参数和媒体的确定性改写 |
| [`summary_compression/`](summary_compression/README.cn.md) | 摘要预算、提示词、模型调用和转录组装 |
| [`sliding_window/`](sliding_window/README.cn.md) | 头部保护、锚点，以及尾部裁剪 |
