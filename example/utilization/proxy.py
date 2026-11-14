"""Record each model request without queueing or rejecting it.

The proxy is a clock. It does not decide which arm may call the model.
A second request that arrives while the first is still running is forwarded
and recorded; the analysis marks that round invalid.
"""

from __future__ import annotations

import gzip
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from example.utilization.common import append_event


def completion_to_turn(payload: dict[str, Any]) -> dict[str, Any]:
    """OpenAI chat completion to the model_turn the Linope loop already accepts."""

    choice = (payload.get("choices") or [{}])[0]
    message = choice.get("message") or {}
    blocks: list[dict[str, Any]] = []
    reasoning = message.get("reasoning_content")
    if isinstance(reasoning, str) and reasoning:
        blocks.append({"type": "reasoning", "text": reasoning})
    content = message.get("content")
    if isinstance(content, str) and content:
        blocks.append({"type": "text", "text": content})
    for call in message.get("tool_calls") or []:
        function = call.get("function") or {}
        blocks.append({
            "type": "tool-call",
            "id": str(call.get("id") or ""),
            "name": str(function.get("name") or ""),
            "arguments": function.get("arguments") if function.get("arguments") is not None else "{}",
        })
    return {
        "type": "model_turn",
        "blocks": blocks,
        "finish_reason": str(choice.get("finish_reason") or "stop"),
    }


def _mock_completion(body: dict[str, Any]) -> dict[str, Any]:
    messages = body.get("messages") or []
    if any(isinstance(item, dict) and item.get("role") == "tool" for item in messages):
        content = ""
        for item in reversed(messages):
            if isinstance(item, dict) and item.get("role") == "tool":
                content = str(item.get("content") or "")
                break
        return {
            "choices": [{
                "finish_reason": "stop",
                "message": {"role": "assistant", "content": content},
            }]
        }
    user = ""
    for item in reversed(messages):
        if isinstance(item, dict) and item.get("role") == "user":
            user = str(item.get("content") or "")
            break
    path = ""
    seconds = "0"
    for line in user.splitlines():
        if " with path " in line and " and seconds " in line:
            path = line.split(" with path ", 1)[1].split(" and seconds ", 1)[0].strip()
            seconds = line.split(" and seconds ", 1)[1].strip().rstrip(".")
    arguments = json.dumps({"path": path, "seconds": float(seconds or 0)}, ensure_ascii=False)
    return {
        "choices": [{
            "finish_reason": "tool_calls",
            "message": {
                "role": "assistant",
                "content": "",
                "tool_calls": [{
                    "id": "call-wait",
                    "type": "function",
                    "function": {"name": "wait_read", "arguments": arguments},
                }],
            },
        }]
    }


