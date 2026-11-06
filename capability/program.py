"""Run one Python capability the table named.

Other packages put their own command in the table. This runner is only for a
Python plugin path.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> None:
    """Load the plugin and answer the kernel on stdin."""
    arguments = list(sys.argv[1:] if argv is None else argv)
    if len(arguments) != 1:
        raise SystemExit("usage: python -m capability.program <plugin>")
    plugin_path = _plugin_path(arguments[0])
    plugin = _load(plugin_path, f"linope_plugin_{plugin_path.stem}")
    adapter = _load(Path(__file__).resolve().parent / "process_adapter.py", "linope_process_adapter")
    from kernel.process.process_runtime.runtime import serve_stdio

    serve_stdio(modules=[plugin, adapter])


def _plugin_path(raw: str) -> Path:
    path = Path(raw)
    if path.is_file():
        return path
    rooted = Path(__file__).resolve().parent.parent / raw
    if rooted.is_file():
        return rooted
    raise SystemExit(f"Cannot find capability plugin: {raw}")


def _load(path: Path, name: str) -> object:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"Cannot load capability plugin: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(name, None)
        raise
    return module


if __name__ == "__main__":
    main()
