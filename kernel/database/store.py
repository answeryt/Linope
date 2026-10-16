"""One JSON row in whatever database the user addressed.

This module does not import resource or process sections. The caller passes
the in-memory ledger and receives it back inside each transaction.
"""

from __future__ import annotations

import functools
import json
import threading
from typing import Any

from sqlalchemy import create_engine, select
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import NoSuchModuleError

from kernel.database.schema import ROW_ID, ensure_schema, ledger

_MISSING_DRIVER = "使用这个数据库地址需要先安装对应的驱动"


class DatabaseStore:
    """Read and write one ledger document inside a database transaction."""

    def __init__(self, locator: str, *, memory: Any, reap: bool = True) -> None:
        self.locator = locator
        self.path = None
        memory.locator = locator
        self._memory = memory
        self._lock = threading.RLock()
        self._engine = _open_engine(locator)
        try:
            self.initialize_schema()
            self._load()
            if reap:
                self._run_operation("reap_dead_processes")
        except BaseException:
            self._engine.dispose()
            raise

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)
        memory = object.__getattribute__(self, "_memory")
        attr = getattr(memory, name)
        if callable(attr):
            return functools.partial(
                object.__getattribute__(self, "_run_operation"),
                name,
            )
        return attr

    def initialize_schema(self) -> None:
        ensure_schema(self._engine)

    def migrate(self) -> None:
        ensure_schema(self._engine)

    def check(self) -> dict[str, Any]:
        return {
            "locator": self.locator,
            "backend": "database",
            "ready": True,
            "persistent": True,
        }

    def close(self) -> None:
        self._engine.dispose()

    def _load(self) -> None:
        with self._engine.begin() as connection:
            payload = _read_row(connection)
            if payload is None:
                _write_row(connection, self._memory.export_state())
            else:
                self._memory.import_state(payload)

    def _run_operation(self, name: str, *args: Any, **kwargs: Any) -> Any:
        with self._lock:
            with self._engine.begin() as connection:
                payload = _read_row(connection)
                if payload is None:
                    _write_row(connection, self._memory.export_state())
                else:
                    self._memory.import_state(payload)
                result = getattr(self._memory, name)(*args, **kwargs)
                _write_row(connection, self._memory.export_state())
                return result


def _open_engine(locator: str) -> Engine:
    try:
        engine = create_engine(locator)
    except NoSuchModuleError as exc:
        raise RuntimeError(_MISSING_DRIVER) from exc
    try:
        connection = engine.connect()
    except (ImportError, ModuleNotFoundError) as exc:
        engine.dispose()
        raise RuntimeError(_MISSING_DRIVER) from exc
    except BaseException:
        engine.dispose()
        raise
    connection.close()
    return engine


def _read_row(connection: Connection) -> dict[str, Any] | None:
    statement = select(ledger.c.state_json).where(ledger.c.id == ROW_ID)
    if connection.dialect.name != "sqlite" and connection.dialect.supports_for_update:
        statement = statement.with_for_update()
    row = connection.execute(statement).first()
    if row is None:
        return None
    payload = json.loads(row[0])
    if not isinstance(payload, dict):
        raise RuntimeError("数据库账本不是有效 JSON 对象")
    return payload


def _write_row(connection: Connection, payload: dict[str, Any]) -> None:
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    exists = connection.execute(
        select(ledger.c.id).where(ledger.c.id == ROW_ID)
    ).first()
    if exists is None:
        connection.execute(ledger.insert().values(id=ROW_ID, state_json=text))
        return
    connection.execute(
        ledger.update().where(ledger.c.id == ROW_ID).values(state_json=text)
    )
