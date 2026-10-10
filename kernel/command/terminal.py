"""A session that stays open and runs Linope commands itself.

Lines are read and executed in this process. PowerShell, cmd, and bash are
not started. ``start`` leaves the capability process running. ``load`` sends
one slip to that process through the channel already selected for the ledger.
"""

from __future__ import annotations

import io
import json
import os
import re
import sys
from collections.abc import Callable
from contextlib import redirect_stderr, redirect_stdout

from kernel.command.command_blocks import (
    command_lines,
    reply_payload,
    reply_text,
    split_line,
    tool_body,
)
from kernel.command.protocol import CommandSpec
from kernel.process.profile import ProfileUnavailable
from kernel.process.process_manager.tool_dispatch import (
    tool_capability,
    tool_request,
)
from kernel.services import ServiceRequest
from capability.model.model_runtime.blocks import turn_from_payload

MAX_FOLLOW = 8
_HREF = re.compile(r"https?://\S+/resources/\S+")
_WRITER = Callable[[str], None]


class SessionExit(Exception):
    """The person typed exit. This is not a capability command."""


def resource_href(body: str) -> str | None:
    """Return a file resource address written in the text, if there is one."""
    match = _HREF.search(body)
    if match is None:
        return None
    return match.group(0).rstrip(".,)")


def slip(kind: str, body: str) -> dict[str, str]:
    """One load message. A bare address stays the body; the file text does not."""
    message = {"operation": "load", "kind": kind, "body": body}
    href = resource_href(body)
    if href:
        message["href"] = href
        if kind == "prompt" and body.strip() == href:
            message["body"] = href
    return message


