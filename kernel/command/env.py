"""Create or remember the secret file a developer keeps outside the tree."""

from __future__ import annotations

import sys
from pathlib import Path

from kernel.command.convention import UsageError, guard, parse
from kernel.resource.store.locator import set_default_env_file

USAGE = "用法: linope env init [路径] | linope env use <路径>"


@guard(USAGE)
def run(argv: list[str]) -> int:
    invocation = parse(argv, flags={}, usage=USAGE)
    if not invocation.position or invocation.position[0] not in {"init", "use"}:
        raise UsageError(USAGE)
    action = invocation.position[0]
    extra = invocation.position[1:]
    if action == "init":
        if len(extra) > 1:
            raise UsageError("用法: linope env init [路径]")
        path = Path.cwd() / ".env" if not extra else Path(extra[0])
        return _init(path.expanduser())
    if len(extra) != 1:
        raise UsageError("用法: linope env use <路径>")
    recorded = set_default_env_file(extra[0])
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
