def estimate_message_tokens_rough(
    message: dict,
    text_estimator,
) -> int:
    """估算单条消息的文本 Token，不计图片固定成本。

    text_estimator 由调用侧传入，因此本插件不导入或绑定具体文本估算插件。
    Base64 图片会替换为短占位符，避免将图片字节当作文本 Token。
    """
    if not isinstance(message, dict):
        return text_estimator(str(message))

    shadow = {}
    for key, value in message.items():
        if key == "_anthropic_content_blocks":
            continue
        if key != "content":
            shadow[key] = value
            continue
        if isinstance(value, list):
            cleaned = []
            for part in value:
                if (
                    isinstance(part, dict)
                    and part.get("type") in {"image", "image_url", "input_image"}
                ):
                    cleaned.append(
                        {"type": part.get("type"), "image": "[stripped]"}
                    )
                else:
                    cleaned.append(part)
            shadow[key] = cleaned
        elif isinstance(value, dict) and value.get("_multimodal"):
            shadow[key] = value.get("text_summary", "")
        else:
            shadow[key] = value
    return text_estimator(str(shadow))


def estimate_messages_tokens_rough(
    messages: list[dict],
    text_estimator,
    image_estimator,
) -> int:
    """估算消息列表 Token；具体文本和图片算法由调用侧注入。"""
    total = 0
    for message in messages or []:
        total += estimate_message_tokens_rough(message, text_estimator)
        total += image_estimator(message)
    return total
