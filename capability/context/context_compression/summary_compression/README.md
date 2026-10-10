# 摘要压缩的原子函数

这个目录里的函数从根目录的 `context_compression.py` 算法中拆出，各自无状态、只做一件事。每个 Python 文件只导入标准库。这些文件还不是会被自动发现并组装的能力插件；由宿主显式导入并接好。函数之间互不导入，也不导入 `sliding_window`、`semantic_compression`、模型代码或词元代码。

## 原子函数

- `summary_budget.py`：用宿主提供的估算器计算有上限的目标预算。
- `turn_serializer.py`：把轮次的字典列表序列化。脱敏、去掉思考内容、给图片加标签都由外部注入。
- `aggregate_input_bounder.py`：按确定的头尾规则限制汇总输入的长度。
- `structured_prompt_builder.py`：构造首轮和后续提示，并写上焦点、记忆、日期和出处说明。
- `static_fallback.py`：本地确定的检查点，不调用模型。
- `summary_text.py`：去掉摘要前缀、做规范化，并给摘要分类。
- `handoff_helpers.py`：发现交接内容、剥掉交接标记，以及恢复交接数据。
- `real_user_provenance.py`：判断是不是真实用户，并在没有用户时做校验。
- `latest_task_grounding.py`：按确定规则把摘要落实到最近一项任务。
- `auto_focus.py`：从最近的真实用户轮次推断有限长度的焦点。
- `summary_runner.py`：注入一次大模型调用，并返回结构化结果。
- `compressed_transcript_assembler.py`：按交替顺序安全插入、并入末尾、写入元数据，并清理注入进来的过期附属内容。

这里不提供 `host.py` 或 `facade.py`。组装、配置、重试、冷却、遥测、持久化和失败策略都由应用宿主负责。

## 宿主如何组装

宿主可以导入需要的函数，再用 `functools.partial` 或本地小闭包把它们接起来：

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

`run_summary_generation` 不会重试，不会改宿主状态，也不会自行换成兜底结果。当 `result["ok"] == False` 时，宿主必须明确选择：保留原始记录、换一个提供商再试、进入冷却，还是调用 `build_static_fallback`。只有做出这个决定之后，宿主才应调用 `assemble_compressed_transcript`。

所有面向记录的接口都保持 `list[dict]`。回调是扩展边界，用来接入本项目自己的判断、脱敏、词元估算、模型适配、回复提取，以及过期 `api_content` 的清除。
