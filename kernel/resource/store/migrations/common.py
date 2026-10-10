"""Schema version used by persistent ledger adapters."""

SCHEMA_VERSION = 2


def current_schema_version() -> int:
    return SCHEMA_VERSION
