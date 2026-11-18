"""Read and write one JSON object per line."""

from __future__ import annotations

import json
from typing import Any, TextIO


def read_json_line(stream: TextIO) -> Any:
    """Read one JSON value or raise EOFError when the stream closes."""

    line = stream.readline()
    if not line:
        raise EOFError
    return json.loads(line)


def write_json_line(stream: TextIO, value: Any) -> None:
    """Write one flushed JSON line."""

    stream.write(json.dumps(value, ensure_ascii=False) + "\n")
    stream.flush()
