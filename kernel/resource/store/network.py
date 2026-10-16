"""Local and private network choices for the resource server.

``local`` keeps every link on the loopback interface. ``private`` is an
explicit choice for an intranet or VPN: links use one reachable address, and
the ledger must be a database the other machines can share.
"""

from __future__ import annotations

import ipaddress
import os
import threading
from dataclasses import dataclass
from urllib.parse import urlsplit

from kernel.resource.store.locator import normalize_locator, read_project_config, write_project_config

LOCAL = "local"
PRIVATE = "private"
_MODES = frozenset({LOCAL, PRIVATE})
_LOOPBACK = frozenset({"127.0.0.1", "localhost", "::1"})
_UNSPECIFIED = frozenset({"0.0.0.0", "::"})
_lock = threading.Lock()
_trusted: set[str] = set()


@dataclass(frozen=True)
class ServePlan:
    """How one resource server should listen and which address links use."""

    mode: str
    bind_host: str
    port: int
    public_base: str
    locator: str
    allow: tuple[str, ...]


def configured_mode() -> str:
    """The mode saved for this project, or ``local`` when nobody chose one."""
    raw = os.environ.get("LINOPE_NETWORK_MODE", "").strip().lower()
    if raw:
        return _mode(raw)
    network = _saved_network()
    return _mode(str(network.get("mode") or LOCAL))


def configured_public_base() -> str:
    """The saved link origin. Empty in the default local setup."""
    raw = os.environ.get("LINOPE_PUBLIC_BASE_URL", "").strip()
    if raw:
        return raw.rstrip("/")
    network = _saved_network()
    return str(network.get("public_base_url") or "").strip().rstrip("/")


def save_network(mode: str, public_base: str = "") -> None:
    """Remember one mode. A secret does not belong in this record."""
    payload = read_project_config()
    payload["network"] = {
        "mode": _mode(mode),
        "public_base_url": public_base.rstrip("/"),
    }
    write_project_config(payload)


def plan_serve(
    store: str,
    *,
    mode: str = LOCAL,
    host: str = "127.0.0.1",
    port: int = 0,
    public_base_url: str = "",
    allow: tuple[str, ...] = (),
) -> ServePlan:
    """Check one serve command before a socket is opened."""
    chosen = _mode(mode)
    locator = normalize_locator(store)
    bind_host = host.strip() or "127.0.0.1"
    if chosen == LOCAL:
        if bind_host not in _LOOPBACK:
            raise ValueError("本机模式只能监听 127.0.0.1、localhost 或 ::1")
        if public_base_url and not _loopback_url(public_base_url):
            raise ValueError("本机模式的链接地址必须是回环地址")
        if _shared_file(locator):
            raise ValueError("本机模式不要把账本放在网络共享盘上")
        return ServePlan(LOCAL, bind_host, port, "", locator, tuple(allow))
    if port <= 0:
        raise ValueError("私网模式要写固定端口，重启后链接才不会变")
    public = (public_base_url or _derived_public(bind_host, port)).rstrip("/")
    _require_private_url(public, port)
    if _file_ledger(locator):
        raise ValueError("私网模式要用数据库账本，不能用本地 JSON 或网络共享盘")
    if "://" not in locator:
        raise ValueError("私网模式要用数据库账本，例如 sqlite:/// 或 postgresql+psycopg://")
    if bind_host not in _UNSPECIFIED | _LOOPBACK and _is_ip(bind_host) and _is_ip(_host_of(public)):
        if bind_host != _host_of(public):
            raise ValueError("监听地址和公开地址不是同一台机器")
    return ServePlan(PRIVATE, bind_host, port, public, locator, tuple(allow))


def trust_host(host: str) -> None:
    """Let this process accept links for one configured private host."""
    cleaned = host.strip().lower()
    if not cleaned:
        return
    with _lock:
        _trusted.add(cleaned)


def untrust_host(host: str) -> None:
    with _lock:
        _trusted.discard(host.strip().lower())


def host_allowed(host: str | None) -> bool:
    """Loopback is always allowed. A private host must have been configured."""
    if not host:
        return False
    lowered = host.lower()
    if lowered in _LOOPBACK:
        return True
    with _lock:
        return lowered in _trusted


