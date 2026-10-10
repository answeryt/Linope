"""Parsing helpers shared by CLI commands."""

from __future__ import annotations

from kernel.process.profile import Change
from kernel.resource.store.locator import default_store_locator

USAGE = (
    "用法: linope start 能力 [--ping] | linope load 能力 种类 内容 | "
    "linope call 能力 ping | linope layouts | linope layout 名称 | "
    "linope channels | linope channel 名称 | linope share 能力 | "
    "linope file once|lasting 路径 -- 全文 | "
    "linope ask 模型 HTTP链接 -- 问题 | "
    "linope resources serve | linope stores | linope store current|use|check|init|migrate | "
    "linope thread add|remove|show|idle 能力 | linope room [进程号] | "
    "linope env init [路径] | linope env use 路径 | linope terminal | "
    "linope services | linope service start 种类 [成员...]"
)
COMPOSITIONS = frozenset({"chain", "group", "chord"})


def env_key(raw: str) -> str:
    """Validate an environment key whose value lives in a file."""
    key = raw.strip()
    if not key or "=" in key or "\x00" in key:
        raise SystemExit("命令只写键名，值放在环境文件里")
    return key


def take_env_flags(argv: list[str]) -> tuple[list[str], str, tuple[str, ...]]:
    """Remove the shared environment flags from a command."""
    rest: list[str] = []
    env_file = ""
    keys: list[str] = []
    index = 0
    while index < len(argv):
        token = argv[index]
        if token == "--env-file":
            if index + 1 >= len(argv):
                raise SystemExit("--env-file 后面要写文件路径")
            env_file = argv[index + 1]
            index += 2
            continue
        if token.startswith("--env-file="):
            env_file = token.split("=", 1)[1]
            index += 1
            continue
        if token == "--env":
            if index + 1 >= len(argv):
                raise SystemExit("--env 后面要写键名")
            keys.append(env_key(argv[index + 1]))
            index += 2
            continue
        if token.startswith("--env=") and not token.startswith("--env-file="):
            keys.append(env_key(token.split("=", 1)[1]))
            index += 1
            continue
        rest.append(token)
        index += 1
    if keys and not env_file:
        raise SystemExit("还没指定环境文件，不能选择键")
    return rest, env_file, tuple(keys)


def resource_store_path(argv: list[str]) -> tuple[list[str], str]:
    """Remove the shared ``--resource-store`` option."""
    rest: list[str] = []
    store_path = default_store_locator()
    index = 0
    while index < len(argv):
        token = argv[index]
        if token == "--resource-store":
            if index + 1 >= len(argv):
                raise SystemExit("--resource-store 后面要写定位串")
            store_path = argv[index + 1]
            index += 2
            continue
        if token.startswith("--resource-store="):
            store_path = token.split("=", 1)[1]
            index += 1
            continue
        rest.append(token)
        index += 1
    return rest, store_path


def member_names(tokens: list[str]) -> tuple[tuple[str, ...], list[str]]:
    """Take leading capability names. A name has a dot; change clauses and counts do not."""
    members: list[str] = []
    rest = list(tokens)
    while rest and "." in rest[0] and rest[1:3] != ["change", "-"]:
        members.append(rest.pop(0))
    return tuple(members), rest


def replica_count(tokens: list[str]) -> tuple[int | None, list[str]]:
    """Take a trailing integer only after complete change clauses."""
    if not tokens or len(tokens) % 4 != 1 or not tokens[-1].isdigit():
        return None, tokens
    count = int(tokens[-1])
    if count < 1:
        raise SystemExit("份数至少为 1")
    return count, tokens[:-1]


def changes(tokens: list[str]) -> tuple[Change, ...]:
    """Parse repeated ``topic change - value`` clauses."""
    parsed: list[Change] = []
    index = 0
    while index < len(tokens):
        if index + 3 >= len(tokens):
            raise SystemExit("change 的写法是：主题 change - 值")
        topic, verb, dash, value = tokens[index : index + 4]
        if verb != "change" or dash != "-":
            raise SystemExit("change 的写法是：主题 change - 值")
        parsed.append((topic, value))
        index += 4
    return tuple(parsed)
