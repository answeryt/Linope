# model_message

English | [中文](README.cn.md)

In-process message content blocks. These are type definitions, not replaceable plugins. Provider SDK fields are [`model_interface`](../model_API/model_interface/README.md). The streamed turn assembler is [`model_runtime`](../model_runtime/README.md).

## Contract

Every dataclass is in [`blocks.py`](blocks.py): `TextBlock`, `ThinkingBlock`, `HintBlock`, `DataBlock`, `ToolCallBlock`, `ToolResultBlock`, and their source and state types.

## Model Experience

Indirectly, through the runtime assembler and the interface parsers. This directory does not add system-prompt text.

## Known Limitations and Deferred Work

- **Two block modules** — this file's `ThinkingBlock` is not `model_runtime.blocks.ReasoningBlock`. Each interface maps the blocks it parses.
