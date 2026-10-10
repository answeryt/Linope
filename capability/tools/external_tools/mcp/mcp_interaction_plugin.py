# -*- coding: utf-8 -*-
"""Standalone MCP server-to-client interaction plugin.

Provides sampling, elicitation, protocol logging, and list-change callbacks.
Host-specific model and approval behavior is supplied through callables, so
this file imports no project sibling.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
import time
from collections import deque
from typing import Any, Awaitable, Callable

from mcp.types import (
    CreateMessageResult,
    CreateMessageResultWithTools,
    ElicitResult,
    ErrorData,
    SamplingCapability,
    SamplingToolsCapability,
    TextContent,
)


PLUGIN_NAME = "mcp_bidirectional_interaction"
PLUGIN_VERSION = "1.0"

ModelHandler = Callable[[dict[str, Any]], Any | Awaitable[Any]]
ApprovalHandler = Callable[[dict[str, Any]], Any | Awaitable[Any]]
EventHandler = Callable[[dict[str, Any]], Any | Awaitable[Any]]


async def _call_handler(handler: Callable[[dict[str, Any]], Any], payload: dict[str, Any]) -> Any:
    if inspect.iscoroutinefunction(handler):
        return await handler(payload)
    result = await asyncio.to_thread(handler, payload)
    return await result if inspect.isawaitable(result) else result


class MCPInteractionPlugin:
    """Build callbacks consumed by ``mcp.ClientSession``."""

    _STOP_REASONS = {
        "stop": "endTurn",
        "length": "maxTokens",
        "tool_calls": "toolUse",
    }

    def __init__(
        self,
        server_name: str,
        *,
        model_handler: ModelHandler | None = None,
        approval_handler: ApprovalHandler | None = None,
        event_handler: EventHandler | None = None,
        model: str | None = None,
        allowed_models: list[str] | tuple[str, ...] = (),
        sampling_timeout: float = 30.0,
        elicitation_timeout: float = 300.0,
        max_sampling_rpm: int = 10,
        max_tokens: int = 4096,
        log_payload_limit: int = 2000,
    ) -> None:
        if not server_name:
            raise ValueError("server_name is required.")
        if sampling_timeout <= 0 or elicitation_timeout <= 0:
            raise ValueError("callback timeouts must be positive.")
        if max_sampling_rpm < 1 or max_tokens < 1:
            raise ValueError("sampling limits must be positive.")
        self.server_name = server_name
        self.model_handler = model_handler
        self.approval_handler = approval_handler
        self.event_handler = event_handler
        self.model = model
        self.allowed_models = (
            {allowed_models}
            if isinstance(allowed_models, str)
            else set(allowed_models)
        )
        self.sampling_timeout = sampling_timeout
        self.elicitation_timeout = elicitation_timeout
        self.max_sampling_rpm = max_sampling_rpm
        self.max_tokens = max_tokens
        self.log_payload_limit = max(128, log_payload_limit)
        self.metrics = {
            "sampling_requests": 0,
            "sampling_errors": 0,
            "elicitation_requests": 0,
            "elicitation_accepted": 0,
            "elicitation_declined": 0,
            "notifications": 0,
        }
        self._sampling_times: deque[float] = deque()
        self._pending_events: set[asyncio.Task[None]] = set()
        self._logger = logging.getLogger(f"mcp.server.{server_name}")

    def _sampling_allowed(self) -> bool:
        now = time.monotonic()
        cutoff = now - 60.0
        while self._sampling_times and self._sampling_times[0] <= cutoff:
            self._sampling_times.popleft()
        if len(self._sampling_times) >= self.max_sampling_rpm:
            return False
        self._sampling_times.append(now)
        return True

    @staticmethod
    def _sampling_messages(params: Any) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = []
        for message in getattr(params, "messages", None) or []:
            content = getattr(message, "content_as_list", None)
            if content is None:
                raw = getattr(message, "content", "")
                content = raw if isinstance(raw, list) else [raw]
            blocks: list[dict[str, Any]] = []
            for block in content:
                text = getattr(block, "text", None)
                if text is not None:
                    blocks.append({"type": "text", "text": text})
                    continue
                data = getattr(block, "data", None)
                mime = getattr(block, "mimeType", None)
                if data is not None and mime:
                    blocks.append(
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime};base64,{data}"},
                        },
                    )
            payload: Any = blocks
            if len(blocks) == 1 and blocks[0]["type"] == "text":
                payload = blocks[0]["text"]
            messages.append(
                {"role": str(getattr(message, "role", "user")), "content": payload},
            )
        system_prompt = getattr(params, "systemPrompt", None)
        if system_prompt:
            messages.insert(0, {"role": "system", "content": system_prompt})
        return messages

    def _requested_model(self, params: Any) -> str | None:
        if self.model:
            return self.model
        preferences = getattr(params, "modelPreferences", None)
        for hint in getattr(preferences, "hints", None) or []:
            name = getattr(hint, "name", None)
            if name:
                return str(name)
        return None

    async def sampling_callback(self, context: Any, params: Any) -> Any:
        """Handle ``sampling/createMessage`` with limits and host injection."""
        if self.model_handler is None:
            return ErrorData(code=-32601, message="Sampling is not configured.")
        if not self._sampling_allowed():
            self.metrics["sampling_errors"] += 1
            return ErrorData(code=-32000, message="Sampling rate limit exceeded.")

        model = self._requested_model(params)
        if self.allowed_models and model and model not in self.allowed_models:
            self.metrics["sampling_errors"] += 1
            return ErrorData(code=-32602, message=f"Model {model!r} is not allowed.")

        requested_tokens = getattr(params, "maxTokens", self.max_tokens)
        try:
            requested_tokens = int(requested_tokens)
        except (TypeError, ValueError, OverflowError):
            requested_tokens = self.max_tokens
        request = {
            "server": self.server_name,
            "model": model,
            "messages": self._sampling_messages(params),
            "max_tokens": max(1, min(requested_tokens, self.max_tokens)),
            "temperature": getattr(params, "temperature", None),
            "tools": getattr(params, "tools", None),
            "context": context,
            "raw_params": params,
        }
        try:
            response = await asyncio.wait_for(
                _call_handler(self.model_handler, request),
                timeout=self.sampling_timeout,
            )
        except asyncio.TimeoutError:
            self.metrics["sampling_errors"] += 1
            return ErrorData(code=-32001, message="Sampling request timed out.")
        except Exception as error:
            self.metrics["sampling_errors"] += 1
            return ErrorData(
                code=-32603,
                message=f"Sampling handler failed: {type(error).__name__}",
            )

        self.metrics["sampling_requests"] += 1
        if isinstance(
            response,
            (CreateMessageResult, CreateMessageResultWithTools, ErrorData),
        ):
            return response
        if not isinstance(response, dict):
            response = {"text": str(response)}
        text = str(response.get("text", response.get("content", "")))
        stop_reason = self._STOP_REASONS.get(
            str(response.get("finish_reason", "stop")),
            str(response.get("stop_reason", "endTurn")),
        )
        return CreateMessageResult(
            role="assistant",
            content=TextContent(type="text", text=text),
            model=str(response.get("model") or model or "host-default"),
            stopReason=stop_reason,
        )

    async def elicitation_callback(self, context: Any, params: Any) -> Any:
        """Handle form-mode elicitation and fail closed on every error."""
        self.metrics["elicitation_requests"] += 1
        mode = str(getattr(params, "mode", "form"))
        if mode == "url" or self.approval_handler is None:
            self.metrics["elicitation_declined"] += 1
            return ElicitResult(action="decline")

        schema = (
            getattr(params, "requested_schema", None)
            or getattr(params, "requestedSchema", None)
            or {}
        )
        request = {
            "server": self.server_name,
            "message": str(getattr(params, "message", "") or ""),
            "schema": schema,
            "mode": mode,
            "context": context,
            "raw_params": params,
        }
        try:
            answer = await asyncio.wait_for(
                _call_handler(self.approval_handler, request),
                timeout=self.elicitation_timeout,
            )
        except asyncio.TimeoutError:
            return ElicitResult(action="cancel")
        except Exception:
            self.metrics["elicitation_declined"] += 1
            return ElicitResult(action="decline")

        if isinstance(answer, ElicitResult):
            return answer
        if isinstance(answer, dict):
            action = str(answer.get("action", "decline"))
            content = answer.get("content")
        else:
            action = str(answer)
            content = None
        if action == "accept":
            self.metrics["elicitation_accepted"] += 1
            return ElicitResult(action="accept", content=content or {})
        if action == "cancel":
            return ElicitResult(action="cancel")
        self.metrics["elicitation_declined"] += 1
        return ElicitResult(action="decline")

    async def logging_callback(self, params: Any) -> None:
        """Route MCP ``notifications/message`` into host logging/events."""
        level_name = str(getattr(params, "level", "info")).lower()
        level = {
            "debug": logging.DEBUG,
            "info": logging.INFO,
            "notice": logging.INFO,
            "warning": logging.WARNING,
            "error": logging.ERROR,
            "critical": logging.CRITICAL,
            "alert": logging.CRITICAL,
            "emergency": logging.CRITICAL,
        }.get(level_name, logging.INFO)
        data = getattr(params, "data", None)
        if not isinstance(data, str):
            data = json.dumps(data, ensure_ascii=False, default=str)
        if len(data) > self.log_payload_limit:
            data = data[: self.log_payload_limit] + "... [truncated]"
        logger_name = getattr(params, "logger", None)
        self._logger.log(level, "[%s] %s", logger_name or self.server_name, data)
        self._schedule_event(
            {
                "kind": "log",
                "server": self.server_name,
                "level": level_name,
                "logger": logger_name,
                "data": data,
            },
        )

    async def message_handler(self, message: Any) -> None:
        """Dispatch list-change notifications without issuing nested RPCs."""
        root = getattr(message, "root", message)
        type_name = type(root).__name__.lower()
        method = str(getattr(root, "method", "")).lower()
        kind = None
        if "toollistchanged" in type_name or "tools/list_changed" in method:
            kind = "tools_changed"
        elif "promptlistchanged" in type_name or "prompts/list_changed" in method:
            kind = "prompts_changed"
        elif "resourcelistchanged" in type_name or "resources/list_changed" in method:
            kind = "resources_changed"
        if kind:
            self.metrics["notifications"] += 1
            self._schedule_event({"kind": kind, "server": self.server_name})
            await asyncio.sleep(0)

    async def _emit(self, event: dict[str, Any]) -> None:
        if self.event_handler is not None:
            await _call_handler(self.event_handler, event)

    def _schedule_event(self, event: dict[str, Any]) -> None:
        """Keep notification work outside the SDK receive-loop callback."""
        if self.event_handler is None:
            return
        task = asyncio.create_task(self._emit(event))
        self._pending_events.add(task)
        task.add_done_callback(self._pending_events.discard)

    async def close(self) -> None:
        """Cancel and join outstanding host event deliveries."""
        tasks = tuple(self._pending_events)
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._pending_events.clear()

    def session_kwargs(
        self,
        client_session_type: type[Any] | None = None,
    ) -> dict[str, Any]:
        """Return SDK-version-compatible ``ClientSession`` callback kwargs."""
        kwargs: dict[str, Any] = {
            "logging_callback": self.logging_callback,
            "message_handler": self.message_handler,
        }
        if self.model_handler is not None:
            kwargs["sampling_callback"] = self.sampling_callback
            kwargs["sampling_capabilities"] = SamplingCapability(
                tools=SamplingToolsCapability(),
            )
        if self.approval_handler is not None:
            kwargs["elicitation_callback"] = self.elicitation_callback
        if client_session_type is not None:
            try:
                supported = inspect.signature(client_session_type).parameters
            except (TypeError, ValueError):
                supported = {}
            kwargs = {
                key: value
                for key, value in kwargs.items()
                if key in supported
            }
        return kwargs

def capability_profile(capability_id, changes):
    """Tell the process this tool needs a tool resource."""
    from kernel.process.declaration import ProcessDeclaration, ResourceClaim
    from kernel.resource.definition import ResourceKind

    return ProcessDeclaration(
        capability=capability_id,
        resources=(
            ResourceClaim(kind=ResourceKind.TOOL, identity={"id": capability_id}),
        ),
    )

