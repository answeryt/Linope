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
from kernel.command.convention import UsageError
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


def _follow_commands(line: str, from_output: bool) -> bool:
    """Model and tool text can contain the next command. A status line cannot.

    A command the model already asked for is ``from_output``. A person typing
    ``load`` also receives model or tool text. Other commands only report
    what they did.
    """
    if from_output:
        return True
    try:
        argv = split_line(line.strip())
    except ValueError:
        return False
    return bool(argv) and argv[:2] == ["capability", "load"]


def slip(kind: str, body: str) -> dict[str, str]:
    """One load message. A bare address stays the body; the file text does not."""
    message = {"operation": "load", "kind": kind, "body": body}
    href = resource_href(body)
    if href:
        message["href"] = href
        if kind == "message" and body.strip() == href:
            message["body"] = href
    return message


class Session:
    """Commands typed here, and command lines found in later output."""

    def __init__(self, writer: _WRITER | None = None, live: Callable[[dict], None] | None = None) -> None:
        self.follow_limit = MAX_FOLLOW
        self._writer = writer or _print
        self._live = live
        self._seen = ""
        self._out = sys.stdout
        self._living: dict[tuple[str, str], list[tuple]] = {}
        self._order: list = []
        self._last_model: tuple[str, str] | None = None
        self._runners: dict | None = None
        self.closed = False

    def emit_live(self, event: dict) -> None:
        """Show one model fragment now. The final reply will not repeat it."""
        if event.get("type") == "text-delta":
            self._seen += str(event.get("text") or "")
        if self._live is not None:
            self._live(event)
            return
        text = str(event.get("text") or "")
        if text:
            self._out.write(text)
            self._out.flush()

    def turn(self, line: str) -> None:
        """Run one line, then any command lines that show up in the output."""
        from kernel.command.live_stream import reset_emitter, use_emitter

        token = use_emitter(self.emit_live)
        try:
            self._turn(line)
        finally:
            reset_emitter(token)

    def _turn(self, line: str) -> None:
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
                output = self._without_seen(self.execute(current))
            except SessionExit:
                self.closed = True
                return
            self._emit(output)
            if _follow_commands(current, from_output):
                for found in command_lines(output, self._names()):
                    queue.append((found, True))
            if not from_output or self._last_model is None:
                continue
            if self._is_message_to_last(current):
                continue
            if steps >= self.follow_limit:
                self._show_stopped(
                    ["把结果交回刚才的模型", *[item for item, _flag in queue]]
                )
                return
            steps += 1
            reply = self._safe_message_last(output)
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
        if name == "process" and argv[1:2] == ["start"]:
            return self._process_start(argv[2:])
        if name == "capability" and argv[1:2] == ["load"]:
            return self._load(argv[2:])
        if name == "capability" and argv[1:2] in (["call"], ["chain"], ["group"], ["chord"]):
            return self._call(argv[1], argv[2:])
        runner = self._names_table().get(name)
        if runner is None:
            from kernel.command.dispatch import usage

            return usage()
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
        from kernel.services import launch_session

        return [launch_session(spec, launch_options(options))]

    def _process_start(self, argv: list[str]) -> str:
        from kernel.command.start import _parse_start_options

        try:
            options = _parse_start_options(argv)
        except UsageError as exc:
            return str(exc)
        try:
            services = self.open_started(options)
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

    def _call(self, mode: str, argv: list[str]) -> str:
        """Run a composition on the living process, or launch one when none is open."""
        from kernel.command.call import _line, execute
        from kernel.command.convention import parse
        from kernel.command.call import USAGE, render

        try:
            invocation = parse(argv, flags={"change": "repeat"}, usage=USAGE)
            line = _line(mode, invocation)
        except UsageError as exc:
            return str(exc)
        found = self._first_alive(line.store, line.name)
        if found is None:
            return _capture(lambda _argv: execute(line), [])
        service, role = found
        return render(service, line, role=role)

    def _load(self, argv: list[str]) -> str:
        from kernel.command.load import line_from

        try:
            line = line_from(argv)
        except UsageError as exc:
            return str(exc)
        capability = line.name
        profile_changes = line.changes
        kind = line.kind
        body = line.body
        store_path = line.store
        env_file = line.env_file
        env_keys = line.env_keys
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
        if kind == "message":
            self._last_model = (store_path, capability)
            turn = turn_from_payload(reply_payload(reply))
            if turn is not None and turn.tool_calls():
                tool_reply = self._execute_tool_call(
                    turn.tool_calls()[0],
                    store_path,
                    env_file,
                    env_keys,
                )
                return self._message_last(reply_text(tool_reply))
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
            argv.extend(["--change", f"{topic}={value}"])
        services = self.open_started(_parse_start_options(argv))
        self._remember(store_path, capability, services)
        return self._first_alive(store_path, capability)

    def _message_last(self, text: str) -> str:
        if self._last_model is None:
            return ""
        store_path, capability = self._last_model
        found = self._first_alive(store_path, capability)
        if found is None:
            return "刚才的模型已经不在"
        return reply_text(_send(found, slip("message", text)))

    def _safe_message_last(self, text: str) -> str:
        try:
            return self._message_last(text)
        except Exception as exc:
            return str(exc)

    def _is_message_to_last(self, line: str) -> bool:
        if self._last_model is None:
            return False
        try:
            argv = split_line(line)
        except ValueError:
            return False
        if not argv or argv[:2] != ["capability", "load"]:
            return False
        from kernel.command.load import line_from

        try:
            parsed = line_from(argv[2:])
        except UsageError:
            return False
        return parsed.kind == "message" and (parsed.store, parsed.name) == self._last_model

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

    def _without_seen(self, text: str) -> str:
        seen = self._seen
        self._seen = ""
        if seen and text and seen in text:
            return text.replace(seen, "", 1)
        return text

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
    from kernel.command.live_stream import StreamTail

    service, role = found
    ticket = service.submit(ServiceRequest.from_message(message, role=role))
    tail = StreamTail(str(ticket.ticket_id))
    tail.start()
    try:
        return service.wait(ticket, timeout=180)
    finally:
        tail.finish()


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
    from kernel.command.dispatch import usage

    if isinstance(exc.code, str) and exc.code:
        return exc.code
    return usage()


