"""The one ledger table. Callers pass an engine; this module does not connect."""

from __future__ import annotations

from sqlalchemy import Column, Integer, MetaData, Table, Text
from sqlalchemy.engine import Engine

metadata = MetaData()

ledger = Table(
    "linope_state",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("state_json", Text, nullable=False),
)

ROW_ID = 1


def ensure_schema(engine: Engine) -> None:
    """Create the ledger table when it is missing. An existing table is left as it is."""
    metadata.create_all(engine)