class Proxy:
    """One local OpenAI-compatible endpoint that writes request intervals."""

    def __init__(
        self,
        log_path: Path,
        *,
        mock: bool = False,
        upstream: str = "",
        mock_seconds: float = 0.05,
        serial: bool = False,
    ) -> None:
        self.log_path = log_path
        self.mock = mock
        self.upstream = upstream.rstrip("/")
        self.mock_seconds = mock_seconds
        self.serial = serial
        self._slot = threading.Lock()
        self._httpd: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    @property
    def base_url(self) -> str:
        if self._httpd is None:
            raise RuntimeError("proxy is not started")
        host, port = self._httpd.server_address[:2]
        return f"http://{host}:{port}/v1"

    def start(self) -> str:
        proxy = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, fmt: str, *args: object) -> None:
                del fmt, args

            def do_GET(self) -> None:  # noqa: N802
                if self.path.rstrip("/") == "/health":
                    raw = b'{"ok":true}'
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(raw)))
                    self.end_headers()
                    self.wfile.write(raw)
                    return
                self.send_error(404)

            def do_POST(self) -> None:  # noqa: N802
                length = int(self.headers.get("Content-Length") or 0)
                raw = self.rfile.read(length)
                ident = uuid.uuid4().hex
                task = self.headers.get("X-Task-Id") or _task_from_body(raw)

                def serve() -> None:
                    append_event(proxy.log_path, {
                        "kind": "request_start",
                        "id": ident,
                        "task": task,
                        "t": time.time(),
                    })
                    status = 502
                    try:
                        if proxy.mock:
                            if proxy.mock_seconds:
                                time.sleep(proxy.mock_seconds)
                            body = json.loads(raw.decode("utf-8"))
                            payload = _mock_completion(body)
                            status = 200
                            response = json.dumps(payload).encode("utf-8")
                            self._write_bytes(status, "application/json", response)
                        else:
                            status = self._pipe_upstream(proxy.upstream, raw)
                    except Exception as exc:
                        status = 502
                        response = json.dumps({"error": str(exc)}).encode("utf-8")
                        self._write_bytes(status, "application/json", response)
                    append_event(proxy.log_path, {
                        "kind": "request_end",
                        "id": ident,
                        "task": task,
                        "t": time.time(),
                        "status": status,
                    })

                if proxy.serial:
                    with proxy._slot:
                        serve()
                else:
                    serve()

            def _write_bytes(self, status: int, content_type: str, response: bytes) -> None:
                self.send_response(status)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(response)))
                self.end_headers()
                self.wfile.write(response)

            def _pipe_upstream(self, upstream: str, raw: bytes) -> int:
                """Copy the provider stream through, including server-sent events."""

                if not upstream:
                    raise RuntimeError("Set UTILIZATION_UPSTREAM or pass --upstream")
                request = urllib.request.Request(upstream + self.path, data=raw, method="POST")
                for key, value in self.headers.items():
                    if key.lower() in {"host", "content-length", "accept-encoding"}:
                        continue
                    request.add_header(key, value)
                try:
                    upstream_response = urllib.request.urlopen(request, timeout=300)
                except urllib.error.HTTPError as exc:
                    self._write_bytes(
                        exc.code,
                        exc.headers.get("Content-Type") or "application/json",
                        exc.read(),
                    )
                    return exc.code
                with upstream_response:
                    body = upstream_response.read()
                    if (upstream_response.headers.get("Content-Encoding") or "").lower() == "gzip":
                        body = gzip.decompress(body)
                    content_type = upstream_response.headers.get("Content-Type") or "application/json"
                    if "text/event-stream" in content_type and not body.endswith(b"\n"):
                        body += b"\n"
                    self._write_bytes(upstream_response.status, content_type, body)
                    return upstream_response.status

        self._httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(target=self._httpd.serve_forever, name="utilization-proxy", daemon=True)
        self._thread.start()
        return self.base_url

    def close(self) -> None:
        if self._httpd is not None:
            self._httpd.shutdown()
            self._httpd.server_close()
            self._httpd = None


def _task_from_body(raw: bytes) -> str:
    """The task id written into the user message. dsh does not send X-Task-Id."""

    try:
        body = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return ""
    messages = body.get("messages")
    if not isinstance(messages, list):
        return ""
    for message in messages:
        if not isinstance(message, dict):
            continue
        content = message.get("content")
        texts: list[str] = []
        if isinstance(content, str):
            texts.append(content)
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, str):
                    texts.append(block)
                elif isinstance(block, dict) and isinstance(block.get("text"), str):
                    texts.append(block["text"])
        for text in texts:
            for line in text.splitlines():
                if line.startswith("task: "):
                    return line.split("task: ", 1)[1].strip()
    return ""


def _forward(upstream: str, path: str, raw: bytes, headers: Any) -> tuple[int, bytes]:
    if not upstream:
        raise RuntimeError("Set UTILIZATION_UPSTREAM or pass --upstream")
    target = upstream + path
    request = urllib.request.Request(target, data=raw, method="POST")
    request.add_header("Content-Type", headers.get("Content-Type") or "application/json")
    if headers.get("Authorization"):
        request.add_header("Authorization", headers.get("Authorization"))
    try:
        with urllib.request.urlopen(request, timeout=300) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


def post_chat(base_url: str, body: dict[str, Any], task_id: str, api_key: str = "") -> dict[str, Any]:
    """Send one chat completion through the recording proxy."""

    raw = json.dumps(body).encode("utf-8")
    request = urllib.request.Request(
        base_url.rstrip("/") + "/chat/completions",
        data=raw,
        method="POST",
    )
    request.add_header("Content-Type", "application/json")
    request.add_header("X-Task-Id", task_id)
    if api_key:
        request.add_header("Authorization", f"Bearer {api_key}")
    try:
        with urllib.request.urlopen(request, timeout=300) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--log", required=True)
    parser.add_argument("--mock", action="store_true")
    parser.add_argument("--upstream", default=os.environ.get("UTILIZATION_UPSTREAM", ""))
    parser.add_argument("--mock-seconds", type=float, default=0.05)
    args = parser.parse_args(argv)
    proxy = Proxy(Path(args.log), mock=args.mock, upstream=args.upstream, mock_seconds=args.mock_seconds)
    print(proxy.start(), flush=True)
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        proxy.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
