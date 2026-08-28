# token_paramaters

独立的 Token 粗略估算插件，算法来自根目录 `model_metadata.py`。

- `text_tokens.py`：ASCII 约 4 字符/Token，CJK 约 1 字符/Token
- `image_tokens.py`：图片固定按约 1500 Token/张计算
- `message_tokens.py`：清理图片载荷后估算消息文本
- `tool_tokens.py`：按工具名称、描述和参数 Schema 估算

本目录不提供完整请求聚合器。`message_tokens.py` 通过函数参数接收文本和图片
估算器，避免插件之间产生项目内 import。
