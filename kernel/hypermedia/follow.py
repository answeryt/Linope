"""Select links on a page. This module does not run a model turn.

The name remains so older imports keep working. New code should call
``kernel.hypermedia.link_selector``. Model turns are scheduled by
``kernel.scheduler``.
"""

from kernel.hypermedia.link_selector import FollowResult, link_named, select_links

follow_selected = select_links

__all__ = ["FollowResult", "follow_selected", "link_named", "select_links"]
