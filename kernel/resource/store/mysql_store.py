"""MySQL ledger adapter with optional driver support."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

from kernel.resource.store.database_store import DatabaseStore


class MySQLResourceStore(DatabaseStore):
    driver_name = "mysql"

    def __init__(self, locator: str, *, memory: Any, reap: bool = True) -> None:
        connect = _connector(locator)
        super().__init__(locator, connect, memory=memory, reap=reap)


def _connector(locator: str):
    parsed = urlsplit(locator)
    if not parsed.hostname:
        raise ValueError("MySQL 连接串必须包含主机名")
    settings = {
        "host": parsed.hostname,
        "port": parsed.port or 3306,
        "user": parsed.username or "",
        "password": parsed.password or "",
        "database": parsed.path.lstrip("/") or None,
    }
    try:
        import pymysql
    except ImportError:
        try:
            import mysql.connector
        except ImportError as exc:
            raise RuntimeError(
                "使用 MySQL 存储需要先安装：pip install pymysql"
            ) from exc
        return lambda: mysql.connector.connect(**settings)
    return lambda: pymysql.connect(
        **settings,
        autocommit=False,
        charset="utf8mb4",
    )
