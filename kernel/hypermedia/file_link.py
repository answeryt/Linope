"""Turn one file on disk into a representation that can be followed."""

from __future__ import annotations

from kernel.hypermedia.link import Link
from kernel.hypermedia.representation import Representation


def representation_for_file(path: str, handle: str) -> Representation:
    """One file, one ``self`` link. An empty handle cannot be followed."""
    return Representation(
        facts={"path": path},
        links=(Link(relation="self", resource_id=path, handle=handle),),
    )
