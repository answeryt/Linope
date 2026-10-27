# model_runtime

English | [中文](README.cn.md)

Load a named provider card and turn the SDK result into text or a `ModelTurn`. The card identity and `capability_profile` live in [`model_provider`](../model_provider/README.md). The SDK call lives in [`model_interface`](../model_API/model_interface/README.md).

## Contract

`call_model.py` loads `<card_id>/<card_id>.json` under `model_provider`. `load_interface` loads `model_interface/<interface>.py`. `build_payload` drops fields whose value is `UNSET`. The API key is read from the environment name on the card.

`model_main.load_named_card` accepts kind `message`. A string body is one user message. A mapping may also carry `tools` and `tool_choice`. Any other kind raises `ValueError`. Provider plugins forward `load` and `load_async` to this function. The process declaration still comes from `CARD_CONFIG` in the plugin, via `capability_profile`, not from the JSON file.

A streamed result is walked with `parse_stream_parts` into `assembler.BlockAssembler` when the interface provides that parser. Otherwise chunks are joined with `parse_stream_chunk`. A finished response uses `parse_response_turn` when the interface has it, then `parse_response`.

`blocks.py` is the runtime turn: `TextBlock`, `ReasoningBlock`, `ToolCallBlock`, `ToolResultBlock`, and `ModelTurn`. Message blocks shared with the rest of the tree are [`model_message`](../model_message/README.md).

`usage.py` copies provider usage into `input` and `output` when those counts are present. A missing usage object returns no part. Counts the provider did not send stay absent.

## Model Experience

### Request body

#### What the model sees

The messages, and `tools` / `tool_choice` when the caller put them on the body. `UNSET` fields are omitted, so they do not override the SDK default.

#### Token effect

The request pays for the messages and any tool declarations passed in. This directory does not add a system prompt of its own. Prompt text is [`capability/prompt`](../../prompt/README.md).

#### KV Cache effect

A stable card and a stable message prefix can be reused by the provider. Changing `model`, tools, or an earlier message replaces that prefix. Streaming assembly does not add a second model request.

## Known Limitations and Deferred Work

- **One card id, one interface module** — `load_interface` loads the file named by `interface`. A card whose interface file is missing fails the load.
