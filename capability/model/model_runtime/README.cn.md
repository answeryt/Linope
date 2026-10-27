# model_runtime

[English](README.md) | 中文

加载一张点名的提供者卡片，并把 SDK 结果变成文本或一个 `ModelTurn`。卡片身份和 `capability_profile` 在 [`model_provider`](../model_provider/README.cn.md)。SDK 调用在 [`model_interface`](../model_API/model_interface/README.cn.md)。

## 契约

`call_model.py` 加载 `model_provider` 下的 `<card_id>/<card_id>.json`。`load_interface` 加载 `model_interface/<interface>.py`。`build_payload` 丢掉值为 `UNSET` 的字段。API 密钥从卡片上的环境变量名读取。

`model_main.load_named_card` 接受种类 `message`。字符串正文是一条用户消息。映射还可以带 `tools` 和 `tool_choice`。其他种类抛出 `ValueError`。提供者插件把 `load` 和 `load_async` 转发到这个函数。进程声明仍来自插件里的 `CARD_CONFIG`，经由 `capability_profile`，不来自 JSON 文件。

接口提供 `parse_stream_parts` 时，流式结果被走入 `assembler.BlockAssembler`。否则用 `parse_stream_chunk` 把片段拼起来。完成的响应在接口有 `parse_response_turn` 时使用它，然后使用 `parse_response`。

`blocks.py` 是运行时回合：`TextBlock`、`ReasoningBlock`、`ToolCallBlock`、`ToolResultBlock` 和 `ModelTurn`。与树的其余部分共享的消息块在 [`model_message`](../model_message/README.cn.md)。

`usage.py` 在提供者给出这些计数时，把用量抄成 `input` 和 `output`。缺少用量对象时不返回这一部分。提供者没有发送的计数保持缺席。

## 模型体验

### 请求正文

#### 模型看到什么

消息，以及调用方放在正文上的 `tools` / `tool_choice`。`UNSET` 字段被省略，因此不会覆盖 SDK 默认值。

#### Token 影响

请求为消息和传入的工具声明付费。本目录不自己添加系统提示词。提示词文本在 [`capability/prompt`](../../prompt/README.cn.md)。

#### KV Cache 影响

稳定的卡片和稳定的消息前缀可以被提供者复用。改变 `model`、工具或更早的一条消息会替换该前缀。流式组装不会增加第二次模型请求。

## 已知限制与暂缓事项

- **一个卡片 id，一个接口模块** — `load_interface` 加载 `interface` 点名的文件。卡片的接口文件缺失时，加载失败。
