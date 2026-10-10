"""JSON-state database adapters for PostgreSQL and MySQL."""

from __future__ import annotations

import json
import threading
from typing import Any, Callable

from kernel.resource.store.persistent_store import StateBackedStore


class DatabaseStore(StateBackedStore):
    """Common transaction wrapper for SQL database-backed stores."""

    driver_name = "database"

    def __init__(
        self,
        locator: str,
        connect: Callable[[], Any],
        *,
        memory: Any,
        reap: bool = True,
    ) -> None:
        self.locator = locator
        self.path = None
        memory.locator = locator
        self._connection = connect()
        self._db_thread_lock = threading.RLock()
        super().__init__(memory)
        self._ensure_table()
        self._load_db_state()
        if reap:
            self._run_operation("reap_dead_processes")

    def _run_operation(self, name: str, *args: Any, **kwargs: Any) -> Any:
        with self._db_thread_lock:
            cursor = self._connection.cursor()
            try:
                cursor.execute(
                    "SELECT state_json FROM linope_state WHERE id = %s FOR UPDATE",
                    (1,),
                )
                row = cursor.fetchone()
                if row is None:
                    cursor.execute(
                        "INSERT INTO linope_state (id, state_json) VALUES (%s, %s)",
                        (
                            1,
                            json.dumps(
                                self._codec.encode(self._memory),
                                ensure_ascii=False,
                                sort_keys=True,
                            ),
                        ),
                    )
                else:
                    self._codec.decode(self._memory, _row_value(row))
                result = self._delegate(name, *args, **kwargs)
                cursor.execute(
                    "UPDATE linope_state SET state_json = %s WHERE id = %s",
                    (
                        json.dumps(
                            self._codec.encode(self._memory),
                            ensure_ascii=False,
                            sort_keys=True,
                        ),
                        1,
                    ),
                )
                self._connection.commit()
                return result
            except BaseException:
                self._connection.rollback()
                raise
            finally:
                cursor.close()

    def _ensure_table(self) -> None:
        cursor = self._connection.cursor()
        try:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS linope_state (
                    id INTEGER PRIMARY KEY,
                    state_json TEXT NOT NULL
                )
                """
            )
            self._connection.commit()
        finally:
            cursor.close()

    def _load_db_state(self) -> None:
        cursor = self._connection.cursor()
        try:
            cursor.execute("SELECT state_json FROM linope_state WHERE id = %s", (1,))
            row = cursor.fetchone()
            if row is None:
                cursor.execute(
                    "INSERT INTO linope_state (id, state_json) VALUES (%s, %s)",
                    (
                        1,
                        json.dumps(
                            self._codec.encode(self._memory),
                            ensure_ascii=False,
                            sort_keys=True,
                        ),
                    ),
                )
                self._connection.commit()
            else:
                self._codec.decode(self._memory, _row_value(row))
        finally:
            cursor.close()

    def initialize_schema(self) -> None:
        self._ensure_table()

    def migrate(self) -> None:
        self._ensure_table()

    def check(self) -> dict[str, Any]:
        return {
            "locator": self.locator,
            "backend": self.driver_name,
            "ready": True,
            "persistent": True,
        }

    def close(self) -> None:
        self._connection.close()


def _row_value(row: Any) -> dict[str, Any]:
    value = row[0] if not isinstance(row, dict) else row["state_json"]
    payload = json.loads(value)
    if not isinstance(payload, dict):
        raise RuntimeError("数据库账本不是有效 JSON 对象")
    return payload
