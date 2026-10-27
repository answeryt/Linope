# context_compression/ — three compression packages

English | [中文](README.cn.md)

Each package is loaded by its own `load`, which calls [`load_in_directory`](../README.md) on that package's folder. Functions in one package do not import another package. Token counting is injected by the caller. This directory does not discover a single pipeline.

| Directory | Role |
|---|---|
| [`semantic_compression/`](semantic_compression/README.md) | Deterministic rewrites of tool results, arguments, and media |
| [`summary_compression/`](summary_compression/README.md) | Summary budget, prompt, model call, and transcript assembly |
| [`sliding_window/`](sliding_window/README.md) | Head protection, anchors, and a tail cut |
