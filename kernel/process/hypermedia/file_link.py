"""Turn one file on disk into a representation that can be followed."""

from __future__ import annotations

from kernel.process.hypermedia.link import Link
from kernel.process.hypermedia.representation import Representation


def representation_for_file(path: str, handle: str) -> Representation:
    """One file, one ``self`` link. An empty handle cannot be followed."""
    return Representation(
        facts={"path": path},
        links=(Link(relation="self", resource_id=path, handle=handle),),
    )


def messages_for_followed_file(file_text: str, words: str) -> list[dict[str, str]]:
    """The file text comes first. The words typed after it come second."""
    return [
        {"role": "user", "content": file_text},
        {"role": "user", "content": words},
    ]