class Session:
    """Commands typed here, and command lines found in later output."""

    def __init__(self, writer: _WRITER | None = None) -> None:
        self.follow_limit = MAX_FOLLOW
        self._writer = writer or _print
        self._living: dict[tuple[str, str], list[tuple]] = {}
        self._order: list = []
        self._last_model: tuple[str, str] | None = None
        self._runners: dict | None = None
        self.closed = False

    def turn(self, line: str) -> None:
        """Run one line, then any command lines that show up in the output."""
        queue: list[tuple[str, bool]] = [(line, False)]
        steps = 0
        while queue:
            current, from_output = queue.pop(0)
            if from_output and steps >= self.follow_limit:
                self._show_stopped([current, *[item for item, _flag in queue]])
                return
            if from_output:
                steps += 1
            try:
                output = self.execute(current)
            except SessionExit:
                self.closed = True
                return
            self._emit(output)
            for found in command_lines(output, self._names()):
                queue.append((found, True))
            if not from_output or self._last_model is None:
                continue
            if self._is_prompt_to_last(current):
                continue
            if steps >= self.follow_limit:
                self._show_stopped(
                    ["把结果交回刚才的模型", *[item for item, _flag in queue]]
                )
                return
            steps += 1
            reply = self._safe_prompt_last(output)
            self._emit(reply)
            for found in command_lines(reply, self._names()):
                queue.append((found, True))

    def execute(self, line: str) -> str:
        """Run one command in this process."""
        stripped = line.strip()
        if not stripped:
            return ""
        if stripped == "exit":
            raise SessionExit()
        try:
            argv = split_line(stripped)
        except ValueError as exc:
            return str(exc)
        if not argv:
            return ""
        name = argv[0]
        if name == "exit":
            raise SessionExit()
        if name == "terminal":
            return "已经在终端里"
        if name == "start":
            return self._start(argv[1:])
        if name == "service" and argv[1:2] == ["start"]:
            return self._service_start(argv[2:])
        if name == "load":
            return self._load(argv[1:])
        runner = self._names_table().get(name)
        if runner is None:
            from kernel.command.parser import USAGE

            return USAGE
        return _capture(runner, argv[1:])

    def close(self) -> None:
        """Close the services this session kept. Each closes its own ledger."""
        for service in self._order:
            try:
                service.close()
            except Exception:
                pass
        self._order.clear()
        self._living.clear()

    def open_started(self, options: tuple) -> list:
        """Open one capability as a service and leave it running. Tests replace this."""
        from kernel.services import ServiceSpec

        spec = ServiceSpec(
            kind="capability",
            members=(options[0],),
            changes=options[1],
            replica_count=options[4],
        )
        return self.open_spec(spec, options)

    def open_spec(self, spec, options: tuple) -> list:
        """Open one service from a spec and the start flags. Tests replace this."""
        from kernel.command.start import launch_options
        from kernel.services import open_service

        return [open_service(spec, launch_options(options))]

    def _start(self, argv: list[str]) -> str:
        from kernel.command.start import _parse_start_options

        try:
            options = _parse_start_options(argv)
        except SystemExit as exc:
            return _exit_text(exc)
        try:
            services = self.open_started(options)
        except (ProfileUnavailable, ValueError, KeyError, RuntimeError, OSError) as exc:
            return str(exc)
        return self._opened(options, services)

    def _service_start(self, argv: list[str]) -> str:
        from kernel.command.service import parse_service_start

        try:
            spec, options = parse_service_start(argv)
        except SystemExit as exc:
            return _exit_text(exc)
        except ValueError as exc:
            return str(exc)
        try:
            services = self.open_spec(spec, options)
        except (ProfileUnavailable, ValueError, KeyError, RuntimeError, OSError) as exc:
            return str(exc)
        return self._opened(options, services)

    def _opened(self, options: tuple, services: list) -> str:
        from kernel.command.start import member_lines

        store_path = options[3]
        self._remember(store_path, options[0], services)
        lines: list[str] = []
        for service in services:
            lines.extend(member_lines(service))
        if options[2]:
            for service in services:
                for role in dict.fromkeys(m.role for m in service.members()):
                    ticket = service.submit(ServiceRequest(operation="ping", role=role))
                    lines.append(str(service.wait(ticket)))
        return "\n".join(lines)

    def _load(self, argv: list[str]) -> str:
        from kernel.command.load import parse_load

        try:
            (
                capability,
                profile_changes,
                kind,
                body,
                store_path,
                env_file,
                env_keys,
            ) = parse_load(argv)
        except SystemExit as exc:
            return _exit_text(exc)
        found = self._first_alive(store_path, capability)
        if found is None:
            try:
                found = self._open_for_load(
                    capability,
                    profile_changes,
                    store_path,
                    env_file,
                    env_keys,
                )
            except (ProfileUnavailable, ValueError, KeyError, RuntimeError, OSError, SystemExit) as exc:
                if isinstance(exc, SystemExit):
                    return _exit_text(exc)
                return str(exc)
        if found is None:
            return "没有拉起能力进程"
        if kind == "tool":
            message = {
                "operation": "load",
                "kind": "tool",
                "body": tool_body(body),
            }
        else:
            message = slip(kind, body)
        reply = _send(found, message)
        if kind == "prompt":
            self._last_model = (store_path, capability)
            turn = turn_from_payload(reply_payload(reply))
            if turn is not None and turn.tool_calls():
                tool_reply = self._execute_tool_call(
                    turn.tool_calls()[0],
                    store_path,
                    env_file,
                    env_keys,
                )
                return self._prompt_last(reply_text(tool_reply))
        return reply_text(reply)

    def _execute_tool_call(
        self,
        call,
        store_path: str,
        env_file: str,
        env_keys: tuple[str, ...],
    ):
        arguments = call.arguments
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except json.JSONDecodeError:
                return {
                    "event": "error",
                    "error": f"工具参数不是有效 JSON: {arguments}",
                }
        capability = tool_capability(call.name)
        found = self._first_alive(store_path, capability)
        if found is None:
            found = self._open_for_load(
                capability,
                (),
                store_path,
                env_file,
                env_keys,
            )
        if found is None:
            return {"event": "error", "error": f"没有拉起工具进程: {capability}"}
        return _send(found, tool_request(call.name, arguments))

    def _open_for_load(
        self,
        capability: str,
        profile_changes: tuple,
        store_path: str,
        env_file: str,
        env_keys: tuple[str, ...],
    ):
        from kernel.command.start import _parse_start_options

        argv = [capability, "--resource-store", store_path]
        if env_file:
            argv.extend(["--env-file", env_file])
        for key in env_keys:
            argv.extend(["--env", key])
        for topic, value in profile_changes:
            argv.extend([topic, "change", "-", value])
        services = self.open_started(_parse_start_options(argv))
        self._remember(store_path, capability, services)
        return self._first_alive(store_path, capability)

    def _prompt_last(self, text: str) -> str:
        if self._last_model is None:
            return ""
        store_path, capability = self._last_model
        found = self._first_alive(store_path, capability)
        if found is None:
            return "刚才的模型已经不在"
        return reply_text(_send(found, slip("prompt", text)))

    def _safe_prompt_last(self, text: str) -> str:
        try:
            return self._prompt_last(text)
        except Exception as exc:
            return str(exc)

    def _is_prompt_to_last(self, line: str) -> bool:
        if self._last_model is None:
            return False
        try:
            argv = split_line(line)
        except ValueError:
            return False
        if not argv or argv[0] != "load":
            return False
        from kernel.command.load import parse_load

        try:
            capability, _changes, kind, _body, store_path, _env_file, _keys = parse_load(
                argv[1:]
            )
        except SystemExit:
            return False
        return kind == "prompt" and (store_path, capability) == self._last_model

    def _remember(self, store_path: str, head: str, services: list) -> None:
        """File each service under every member capability, with the member's role."""
        for service in services:
            roles_seen = False
            for role, capability in dict.fromkeys(
                (member.role, member.capability) for member in service.members()
            ):
                roles_seen = True
                self._living.setdefault((store_path, capability), []).append((service, role))
            if not roles_seen:
                self._living.setdefault((store_path, head), []).append((service, ""))
        self._order.extend(services)

    def _first_alive(self, store_path: str, capability: str):
        """The first kept service with a living member of this capability, and the role."""
        for service, role in self._living.get((store_path, capability), ()):
            for member in service.members():
                if member.alive and (not role or member.role == role):
                    return service, role
        return None

    def _names(self) -> frozenset[str]:
        return frozenset(name for name in self._names_table() if name != "terminal")

    def _names_table(self) -> dict:
        if self._runners is None:
            from kernel.command.dispatch import command_table

            self._runners = command_table()
        return self._runners

    def _emit(self, text: str) -> None:
        if text is None:
            return
        if not isinstance(text, str):
            text = str(text)
        if text == "":
            return
        if not text.endswith("\n"):
            text += "\n"
        self._writer(text)

    def _show_stopped(self, lines: list[str]) -> None:
        self._emit("还有没跑的命令:")
        for line in lines:
            if line:
                self._emit(line)


