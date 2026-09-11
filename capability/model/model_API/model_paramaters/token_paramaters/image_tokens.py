from kernel.compose.capability.capability import Capability


class ImageTokensCapability(Capability):
    name = "model.tokens.image"
    version = "1.0"
    kind = "model.token"
    provides = ("model.tokens.image",)


PLUGIN_NAME = "model.tokens.image"
PLUGIN_VERSION = "1.0"


DEFAULT_IMAGE_TOKEN_COST = 1500


def estimate_image_tokens(
    message: dict,
    cost_per_image: int = DEFAULT_IMAGE_TOKEN_COST,
) -> int:
    """Count image content in a message and estimate tokens based on a fixed cost."""
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
