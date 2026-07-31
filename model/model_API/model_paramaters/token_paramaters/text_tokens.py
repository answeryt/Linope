def estimate_text_tokens_rough(text: str) -> int:
    """
    Estimate the text tokens for a given text string, using a rough approximation based on the model's metadata.
    ASCII and normal non-CJK text is approximately 4 characters per token;
    CJK, Korean, and full-width characters are approximately one character per token.
    """
    if not text:
        return 0
    text = str(text)
    if text.isascii():
        return (len(text) + 3) // 4

    dense = sum(1 for char in text if _is_cjk_token_dense_char(char))
    if not dense:
        return (len(text) + 3) // 4
    sparse = len(text) - dense
    return dense + ((sparse + 3) // 4)


def _is_cjk_token_dense_char(char: str) -> bool:
    code = ord(char)
    return (
        0x1100 <= code <= 0x11FF
        or 0x2E80 <= code <= 0x9FFF
        or 0xA960 <= code <= 0xA97F
        or 0xAC00 <= code <= 0xD7AF
        or 0xF900 <= code <= 0xFAFF
        or 0xFF00 <= code <= 0xFFEF
    )
