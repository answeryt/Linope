"""Capability runtime exceptions."""


class NoUniqueMatch(RuntimeError):
    """There was more than one match, or none, for a requested query."""


class NoMatches(NoUniqueMatch):
    """There were no matching entries for the requested name."""


class MultipleMatches(NoUniqueMatch):
    """There were multiple matches for the given name."""

