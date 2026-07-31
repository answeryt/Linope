# Summary compression plugins

This directory contains stateless, atomic plugins extracted from the root
`context_compression.py` algorithm. Each Python file imports only the standard
library. Plugins do not import one another, `sliding_window`,
`semantic_compression`, model code, or token code.

## Capabilities

- `summary_budget.py`: bounded target budget using a Host-provided estimator.
- `turn_serializer.py`: list-of-dict turn serialization with injected redaction,
  thinking removal, and image labels.
- `aggregate_input_bounder.py`: deterministic head/tail aggregate input bound.
- `structured_prompt_builder.py`: first and iterative prompts, focus, memory,
  date, and provenance instructions.
- `static_fallback.py`: deterministic local checkpoint.
- `summary_text.py`: summary prefix strip, normalization, and classification.
- `handoff_helpers.py`: handoff discovery, stripping, and rehydration data.
- `real_user_provenance.py`: real-user detection and no-user validation.
- `latest_task_grounding.py`: deterministic latest-task grounding.
- `auto_focus.py`: bounded focus inference from recent real-user turns.
- `summary_runner.py`: one injected LLM call with a structured result.
- `compressed_transcript_assembler.py`: alternation-safe insertion,
  merge-into-tail, metadata, and injected stale-sidecar cleanup.

No `host.py` or `facade.py` is provided. The application Host owns composition,
configuration, retries, cooldowns, telemetry, persistence, and failure policy.

## Host composition

The Host may import the required functions and wire them with `functools.partial`
or small local closures:

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

`run_summary_generation` never retries, mutates Host state, or substitutes the
fallback. On `result["ok"] == False`, the Host must explicitly choose whether
to preserve the original transcript, retry another provider, apply cooldown,
or call `build_static_fallback`. Only after that decision should the Host call
`assemble_compressed_transcript`.

All transcript-facing APIs preserve `list[dict]`. Callbacks are the extension
boundary for project-specific predicates, redaction, token estimation, LLM
adapters, response extraction, and stale `api_content` removal.
