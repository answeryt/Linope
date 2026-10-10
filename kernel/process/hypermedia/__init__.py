"""Hypermedia representations handed to an agent."""

from kernel.process.hypermedia.file_link import (
    messages_for_followed_file,
    representation_for_file,
)
from kernel.process.hypermedia.follow import FollowResult, follow_selected, link_named
from kernel.process.hypermedia.link import Link
from kernel.process.hypermedia.observation import (
    act_if_offered,
    deliver_observation,
    fetch_representation,
    observation_body,
    offered_href,
)
from kernel.process.hypermedia.representation import Representation
from kernel.process.hypermedia.representation_json import (
    content_payload,
    file_resource_payload,
    link_payload,
    links_for_state,
    representation_payload,
)
from kernel.process.hypermedia.tool_effect import (
    ToolEffect,
    declare_tool,
    effect_for,
    forget_tool,
)
from kernel.process.hypermedia.uri import (
    action_uri,
    content_uri,
    parse_action_uri,
    parse_content_uri,
    parse_resource_uri,
    parse_tool_uri,
    resource_base_url,
    resource_uri,
    tool_uri,
)

__all__ = [
    "FollowResult",
    "Link",
    "Representation",
    "ToolEffect",
    "act_if_offered",
    "action_uri",
    "declare_tool",
    "deliver_observation",
    "effect_for",
    "fetch_representation",
    "follow_selected",
    "forget_tool",
    "link_named",
    "links_for_state",
    "messages_for_followed_file",
    "observation_body",
    "offered_href",
    "representation_for_file",
    "content_payload",
    "content_uri",
    "file_resource_payload",
    "link_payload",
    "parse_action_uri",
    "parse_content_uri",
    "parse_resource_uri",
    "parse_tool_uri",
    "resource_base_url",
    "representation_payload",
    "resource_uri",
    "tool_uri",
]