def channel_endpoints() -> tuple[str, str]:
    """Return ``(bind_host, advertise_host)`` for a peer channel.

    Local mode never leaves the machine. Private mode binds widely enough to
    be reached and publishes the configured host, never ``0.0.0.0``.
    """
    if configured_mode() != PRIVATE:
        return "127.0.0.1", "127.0.0.1"
    base = configured_public_base()
    if not base:
        raise RuntimeError("私网模式需要先设置公开地址，通道才能告诉其他机器自己在哪里")
    host = _host_of(base)
    _require_private_host(host)
    return "0.0.0.0", host


def nats_url(url: str) -> str:
    """Keep the local default, and refuse a loopback broker once private mode is on."""
    chosen = url.strip() or "nats://127.0.0.1:4222"
    if configured_mode() == PRIVATE and _loopback_url(chosen):
        raise RuntimeError("私网模式的 NATS 地址不能是本机回环，请写成 nats://<私网地址>:4222")
    return chosen


def access_token() -> str:
    """Optional bearer token. It stays in the environment, never in a link."""
    return os.environ.get("LINOPE_RESOURCE_TOKEN", "").strip()


def auth_headers() -> dict[str, str]:
    token = access_token()
    if not token:
        return {}
    return {"Authorization": f"Bearer {token}"}


def http_origin(value: str) -> str:
    """Scheme and authority from a link a person already holds."""
    parts = urlsplit(value.strip())
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        raise ValueError("链接必须是带主机的 HTTP 地址")
    if parts.query or parts.fragment:
        raise ValueError("链接不能带查询或片段")
    return f"{parts.scheme}://{parts.netloc}"


def _saved_network() -> dict:
    raw = read_project_config().get("network") or {}
    return raw if isinstance(raw, dict) else {}


def _mode(value: str) -> str:
    chosen = value.strip().lower() or LOCAL
    if chosen not in _MODES:
        raise ValueError("运行模式只能是 local 或 private")
    return chosen


def _derived_public(host: str, port: int) -> str:
    if host in _UNSPECIFIED or host in _LOOPBACK:
        raise ValueError("私网模式要写 --public-base-url，例如 http://10.0.0.10:49152")
    return f"http://{host}:{port}"


def _require_private_url(value: str, expected_port: int) -> None:
    parts = urlsplit(value)
    if parts.scheme not in {"http", "https"} or not parts.hostname:
        raise ValueError("公开地址要写成 http://<私网主机>:<端口>")
    if parts.query or parts.fragment or parts.path not in {"", "/"}:
        raise ValueError("公开地址只写到主机和端口")
    if parts.port is None:
        raise ValueError("公开地址要带端口")
    if parts.port != expected_port:
        raise ValueError("公开地址的端口要和监听端口相同")
    _require_private_host(parts.hostname)


def _require_private_host(host: str) -> None:
    if host.lower() in _LOOPBACK or host in _UNSPECIFIED:
        raise ValueError("私网公开地址不能是 localhost 或 0.0.0.0")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return
    if address.is_loopback or address.is_unspecified or address.is_multicast:
        raise ValueError("私网公开地址不能是回环、未指定或组播地址")
    if address.is_private or address.is_link_local:
        return
    raise ValueError("私网公开地址要是内网 IP 或内部域名，不要写成公网 IP")


def _loopback_url(value: str) -> bool:
    host = _host_of(value)
    if host.lower() in _LOOPBACK:
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _host_of(value: str) -> str:
    return str(urlsplit(value).hostname or "")


def _is_ip(value: str) -> bool:
    try:
        ipaddress.ip_address(value)
    except ValueError:
        return False
    return True


def _file_ledger(locator: str) -> bool:
    return locator.startswith(("file:", "local:", "memory:")) or _shared_file(locator)


def _shared_file(locator: str) -> bool:
    raw = locator
    if raw.startswith(("file:", "local:")):
        raw = raw.split(":", 1)[1]
    return raw.startswith("\\\\") or raw.startswith("//")
