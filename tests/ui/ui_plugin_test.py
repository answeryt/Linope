from __future__ import annotations

import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest import mock
from urllib.error import HTTPError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[2]


def load(relative: str) -> Any:
    path = ROOT / relative
    spec = importlib.util.spec_from_file_location(path.stem, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


startup = load("ui/startup/ui_startup_plugin.py")
server = load("ui/server/ui_server_plugin.py")
static = load("ui/static/ui_static_plugin.py")
shell = load("ui/api/ui_shell_plugin.py")
opening = load("ui/open/ui_open_plugin.py")
cli = load("ui/cli/ui_cli_plugin.py")


def _dist(root: Path) -> Path:
    dist = root / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<html>shell</html>", encoding="utf-8")
    (dist / "app.js").write_text("console.log(1)", encoding="utf-8")
    return dist / "index.html"


class UiStartupTest(unittest.TestCase):
    def test_omitted_flags_leave_bind_values_unset(self) -> None:
        values = startup.parse_startup([])
        self.assertIsNone(values["host"])
        self.assertIsNone(values["port"])
        self.assertEqual([], values["trusted_hosts"])
        self.assertFalse(values["no_open"])

    def test_named_flags(self) -> None:
        values = startup.parse_startup(
            [
                "--host",
                "127.0.0.1",
                "--port",
                "8080",
                "--trusted-host",
                "lab.internal",
                "--trusted-host",
                "10.0.0.9",
                "--no-open",
            ]
        )
        self.assertEqual("127.0.0.1", values["host"])
        self.assertEqual(8080, values["port"])
        self.assertEqual(["lab.internal", "10.0.0.9"], values["trusted_hosts"])
        self.assertTrue(values["no_open"])

    def test_help_exits_without_values(self) -> None:
        buffer = io.StringIO()
        with mock.patch("sys.stdout", buffer):
            with self.assertRaises(SystemExit) as raised:
                startup.parse_startup(["--help"])
        self.assertEqual(0, raised.exception.code)
        self.assertIn("--trusted-host", buffer.getvalue())

    def test_non_numeric_port_is_usage_error(self) -> None:
        buffer = io.StringIO()
        with mock.patch("sys.stderr", buffer):
            with self.assertRaises(SystemExit) as raised:
                startup.parse_startup(["--port", "abc"])
        self.assertNotEqual(0, raised.exception.code)
        self.assertIn("--port must be a number", buffer.getvalue())

    def test_all_interfaces_host_is_rejected(self) -> None:
        with self.assertRaises(SystemExit) as raised:
            startup.parse_startup(["--host", "0.0.0.0"])
        self.assertIn("intentionally not supported", str(raised.exception))


class UiServerTest(unittest.TestCase):
    def test_named_route_and_unmatched_404(self) -> None:
        httpd = server.create_server(host="127.0.0.1", port=0)
        httpd.register(
            "exact",
            "/health",
            lambda _request: {
                "status": 200,
                "headers": {"content-type": "text/plain"},
                "body": b"ok",
            },
        )
        try:
            port = httpd.listen()
            with urlopen(f"http://127.0.0.1:{port}/health") as response:
                self.assertEqual(b"ok", response.read())
            with self.assertRaises(HTTPError) as raised:
                urlopen(f"http://127.0.0.1:{port}/missing")
            self.assertEqual(404, raised.exception.code)
        finally:
            httpd.close()

    def test_duplicate_route_and_fallback_rejected(self) -> None:
        httpd = server.create_server()
        handler = lambda _request: {"status": 200, "headers": {}, "body": b""}
        httpd.register("exact", "/a", handler)
        with self.assertRaises(ValueError):
            httpd.register("exact", "/a", handler)
        httpd.register_fallback(handler)
        with self.assertRaises(ValueError):
            httpd.register_fallback(handler)


class UiStaticTest(unittest.TestCase):
    def test_asset_spa_fallback_and_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            index = _dist(Path(tmp))
            asset = static.serve_static(
                "/app.js",
                dist_root=str(index.parent),
                dist_index=str(index),
                render_index=index.read_text,
            )
            self.assertEqual(200, asset["status"])
            self.assertEqual(b"console.log(1)", asset["body"])
            miss = static.serve_static(
                "/session/1",
                dist_root=str(index.parent),
                dist_index=str(index),
                render_index=lambda: "<html>shell</html>",
            )
            self.assertEqual(200, miss["status"])
            self.assertIn(b"shell", miss["body"])
            denied = static.serve_static(
                "/../secret",
                dist_root=str(index.parent),
                dist_index=str(index),
                render_index=lambda: "no",
            )
            self.assertEqual(403, denied["status"])

    def test_non_get_is_405_and_index_taps_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            index = _dist(Path(tmp))
            captured: list[Any] = []

            def register_fallback(handler: Any) -> None:
                captured.append(handler)

            static.mount_static(
                register_fallback=register_fallback,
                apply_index_taps=lambda html: html.replace("shell", "booted"),
                dist_index=str(index),
            )
            handler = captured[0]
            self.assertEqual(405, handler({"method": "POST", "path": "/"})["status"])
            body = handler({"method": "GET", "path": "/"})["body"]
            self.assertIn(b"booted", body)

    def test_missing_dist_fails_loud(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(FileNotFoundError) as raised:
                static.resolve_dist_index(tmp)
            self.assertIn("frontend dist not built", str(raised.exception))


class UiOpenTest(unittest.TestCase):
    def test_ready_line_and_loopback_url(self) -> None:
        self.assertEqual("http://127.0.0.1:3080", opening.local_url(3080))
        self.assertEqual("ui: http://127.0.0.1:8080", opening.format_ready_line(8080))
        self.assertEqual(
            "ui: http://127.0.0.1:8080 (LAN: http://10.0.0.8:8080)",
            opening.format_ready_line(8080, ["10.0.0.8"]),
        )

    def test_ssh_and_no_open_suppress_browser(self) -> None:
        self.assertFalse(
            opening.should_open_browser({"SSH_CONNECTION": "10.0.0.2 55 10.0.0.9 22"})
        )
        self.assertFalse(opening.should_open_browser({}, no_open=True))
        self.assertTrue(opening.should_open_browser({}))

    def test_announce_prints_and_opens(self) -> None:
        lines: list[str] = []
        opened: list[str] = []
        url = opening.announce(
            host="127.0.0.1",
            port=3080,
            print_fn=lines.append,
            open_url=opened.append,
            env={},
        )
        self.assertEqual("http://127.0.0.1:3080", url)
        self.assertEqual(["ui: http://127.0.0.1:3080"], lines)
        self.assertEqual(["http://127.0.0.1:3080"], opened)
        opened.clear()
        opening.announce(
            host="127.0.0.1",
            port=3080,
            no_open=True,
            print_fn=lambda _line: None,
            open_url=opened.append,
            env={},
        )
        self.assertEqual([], opened)


class UiShellTest(unittest.TestCase):
    def test_empty_shell_has_no_records(self) -> None:
        payload = shell.empty_shell()
        self.assertEqual([], payload["workspaces"])
        self.assertEqual([], payload["sessions"])
        self.assertEqual([], payload["messages"])
        self.assertIsNone(payload["selectedWorkspaceId"])
        self.assertIsNone(payload["selectedSessionId"])
        self.assertIsNone(payload["model"])


class UiCliTest(unittest.TestCase):
    def test_cli_serves_dist_prints_and_opens(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            index = _dist(Path(tmp))
            lines: list[str] = []
            opened: list[str] = []
            held: dict[str, Any] = {}

            def create_server(*, host: str, port: int) -> Any:
                httpd = server.create_server(host=host, port=port)
                held["server"] = httpd
                return httpd

            def announce(**kwargs: Any) -> str:
                kwargs.setdefault("env", {})
                kwargs["print_fn"] = lines.append
                kwargs["open_url"] = opened.append
                return opening.announce(**kwargs)

            try:
                code = cli.run_cli(
                    parse_startup=startup.parse_startup,
                    create_server=create_server,
                    mount_shell=shell.mount_shell,
                    mount_static=static.mount_static,
                    announce=announce,
                    resolve_dist_index=lambda: str(index),
                    argv=["--port", "0", "--trusted-host", "lab.internal"],
                    wait=False,
                )
                self.assertEqual(0, code)
                httpd = held["server"]
                port = httpd.listened_port
                self.assertIsNotNone(port)
                with urlopen(f"http://127.0.0.1:{port}/") as response:
                    self.assertIn(b"shell", response.read())
                with urlopen(f"http://127.0.0.1:{port}/app.js") as response:
                    self.assertEqual(b"console.log(1)", response.read())
                head = urlopen(Request(f"http://127.0.0.1:{port}/", method="HEAD"))
                self.assertEqual(200, head.status)
                self.assertEqual([f"ui: http://127.0.0.1:{port}"], lines)
                self.assertEqual([f"http://127.0.0.1:{port}"], opened)
                with urlopen(f"http://127.0.0.1:{port}/api/shell") as response:
                    payload = json.loads(response.read().decode("utf-8"))
                self.assertEqual([], payload["workspaces"])
                self.assertEqual([], payload["sessions"])
                self.assertEqual([], payload["messages"])
                self.assertIsNone(payload["selectedWorkspaceId"])
                self.assertIsNone(payload["selectedSessionId"])
                self.assertIsNone(payload["model"])
            finally:
                if "server" in held:
                    held["server"].close()

    def test_cli_requires_injected_dependencies(self) -> None:
        with self.assertRaises(TypeError):
            cli.run_cli(
                parse_startup=None,
                create_server=server.create_server,
                mount_shell=shell.mount_shell,
                mount_static=static.mount_static,
                announce=opening.announce,
                resolve_dist_index=static.resolve_dist_index,
            )


if __name__ == "__main__":
    unittest.main()
