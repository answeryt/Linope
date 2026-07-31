def estimate_text_tokens_rough(text: str) -> int:
    """按 model_metadata.py 的规则粗略估算文本 Token。

    ASCII 及普通非 CJK 文本约按 4 字符一个 Token 计算；
    CJK、韩文及全角字符约按一个字符一个 Token 计算。
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
