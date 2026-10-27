# Atomic functions for summary compression

English | [中文](README.cn.md)

The functions in this directory each do one thing and import only the standard library. `load` selects one of them through [`load_in_directory`](../../README.md). A host may also import them and wire them with `functools.partial` or a closure. Functions do not import each other, and they do not import `sliding_window`, `semantic_compression`, model code, or token code.

## Atomic functions

- `summary_budget.py`: compute a capped target budget with the estimator the host provides.
- `turn_serializer.py`: serialize a turn's list of dictionaries. Redaction, stripping thinking, and labeling images are injected from outside.
- `aggregate_input_bounder.py`: limit the length of the aggregated input with a fixed head-and-tail rule.
- `structured_prompt_builder.py`: build the first and later prompts, and write the focus, memory, date, and source notes.
- `static_fallback.py`: a local deterministic checkpoint. It does not call a model.
- `summary_text.py`: strip the summary prefix, normalize, and classify the summary.
- `handoff_helpers.py`: find handoff content, strip handoff markers, and restore handoff data.
- `real_user_provenance.py`: decide whether this is a real user, and validate when there is no user.
- `latest_task_grounding.py`: ground the summary on the latest task with a fixed rule.
- `auto_focus.py`: infer a bounded focus from the latest real user turn.
- `summary_runner.py`: inject one model call and return a structured result.
- `compressed_transcript_assembler.py`: insert in alternating order, merge onto the end, write metadata, and clear stale attached content that was injected.

There is no `host.py` or `facade.py` here. Assembly, configuration, retry, cooldown, telemetry, persistence, and failure policy belong to the application host.

## How the host assembles them

The host can import the functions it needs, then connect them with `functools.partial` or a small local closure:

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

`run_summary_generation` does not retry, does not change host state, and does not substitute a fallback result on its own. When `result["ok"] == False`, the host must choose explicitly: keep the original record, try another provider, enter cooldown, or call `build_static_fallback`. Only after that decision should the host call `assemble_compressed_transcript`.

Every record-facing interface stays `list[dict]`. Callbacks are the extension boundary. They connect this project's own judgment, redaction, token estimates, model adapters, reply extraction, and clearing of stale `api_content`.

## Known Limitations and Deferred Work

- **`run_summary_generation` does not retry or fall back** — when `result["ok"]` is false, the host chooses the next step, including `build_static_fallback`.
- **No facade** — `load_in_directory` will run only when the body's keys match exactly one function in this folder. The host still imports the pieces it wants to chain.
