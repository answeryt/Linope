"""Detached entry for one capability process."""

from __future__ import annotations

import argparse
import os
import sys

from kernel.process.process_manager.liveness import process_identity
from kernel.process.process_runtime.runtime import serve_capability
from kernel.process.ledger import open_store


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run one capability from the ledger")
    parser.add_argument("--store", required=True)
    parser.add_argument("--process-id", required=True)
    args = parser.parse_args(argv)
    os.environ["LINOPE_RESOURCE_STORE"] = args.store
    store = open_store(args.store, reap=False)
    try:
        store.update_process(
            args.process_id,
            pid=os.getpid(),
            status="starting",
            identity=process_identity(os.getpid()),
        )
        activation = store.activation_for(args.process_id)
        serve_capability(store, activation)
    except BaseException as error:
        try:
            store.update_process(args.process_id, status="failed", exit_code=1)
            store.record_failure(args.process_id, str(error))
        except Exception:
            pass
        return 1
    finally:
        store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