def _send(found: tuple, message: dict) -> dict:
    """Send one mailbox message to the member role a service was filed under."""
    service, role = found
    ticket = service.submit(ServiceRequest.from_message(message, role=role))
    return service.wait(ticket, timeout=180)


def _capture(runner: Callable[[list[str]], int], argv: list[str]) -> str:
    stdout = io.StringIO()
    stderr = io.StringIO()
    try:
        with redirect_stdout(stdout), redirect_stderr(stderr):
            runner(argv)
    except SystemExit as exc:
        return _exit_text(exc)
    text = stdout.getvalue()
    err = stderr.getvalue()
    if err:
        if text and not text.endswith("\n"):
            text += "\n"
        text += err
    return text.rstrip("\n")


def _exit_text(exc: SystemExit) -> str:
    from kernel.command.parser import USAGE

    if isinstance(exc.code, str) and exc.code:
        return exc.code
    return USAGE


def _print(text: str) -> None:
    print(text, end="")


def _person_is_typing() -> bool:
    """True when a person is at this keyboard, not a test or a pipe."""
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return False
    try:
        return bool(sys.stdin.isatty())
    except Exception:
        return False


def _show_window_name(name: str) -> None:
    """Tell the terminal window to display this name."""
    if not _person_is_typing():
        return
    label = "".join(ch for ch in name if ch >= " " and ch != "\x7f")
    if not label:
        return
    stream = sys.stdout
    try:
        if stream.isatty():
            stream.write(f"\033]0;{label}\007")
            stream.flush()
    except Exception:
        pass
    if os.name != "nt":
        return
    try:
        import ctypes

        ctypes.windll.kernel32.SetConsoleTitleW(label)
    except Exception:
        pass


def _window_name() -> str:
    """Name the window is using right now."""
    if os.name != "nt" or not _person_is_typing():
        return ""
    try:
        import ctypes

        buf = ctypes.create_unicode_buffer(1024)
        if not ctypes.windll.kernel32.GetConsoleTitleW(buf, len(buf)):
            return ""
        return buf.value
    except Exception:
        return ""


_NO_ENV = "当前没有可用的环境文件。需要的话在终端里执行 env init 或 env init capability/.env"


def offer_env_files(
    root: str,
    reader: Callable[[str], str],
    writer: _WRITER,
) -> str | None:
    """Scan ``root`` and record the file the person accepts. Values are not shown."""
    from kernel.environment.shell import find_env_files
    from kernel.resource.store.locator import set_default_env_file

    files = find_env_files(root)
    if not files:
        writer(_NO_ENV + "\n")
        return None
    for index, (path, keys) in enumerate(files, start=1):
        names = ", ".join(keys) if keys else "无"
        writer(f"{index}. {path}\n   键名: {names}\n")
    if len(files) == 1:
        writer("用这一份吗？y 用，n 不用。\n")
        answer = reader("").strip().lower()
        chosen = files[0][0] if answer == "y" else ""
    else:
        writer("用哪一份？输入序号，或 n 不用。\n")
        answer = reader("").strip().lower()
        chosen = ""
        if answer.isdigit():
            index = int(answer)
            if 1 <= index <= len(files):
                chosen = files[index - 1][0]
    if not chosen:
        writer(_NO_ENV + "\n")
        return None
    recorded = set_default_env_file(chosen)
    writer(f"已记下 {recorded}\n")
    return recorded


def run(argv: list[str]) -> int:
    if argv:
        from kernel.command.parser import USAGE

        print(USAGE)
        return 1
    previous = os.environ.pop("LINOPE_PREVIOUS_TITLE", "")
    if not previous:
        previous = _window_name()
    _show_window_name("linope")
    from kernel.process.process_creat.instances import repo_root

    offer_env_files(str(repo_root()), input, _print)
    session = Session()
    try:
        while not session.closed:
            try:
                _show_window_name("linope")
                line = input("linope> ")
            except EOFError:
                break
            if line.strip() == "exit":
                break
            session.turn(line)
    except KeyboardInterrupt:
        pass
    finally:
        if previous:
            _show_window_name(previous)
        session.close()
    return 0


SPEC = CommandSpec(name="terminal", run=run)
