# 语义压缩的原子函数

[English](README.md) | 中文

对 `list[dict]` 消息的小型确定性函数。`load` 通过 [`load_in_directory`](../../README.cn.md) 选出其中一个。宿主也可以导入这些函数并传入回调。没有函数导入本目录里的另一个模块、`sliding_window` 或 `summary_compression`。

## 契约

- 消息变换接受并返回 `list[dict]`。
- 没有函数导入另一个项目模块，或本目录里的另一个函数。
- 没有函数导入 `sliding_window` 或 `summary_compression`。
- 这里不实现 token 计数。宿主注入 `estimate_messages(list[dict]) -> int`。
- 摘要、标记、选择规则和策略决定可以注入。
- 空操作通常返回原来的列表对象，让宿主能用身份判断是否提交了改写。
- 函数只浅复制被改写的消息或调用，不修改输入。

## 原子函数

- `tool_result_dedup.py`：保留相同字符串工具结果的最新完整副本，并把更早的副本换成回指。
- `tool_result_summary.py`：常见工具的安全一行摘要，加上永不抛出的回退；也暴露由回调驱动的结果替换。
- `json_args_truncation.py`：解析 JSON 之后递归截断字符串叶子，保留合法 JSON，畸形参数保持不变。
- `old_tool_result_demotion.py`：用注入的摘要、图片和保护回调，降级宿主选出的旧结果。
- `protected_tail_pressure.py`：降级受保护尾部的结果，直到注入的估计器报告尾部低于其软上限。
- `proactive_prune_gate.py`：在提交会打破提示缓存的主动修剪之前，应用触发、资格和测得回收量这些门。
- `tool_pair_sanitizer.py`：去掉孤儿工具结果，并剥掉没有匹配结果的工具调用。
- `media_stripping.py`：替换图片部分，并剥掉比最新一条带图片的用户消息更早的图片。
- `skill_view_guard.py`：识别 `skill_view` 调用，计算受保护的技能名，创建降级保护回调，并收集幽灵标记。
- `deterministic_pipeline.py`：可选的、只跑回调的多遍运行器。它不导入插件，也不包含策略。

## 宿主组合

宿主拥有配置，并导入它想要的函数。它为边界和策略创建闭包，然后按这个顺序传给只跑回调的流水线：

1. 去重工具结果。
2. 计算受保护尾部的边界。
3. 从原始或当前消息建立 `skill_view` 保护。
4. 降级边界以外的旧工具结果。
5. 截断旧的 JSON 工具参数。
6. 用宿主估计器做受保护尾部的压力降级。
7. 清理工具调用和结果对。
8. 剥掉历史媒体。
9. 在语义摘要之前收集幽灵技能标记，并把缺失的标记注入宿主产生的摘要。

主动路径应把第 1、4、5 步作为候选放进 `commit_proactive_prune`。那个插件估计实际的前后列表，除非达到回收阈值，否则返回原来的对象。

宿主接线示例（仅作说明）：

```python
passes = [
    deduplicate_tool_results,
    lambda rows: demote_old_tool_results(
        rows,
        should_demote=lambda index, _row: index < protected_start,
        summary_callback=default_tool_result_summary,
        protect_callback=skill_protection,
    ),
    lambda rows: truncate_tool_call_arguments(
        rows,
        should_truncate=lambda index, _row: index < protected_start,
    ),
    lambda rows: demote_protected_tail_under_pressure(
        rows,
        protected_start=protected_start,
        soft_token_limit=tail_limit,
        estimate_messages=host_estimator,
        summary_callback=default_tool_result_summary,
    ),
    sanitize_tool_pairs,
    strip_historical_media,
]
compressed = run_deterministic_pipeline(messages, passes=passes)
```

这个示例里的名字故意不通过 `__init__`、门面或宿主模块重新导出。宿主直接导入每个原子插件。

## 已知限制与暂缓事项

- **没有登记流水线** — `deterministic_pipeline.py` 运行给它的回调，不导入兄弟。本包上的 `load` 仍按参数名选出一个函数。
- **token 计数是注入的** — 宿主传入时，函数调用 `estimate_messages`。本目录自己不计数。