def _print(text: str) -> None:
    print(text, end="")


_DISPLAY_STREAM = None
_IMAGE = re.compile(r"https?://\S+\.(?:png|jpe?g|gif|webp)\b", re.IGNORECASE)


def _parts_in(body: str) -> list[dict] | None:
    """Return display parts when a reply is already a fragment list."""
    if not body.startswith(("{", "[")):
        return None
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return None
    if isinstance(payload, list) and payload and all(isinstance(item, dict) and "type" in item for item in payload):
        return payload
    if not isinstance(payload, dict):
        return None
    parts = payload.get("parts")
    if isinstance(parts, list) and parts and all(isinstance(item, dict) for item in parts):
        return parts
    blocks = payload.get("blocks")
    if payload.get("type") == "model_turn" and isinstance(blocks, list):
        return [block for block in blocks if isinstance(block, dict)]
    return None


def _event_from_part(part: dict) -> dict[str, str] | None:
    kind = str(part.get("type") or "")
    if kind == "text-delta":
        return {"type": "text-delta", "text": str(part.get("text") or "")}
    if kind == "text":
        return {"type": "text", "text": str(part.get("text") or "")}
    if kind == "image":
        href = str(part.get("href") or part.get("url") or part.get("text") or "")
        return {"type": "image", "href": href} if href else None
    if kind in {"tool-call", "tool-call-delta"}:
        name = str(part.get("name") or "")
        arguments = str(part.get("arguments") or "")
        shown = f"{name} {arguments}".strip()
        return {"type": "text", "text": shown} if shown else None
    return None


def events_for(text: str) -> list[dict[str, str]]:
    """Turn one reply into display events. Fragments stay fragments."""
    body = text.strip()
    parts = _parts_in(body)
    if parts:
        return [event for part in parts if (event := _event_from_part(part))]
    events: list[dict[str, str]] = []
    if body:
        events.append({"type": "text", "text": body})
    for href in _IMAGE.findall(body):
        events.append({"type": "image", "href": href.rstrip(".,)")})
    return events


def _input_text(line: str) -> str:
    raw = line.strip()
    if not raw:
        return ""
    if raw.startswith("{"):
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return line.rstrip("\r\n")
        if isinstance(payload, dict) and payload.get("type") == "input":
            return str(payload.get("text") or "")
    return line.rstrip("\r\n")


def _emit_event(event: dict[str, str]) -> None:
    stream = _DISPLAY_STREAM or sys.stdout
    stream.write(json.dumps(event, ensure_ascii=False) + "\n")
    stream.flush()


def _display_writer(text: str) -> None:
    for event in events_for(text):
        if event.get("text") or event.get("href"):
            _emit_event(event)


def _display_reader(_prompt: str = "") -> str:
    line = sys.stdin.readline()
    if line == "":
        raise EOFError
    return _input_text(line)


def run_display() -> int:
    """One living session. Commands come in as lines; replies go out as events."""
    global _DISPLAY_STREAM
    from kernel.process.process_creat.instances import repo_root

    _DISPLAY_STREAM = sys.stdout
    try:
        offer_env_files(str(repo_root()), _display_reader, _display_writer)
    except EOFError:
        return 0
    _emit_session()
    _emit_event({"type": "status", "text": "ready"})
    _emit_event({"type": "done"})
    session = Session(_display_writer, live=_emit_event)
    try:
        while not session.closed:
            line = sys.stdin.readline()
            if line == "":
                break
            text = _input_text(line)
            if not text.strip():
                continue
            if text.strip() == "exit":
                break
            _emit_event({"type": "status", "text": "running"})
            try:
                session.turn(text)
            except Exception as exc:
                _emit_event({"type": "error", "text": str(exc)})
            if session.closed:
                break
            _emit_event({"type": "status", "text": "ready"})
            _emit_event({"type": "done"})
    except EOFError:
        pass
    finally:
        session.close()
    return 0


def _emit_session() -> None:
    """Tell the TUI which directory and ledger this command session is using."""
    from pathlib import Path

    from kernel.resource.store.locator import default_env_file, default_store_locator, env_file_problem

    _emit_event(
        {
            "type": "session",
            "cwd": str(Path.cwd().resolve()),
            "store": default_store_locator(),
            "env": "已配置" if default_env_file() else "未配置",
            "text": env_file_problem(),
        }
    )


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


def _write_env_problem(writer: _WRITER) -> None:
    from kernel.resource.store.locator import env_file_problem

    problem = env_file_problem()
    if problem:
        writer(problem + "\n")


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
        _write_env_problem(writer)
        return None
    _write_env_problem(writer)
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
    if argv == ["--display", "json"]:
        return run_display()
    if argv:
        from kernel.command.dispatch import usage

        print(usage())
        return 2
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
