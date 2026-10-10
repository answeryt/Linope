"""MySQL migration entry point."""

from typing import Any


def migrate(store: Any) -> None:
    """Run the MySQL adapter's idempotent schema migration."""
    store.initialize_schema()
