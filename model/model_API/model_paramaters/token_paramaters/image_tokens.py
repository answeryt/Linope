DEFAULT_IMAGE_TOKEN_COST = 1500


def estimate_image_tokens(
    message: dict,
    cost_per_image: int = DEFAULT_IMAGE_TOKEN_COST,
) -> int:
    """统计消息中的图片内容，并按固定成本估算 Token。"""
    if not isinstance(message, dict):
        return 0

    count = 0
    content = message.get("content")
    if isinstance(content, list):
        count += sum(
            1
            for part in content
            if isinstance(part, dict)
            and part.get("type") in {"image", "image_url", "input_image"}
        )

    anthropic_blocks = message.get("_anthropic_content_blocks")
    if isinstance(anthropic_blocks, list):
        count += sum(
            1
            for part in anthropic_blocks
            if isinstance(part, dict) and part.get("type") == "image"
        )

    if isinstance(content, dict) and content.get("_multimodal"):
        inner = content.get("content")
        if isinstance(inner, list):
            count += sum(
                1
                for part in inner
                if isinstance(part, dict)
                and part.get("type") in {"image", "image_url"}
            )
    return count * cost_per_image
