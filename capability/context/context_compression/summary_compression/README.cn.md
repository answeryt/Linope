# 摘要压缩的原子函数

[English](README.md) | 中文

本目录里的函数各做一件事，并且只导入标准库。`load` 通过 [`load_in_directory`](../../README.cn.md) 选出其中一个。宿主也可以导入它们，并用 `functools.partial` 或闭包接起来。函数互不导入，也不导入 `sliding_window`、`semantic_compression`、模型代码或 token 代码。

## 原子函数

- `summary_budget.py`：用宿主提供的估计器计算一个有上限的目标预算。
- `turn_serializer.py`：序列化一个回合的字典列表。涂改、去掉思考和标注图片从外部注入。
- `aggregate_input_bounder.py`：用固定的头尾规则限制聚合输入的长度。
- `structured_prompt_builder.py`：构造第一次和后来的提示词，并写上焦点、记忆、日期和来源说明。
- `static_fallback.py`：本地的确定性检查点。它不调用模型。
- `summary_text.py`：去掉摘要前缀、规范化并分类摘要。
- `handoff_helpers.py`：找到交接内容、去掉交接标记并恢复交接数据。
- `real_user_provenance.py`：判断这是不是真实用户，并在没有用户时校验。
- `latest_task_grounding.py`：用固定规则把摘要落实到最新任务上。
- `auto_focus.py`：从最新的真实用户回合推断一个有界焦点。
- `summary_runner.py`：注入一次模型调用并返回结构化结果。
- `compressed_transcript_assembler.py`：按交替顺序插入，合并到末尾，写元数据，并清掉注入进来的过期附加内容。

这里没有 `host.py` 或 `facade.py`。组装、配置、重试、冷却、遥测、持久化和失败策略属于应用宿主。

## 宿主如何组装它们

宿主可以导入它需要的函数，然后用 `functools.partial` 或一个小的本地闭包接起来：

```python
from functools import partial

from context.context_compression.summary_compression.summary_budget import (
    compute_summary_budget,
)
from context.context_compression.summary_compression.turn_serializer import (
    serialize_turns,
)
from context.context_compression.summary_compression.aggregate_input_bounder import (
    bound_summary_input,
)
from context.context_compression.summary_compression.structured_prompt_builder import (
    build_structured_prompt,
)
from context.context_compression.summary_compression.summary_runner import (
    run_summary_generation,
)
from context.context_compression.summary_compression.summary_text import (
    content_to_text,
    normalize_summary,
)

budget = compute_summary_budget(
    turns,
    estimator=host_estimate_messages,
    maximum=host_max_summary_tokens,
)
serialized = serialize_turns(
    turns,
    redactor=host_redact,
    think_stripper=host_strip_thinking,
    image_labeler=host_image_label,
)
prompt = build_structured_prompt(
    bound_summary_input(serialized),
    budget,
    previous_summary=previous_summary,
    focus_topic=explicit_focus or auto_focus,
    memory_context=memory_context,
    has_user_turn=has_user_turn,
)
result = run_summary_generation(
    prompt,
    llm=host_summary_llm,
    response_text=host_response_text,
    think_stripper=host_strip_thinking,
    redactor=host_redact,
    normalize_summary=normalize_summary,
    ground_summary=host_ground_summary,
    validate_summary=host_validate_provenance,
)
```

`run_summary_generation` 不重试，不改变宿主状态，也不自己替换成回退结果。当 `result["ok"] == False` 时，宿主必须明确选择：保留原始记录、换一个提供者、进入冷却，或调用 `build_static_fallback`。只有在那个决定之后，宿主才应调用 `assemble_compressed_transcript`。

每个面向记录的接口保持 `list[dict]`。回调是扩展边界。它们接上本项目自己的判断、涂改、token 估计、模型适配器、回复提取，以及清除过期的 `api_content`。

## 已知限制与暂缓事项

- **`run_summary_generation` 不重试也不回退** — `result["ok"]` 为假时，由宿主选择下一步，包括 `build_static_fallback`。
- **没有门面** — 只有正文字段恰好匹配本文件夹里一个函数时，`load_in_directory` 才会运行。宿主仍然导入它想串起来的那些片段。
