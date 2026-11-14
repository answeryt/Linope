"""Read-only answers the kernel asks for by running this module.

``python -m capability.queries tail-cut`` reads one JSON object on stdin:

``{"messages": [...], "budget": <int>, "tokens": [<int>, ...]}``

and writes ``{"cut": <int>}``. ``cut`` is the first index kept when messages
are retained from the end until the token budget is spent. ``0`` means the
whole list fits.
"""

from __future__ import annotations

import json
import sys
from typing import Any


def tail_cut(messages: list[Any], budget: int, tokens: list[Any]) -> int:
    """Keep a suffix whose token weights fit in ``budget``."""

    count = len(messages)
    if count == 0 or budget <= 0:
        return 0
    weights: list[int] = []
    for index in range(count):
        raw = tokens[index] if index < len(tokens) else 0
        if isinstance(raw, bool) or not isinstance(raw, int):
            try:
                raw = int(raw)
            except (TypeError, ValueError):
                raw = 0
        weights.append(raw if isinstance(raw, int) and raw > 0 else 0)
    used = 0
    start = count
    for index in range(count - 1, -1, -1):
        weight = weights[index]
        if used + weight > budget:
            break
        used += weight
        start = index
    return start


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args != ["tail-cut"]:
        sys.stderr.write("usage: python -m capability.queries tail-cut\n")
        return 2
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.stderr.write("tail-cut expects one JSON object\n")
        return 2
    if not isinstance(payload, dict):
        sys.stderr.write("tail-cut expects one JSON object\n")
        return 2
    messages = payload.get("messages")
    budget = payload.get("budget")
    tokens = payload.get("tokens") or []
    if not isinstance(messages, list) or isinstance(budget, bool) or not isinstance(budget, int):
        sys.stderr.write("tail-cut expects messages and an integer budget\n")
        return 2
    if not isinstance(tokens, list):
        sys.stderr.write("tail-cut expects a token list\n")
        return 2
    json.dump({"cut": tail_cut(messages, budget, tokens)}, sys.stdout)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
