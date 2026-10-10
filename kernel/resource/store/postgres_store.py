"""PostgreSQL ledger adapter."""

from __future__ import annotations

from typing import Any

from kernel.resource.store.database_store import DatabaseStore


class PostgreSQLResourceStore(DatabaseStore):
    driver_name = "postgresql"

    def __init__(self, locator: str, *, memory: Any, reap: bool = True) -> None:
        try:
            import psycopg2
        except ImportError as exc:
            raise RuntimeError(
                "使用 PostgreSQL 存储需要先安装：pip install psycopg2-binary"
            ) from exc
        super().__init__(
            locator,
            lambda: psycopg2.connect(locator),
            memory=memory,
            reap=reap,
        )


PostgresResourceStore = PostgreSQLResourceStore
