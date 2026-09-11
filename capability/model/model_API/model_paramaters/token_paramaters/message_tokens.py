from kernel.compose.capability.capability import Capability


class MessageTokensCapability(Capability):
    name = "model.tokens.message"
    version = "1.0"
    kind = "model.token"
    provides = ("model.tokens.message",)


PLUGIN_NAME = "model.tokens.message"
PLUGIN_VERSION = "1.0"


def estimate_message_tokens_rough(
    message: dict,
    text_estimator,
) -> int:
    """Estimate the text tokens for a single message, without counting the fixed cost of images.

    text_estimator is passed in by the caller, so this plugin does not import or bind any specific text estimation plugins.
    Base64 images are replaced with short placeholders to avoid counting image bytes as text tokens.
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
    """Estimate the total token count for a list of messages; specific text and image estimation algorithms are injected by the caller."""
    total = 0
    for message in messages or []:
        total += estimate_message_tokens_rough(message, text_estimator)
        total += image_estimator(message)
    return total
