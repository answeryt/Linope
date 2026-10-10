"""Create or remember the secret file a developer keeps outside the tree."""

from __future__ import annotations

import sys
from pathlib import Path

from kernel.command.parser import USAGE, resource_store_path
from kernel.command.protocol import CommandSpec
from kernel.resource.store.locator import set_default_env_file


def run(argv: list[str]) -> int:
    rest, _store_path = resource_store_path(argv)
    if not rest or rest[0] not in {"init", "use"}:
        raise SystemExit(USAGE)
    if rest[0] == "init":
        if len(rest) > 2:
            raise SystemExit("env init 的写法是：env init [路径]")
        path = Path.cwd() / ".env" if len(rest) == 1 else Path(rest[1])
        return _init(path.expanduser())
    if len(rest) != 2:
        raise SystemExit("env use 的写法是：env use <路径>")
    recorded = set_default_env_file(rest[1])
    print(f"已记下 {recorded}")
    return 0


def _init(path: Path) -> int:
    if path.exists() and not path.is_file():
        print("环境文件不是文件", file=sys.stderr)
        return 1
    if path.exists():
        print(f"环境文件已存在，未覆盖 {path}")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")
        print(f"已创建 {path}")
    recorded = set_default_env_file(path)
    print(f"已记下 {recorded}")
    return 0


SPEC = CommandSpec(name="env", run=run)
