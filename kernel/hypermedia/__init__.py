"""Minimal local HATEOAS resource representations."""

from kernel.hypermedia.file_link import representation_for_file
from kernel.hypermedia.follow import FollowResult, follow_selected, link_named
from kernel.hypermedia.link import Link
from kernel.hypermedia.representation import Representation
from kernel.hypermedia.representation_json import (
    content_payload,
    file_resource_payload,
    link_payload,
    links_for_state,
    representation_payload,
)
from kernel.hypermedia.uri import (
    action_uri,
    content_uri,
    parse_action_uri,
    parse_content_uri,
    parse_resource_uri,
    resource_uri,
)

__all__ = [
    "FollowResult",
    "Link",
    "Representation",
    "action_uri",
    "content_payload",
    "content_uri",
    "file_resource_payload",
    "follow_selected",
    "link_named",
    "link_payload",
    "links_for_state",
    "parse_action_uri",
    "parse_content_uri",
    "parse_resource_uri",
    "representation_for_file",
    "representation_payload",
    "resource_uri",
]
