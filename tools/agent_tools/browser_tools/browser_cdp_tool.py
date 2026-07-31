#!/usr/bin/env python3

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

CDP_DOCS_URL = "https://chromedevtools.github.io/devtools-protocol/"

_SENSITIVE_VALUE_PATTERN = re.compile(
    r"(?i)\b(authorization|api[_-]?key|access[_-]?token|secret|password|cookie)"
    r"(\s*[:=]\s*)([^\s,;&]+)"
)
_BEARER_TOKEN_PATTERN = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+")


def tool_error(message: str, **details: Any) -> str:
    """Return a consistent JSON error response without the Hermes registry."""
    payload: Dict[str, Any] = {"success": False, "error": message}
    payload.update(details)
    return json.dumps(payload, ensure_ascii=False)

_CDP_PRIVATE_PAGE_ALLOWED_METHODS = {
    # Browser/target inspection does not read the current page body, cookies,
    # DOM, storage, or screenshots. Keep these working so the model can list
    # tabs or navigate away from a blocked page.
    "Browser.getVersion",
    "Target.getTargets",
    "Target.attachToTarget",
    "Target.detachFromTarget",
    "Page.navigate",
    "Page.reload",
    "Page.stopLoading",
}


def _redact_cdp_output(value: Any) -> Any:
    """Redact browser-originated CDP result data before returning it."""
    if isinstance(value, str):
        value = _BEARER_TOKEN_PATTERN.sub("Bearer [REDACTED]", value)
        return _SENSITIVE_VALUE_PATTERN.sub(
            lambda match: f"{match.group(1)}{match.group(2)}[REDACTED]",
            value,
        )
    if isinstance(value, list):
        return [_redact_cdp_output(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_redact_cdp_output(item) for item in value)
    if isinstance(value, dict):
        return {key: _redact_cdp_output(item) for key, item in value.items()}
    return value

# ``websockets`` is a direct hermes-agent dependency because the browser CDP
# supervisor and browser_dialog tool import it during tool discovery. Wrap the
# import so a clean error surfaces if an environment is stale or incomplete.
try:
    import websockets
    from websockets.exceptions import WebSocketException

    _WS_AVAILABLE = True
except ImportError:
    websockets = None  # type: ignore[assignment]
    WebSocketException = Exception  # type: ignore[assignment,misc]
    _WS_AVAILABLE = False


# ---------------------------------------------------------------------------
# Async-from-sync bridge (matches the pattern in homeassistant_tool.py)
# ---------------------------------------------------------------------------


def _run_async(coro):
    """Run an async coroutine from a sync handler, safe inside or outside a loop."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(asyncio.run, coro)
            return future.result()
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Endpoint resolution
# ---------------------------------------------------------------------------


def _resolve_cdp_endpoint() -> str:
    """Return the normalized CDP WebSocket URL, or empty string if unavailable.

    Delegates to ``tools.browser_tool._get_cdp_override`` so precedence stays
    consistent with the rest of the browser tool surface:

    1. ``BROWSER_CDP_URL`` env var (live override from ``/browser connect``)
    2. ``browser.cdp_url`` in ``config.yaml``
    """
    try:
        from tools.agent_tools.browser_tools.browser_tool import _get_cdp_override

        return (_get_cdp_override() or "").strip()
    except Exception as exc:  # pragma: no cover — defensive
        logger.debug("browser_cdp: failed to resolve CDP endpoint: %s", exc)
        return ""


def _private_page_guard_error(blocked_url: str, method: str) -> str:
    return tool_error(
        "Blocked: page URL targets a private or internal address "
        f"({blocked_url}). Raw CDP method {method!r} could expose private "
        "page content or state.",
        method=method,
        cdp_docs=CDP_DOCS_URL,
    )


def _browser_cdp_private_guard(
    *,
    task_id: str,
    method: str,
    params: Dict[str, Any],
) -> Optional[str]:
    """Apply the browser SSRF/private-page guard to raw CDP calls.

    ``browser_cdp`` is intentionally an escape hatch, but it still shares the
    same cloud/private-network boundary as ``browser_snapshot``,
    ``browser_console`` and ``browser_eval``.  If a cloud browser has landed on
    a private/internal URL (for example via a prior eval navigation), raw CDP
    calls like ``Runtime.evaluate`` or ``DOM.getDocument`` must not become the
    sibling bypass for the guarded browser tools.
    """
    try:
        from tools.agent_tools.browser_tools import browser_tool as bt

        if not bt._eval_ssrf_guard_active(task_id):  # type: ignore[attr-defined]
            return None

        if method == "Page.navigate":
            target_url = str((params or {}).get("url") or "").strip()
            if target_url and (
                bt._is_always_blocked_url(target_url)  # type: ignore[attr-defined]
                or not bt._is_safe_url(target_url)  # type: ignore[attr-defined]
            ):
                return tool_error(
                    "Blocked: CDP Page.navigate target is a private or "
                    f"internal address ({target_url}).",
                    method=method,
                    cdp_docs=CDP_DOCS_URL,
                )

        if method == "Runtime.evaluate":
            expression = str((params or {}).get("expression") or "")
            blocked_literal = bt._expression_targets_private_url(expression)  # type: ignore[attr-defined]
            if blocked_literal:
                return tool_error(
                    "Blocked: CDP Runtime.evaluate expression targets a "
                    f"private or internal address ({blocked_literal}).",
                    method=method,
                    cdp_docs=CDP_DOCS_URL,
                )

        if method not in _CDP_PRIVATE_PAGE_ALLOWED_METHODS:
            blocked_url = bt._current_page_private_url(task_id)  # type: ignore[attr-defined]
            if blocked_url:
                return _private_page_guard_error(blocked_url, method)
    except Exception as exc:  # noqa: BLE001
        # Match the existing browser guards' posture: guard probes are
        # best-effort and should not break local/custom CDP workflows.
        logger.debug("browser_cdp: private-page guard probe failed: %s", exc)
    return None


# ---------------------------------------------------------------------------
# Core CDP call
# ---------------------------------------------------------------------------


async def _cdp_call(
    ws_url: str,
    method: str,
    params: Dict[str, Any],
    target_id: Optional[str],
    timeout: float,
) -> Dict[str, Any]:
    """Make a single CDP call, optionally attaching to a target first.

    When ``target_id`` is provided, we call ``Target.attachToTarget`` with
    ``flatten=True`` to multiplex a page-level session over the same
    browser-level WebSocket, then send ``method`` with that ``sessionId``.
    When ``target_id`` is None, ``method`` is sent at browser level — which
    works for ``Target.*``, ``Browser.*``, ``Storage.*`` and a few other
    globally-scoped domains.
    """
    assert websockets is not None  # guarded by _WS_AVAILABLE at call-site

    async with websockets.connect(
        ws_url,
        max_size=None,  # CDP responses (e.g. DOM.getDocument) can be large
        open_timeout=timeout,
        close_timeout=5,
        ping_interval=None,  # CDP server doesn't expect pings
    ) as ws:
        next_id = 1
        session_id: Optional[str] = None

        # --- Step 1: attach to target if requested ---
        if target_id:
            attach_id = next_id
            next_id += 1
            await ws.send(
                json.dumps(
                    {
                        "id": attach_id,
                        "method": "Target.attachToTarget",
                        "params": {"targetId": target_id, "flatten": True},
                    }
                )
            )
            deadline = asyncio.get_running_loop().time() + timeout
            while True:
                remaining = deadline - asyncio.get_running_loop().time()
                if remaining <= 0:
                    raise TimeoutError(
                        f"Timed out attaching to target {target_id}"
                    )
                raw = await asyncio.wait_for(ws.recv(), timeout=remaining)
                msg = json.loads(raw)
                if msg.get("id") == attach_id:
                    if "error" in msg:
                        raise RuntimeError(
                            f"Target.attachToTarget failed: {msg['error']}"
                        )
                    session_id = msg.get("result", {}).get("sessionId")
                    if not session_id:
                        raise RuntimeError(
                            "Target.attachToTarget did not return a sessionId"
                        )
                    break
                # Ignore events (messages without "id") while waiting

        # --- Step 2: dispatch the real method ---
        call_id = next_id
        next_id += 1
        req: Dict[str, Any] = {
            "id": call_id,
            "method": method,
            "params": params or {},
        }
        if session_id:
            req["sessionId"] = session_id
        await ws.send(json.dumps(req))

        deadline = asyncio.get_running_loop().time() + timeout
        while True:
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                raise TimeoutError(
                    f"Timed out waiting for response to {method}"
                )
            raw = await asyncio.wait_for(ws.recv(), timeout=remaining)
            msg = json.loads(raw)
            if msg.get("id") == call_id:
                if "error" in msg:
                    raise RuntimeError(f"CDP error: {msg['error']}")
                return msg.get("result", {})
            # Ignore events / out-of-order responses


# ---------------------------------------------------------------------------
# Public tool function
# ---------------------------------------------------------------------------


def _browser_cdp_via_supervisor(
    task_id: str,
    frame_id: str,
    method: str,
    params: Optional[Dict[str, Any]],
    timeout: float,
) -> str:
    """Report that frame routing is unavailable without a supervisor module."""
    return tool_error(
        "frame_id routing is unavailable because this project does not include "
        "the browser supervisor.",
        task_id=task_id,
        frame_id=frame_id,
        method=method,
        params=params or {},
        timeout=timeout,
        cdp_docs=CDP_DOCS_URL,
    )


def browser_cdp(
    method: str,
    params: Optional[Dict[str, Any]] = None,
    target_id: Optional[str] = None,
    frame_id: Optional[str] = None,
    timeout: float = 30.0,
    task_id: Optional[str] = None,
) -> str:
    """Send a raw CDP command.  See ``CDP_DOCS_URL`` for method documentation.

    Args:
        method: CDP method name, e.g. ``"Target.getTargets"``.
        params: Method-specific parameters; defaults to ``{}``.
        target_id: Optional target/tab ID for page-level methods.  When set,
            we first attach to the target (``flatten=True``) and send
            ``method`` with the resulting ``sessionId``.  Uses a fresh
            stateless CDP connection.
        frame_id: Optional cross-origin (OOPIF) iframe ``frame_id`` from
            ``browser_snapshot.frame_tree.children[]``.  When set (and the
            frame is an OOPIF with a live session tracked by the CDP
            supervisor), routes the call through the supervisor's existing
            WebSocket — which is how you Runtime.evaluate *inside* an
            iframe on backends where per-call fresh CDP connections would
            hit signed-URL expiry (Browserbase) or expensive reattach.
        timeout: Seconds to wait for the call to complete.
        task_id: Task identifier for supervisor lookup.  When ``frame_id``
            is set, this identifies which task's supervisor to use; the
            handler will default to ``"default"`` otherwise.

    Returns:
        JSON string ``{"success": True, "method": ..., "result": {...}}`` on
        success, or ``{"error": "..."}`` on failure.
    """
    effective_task_id = task_id or "default"

    # --- Route iframe-scoped calls through the supervisor ---------------
    if frame_id:
        # Same private-page/SSRF boundary as the stateless path below —
        # frame_id routing must not become the sibling bypass for it.
        blocked = _browser_cdp_private_guard(
            task_id=effective_task_id,
            method=method,
            params=params or {},
        )
        if blocked:
            return blocked
        return _browser_cdp_via_supervisor(
            task_id=effective_task_id,
            frame_id=frame_id,
            method=method,
            params=params,
            timeout=timeout,
        )

    if not method or not isinstance(method, str):
        return tool_error(
            "'method' is required (e.g. 'Target.getTargets')",
            cdp_docs=CDP_DOCS_URL,
        )

    if not _WS_AVAILABLE:
        return tool_error(
            "The 'websockets' Python package is required but not installed. "
            "Install it with: pip install websockets"
        )

    endpoint = _resolve_cdp_endpoint()
    if not endpoint:
        return tool_error(
            "No CDP endpoint is available. Run '/browser connect' to attach "
            "to a running Chrome, Brave, Chromium, or Edge browser, or set "
            "'browser.cdp_url' in config.yaml. The Camofox backend is REST-only "
            "and does not expose CDP.",
            cdp_docs=CDP_DOCS_URL,
        )

    if not endpoint.startswith(("ws://", "wss://")):
        return tool_error(
            f"CDP endpoint is not a WebSocket URL: {endpoint!r}. "
            "Expected ws://... or wss://... — the /browser connect "
            "resolver should have rewritten this. Check that a Chromium-family "
            "browser is actually listening on the debug port."
        )

    call_params: Dict[str, Any] = params or {}
    if not isinstance(call_params, dict):
        return tool_error(
            f"'params' must be an object/dict, got {type(call_params).__name__}"
        )

    blocked = _browser_cdp_private_guard(
        task_id=effective_task_id,
        method=method,
        params=call_params,
    )
    if blocked:
        return blocked

    try:
        safe_timeout = float(timeout) if timeout else 30.0
    except (TypeError, ValueError):
        safe_timeout = 30.0
    safe_timeout = max(1.0, min(safe_timeout, 300.0))

    try:
        result = _run_async(
            _cdp_call(endpoint, method, call_params, target_id, safe_timeout)
        )
    except asyncio.TimeoutError as exc:
        return tool_error(
            f"CDP call timed out after {safe_timeout}s: {exc}",
            method=method,
        )
    except TimeoutError as exc:
        return tool_error(str(exc), method=method)
    except RuntimeError as exc:
        return tool_error(str(exc), method=method)
    except WebSocketException as exc:
        return tool_error(
            f"WebSocket error talking to CDP at {endpoint}: {exc}. The "
            "browser may have disconnected — try '/browser connect' again.",
            method=method,
        )
    except Exception as exc:  # pragma: no cover — unexpected
        logger.exception("browser_cdp unexpected error")
        return tool_error(
            f"Unexpected error: {type(exc).__name__}: {exc}",
            method=method,
        )

    payload: Dict[str, Any] = {
        "success": True,
        "method": method,
        "result": _redact_cdp_output(result),
    }
    if target_id:
        payload["target_id"] = target_id
    return json.dumps(payload, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


BROWSER_CDP_SCHEMA: Dict[str, Any] = {
    "name": "browser_cdp",
    "description": (
        "Send a raw Chrome DevTools Protocol (CDP) command. Escape hatch for "
        "browser operations not covered by browser_navigate, browser_click, "
        "browser_console, etc.\n\n"
        "**Requires a reachable CDP endpoint.** Available when the user has "
        "run '/browser connect' to attach to a running Chrome, Brave, Chromium, "
        "or Edge browser, or when 'browser.cdp_url' is set in config.yaml. "
        "Not currently wired up for cloud backends (Browserbase, Browser Use, "
        "Firecrawl) — those expose CDP per session but live-session routing is "
        "a follow-up. Camofox is REST-only and will never support CDP. If the "
        "tool is in your toolset at all, a CDP endpoint is already reachable.\n\n"
        f"**CDP method reference:** {CDP_DOCS_URL} — use web_extract on a "
        "method's URL (e.g. '/tot/Page/#method-handleJavaScriptDialog') "
        "to look up parameters and return shape.\n\n"
        "**Common patterns:**\n"
        "- List tabs: method='Target.getTargets', params={}\n"
        "- Handle a native JS dialog: method='Page.handleJavaScriptDialog', "
        "params={'accept': true, 'promptText': ''}, target_id=<tabId>\n"
        "- Get all cookies: method='Network.getAllCookies', params={}\n"
        "- Eval in a specific tab: method='Runtime.evaluate', "
        "params={'expression': '...', 'returnByValue': true}, "
        "target_id=<tabId>\n"
        "- Set viewport for a tab: method='Emulation.setDeviceMetricsOverride', "
        "params={'width': 1280, 'height': 720, 'deviceScaleFactor': 1, "
        "'mobile': false}, target_id=<tabId>\n\n"
        "**Usage rules:**\n"
        "- Browser-level methods (Target.*, Browser.*, Storage.*): omit "
        "target_id and frame_id.\n"
        "- Page-level methods (Page.*, Runtime.*, DOM.*, Emulation.*, "
        "Network.* scoped to a tab): pass target_id from Target.getTargets.\n"
        "- **Cross-origin iframe scope** (Runtime.evaluate inside an OOPIF, "
        "Page.* targeting a frame target, etc.): pass frame_id from the "
        "browser_snapshot frame_tree output. This routes through the CDP "
        "supervisor's live connection — the only reliable way on "
        "Browserbase where stateless CDP calls hit signed-URL expiry.\n"
        "- Each stateless call (without frame_id) is independent — sessions "
        "and event subscriptions do not persist between calls. For stateful "
        "workflows, prefer the dedicated browser tools or use frame_id "
        "routing."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "method": {
                "type": "string",
                "description": (
                    "CDP method name, e.g. 'Target.getTargets', "
                    "'Runtime.evaluate', 'Page.handleJavaScriptDialog'."
                ),
            },
            "params": {
                "type": "object",
                "description": (
                    "Method-specific parameters as a JSON object. Omit or "
                    "pass {} for methods that take no parameters."
                ),
                "properties": {},
                "additionalProperties": True,
            },
            "target_id": {
                "type": "string",
                "description": (
                    "Optional. Target/tab ID from Target.getTargets result "
                    "(each entry's 'targetId'). Use for page-level methods "
                    "at the top-level tab scope. Mutually exclusive with "
                    "frame_id."
                ),
            },
            "frame_id": {
                "type": "string",
                "description": (
                    "Optional. Out-of-process iframe (OOPIF) frame_id from "
                    "browser_snapshot.frame_tree.children[] where "
                    "is_oopif=true. When set, routes the call through the "
                    "CDP supervisor's live session for that iframe. "
                    "Essential for Runtime.evaluate inside cross-origin "
                    "iframes, especially on Browserbase where fresh "
                    "per-call CDP connections can't keep up with signed "
                    "URL rotation. For same-origin iframes, use parent "
                    "contentWindow/contentDocument from Runtime.evaluate "
                    "at the top-level page instead."
                ),
            },
            "timeout": {
                "type": "number",
                "description": (
                    "Timeout in seconds (default 30, max 300)."
                ),
                "default": 30,
            },
        },
        "required": ["method"],
    },
}


def _browser_cdp_check() -> bool:
    """Availability check for browser_cdp.

    The tool is only offered when the Python side can actually reach a CDP
    endpoint right now — meaning a static URL is set via ``/browser connect``
    (``BROWSER_CDP_URL``) or ``browser.cdp_url`` in ``config.yaml``.

    Backends that do *not* currently expose CDP to us — Camofox (REST-only),
    the default local agent-browser mode (Playwright hides its internal CDP
    port), and cloud providers whose per-session ``cdp_url`` is not yet
    surfaced — are gated out so the model doesn't see a tool that would
    reliably fail.  Cloud-provider CDP routing is a follow-up.

    Kept in a thin wrapper so callers can cheaply probe availability.
    """
    try:
        from tools.agent_tools.browser_tools.browser_tool import (
            _get_cdp_override,
            check_browser_requirements,
        )
    except ImportError as exc:  # pragma: no cover — defensive
        logger.debug("browser_cdp check: browser_tool import failed: %s", exc)
        return False
    if not check_browser_requirements():
        return False
    return bool(_get_cdp_override())

