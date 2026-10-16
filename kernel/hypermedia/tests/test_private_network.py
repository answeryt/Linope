"""Private mode is explicit. Local mode stays on the loopback interface."""

from __future__ import annotations

import pytest

from kernel.hypermedia.uri import parse_resource_uri
from kernel.resource.store.network import (
    channel_endpoints,
    nats_url,
    plan_serve,
    trust_host,
    untrust_host,
)


def test_local_mode_rejects_a_lan_bind_and_a_public_address() -> None:
    with pytest.raises(ValueError, match="本机模式"):
        plan_serve("file:resources.json", mode="local", host="10.0.0.10", port=0)
    with pytest.raises(ValueError, match="回环"):
        plan_serve(
            "file:resources.json",
            mode="local",
            host="127.0.0.1",
            port=9,
            public_base_url="http://10.0.0.10:9",
        )


def test_private_mode_rejects_loopback_files_and_random_ports() -> None:
    with pytest.raises(ValueError, match="固定端口"):
        plan_serve(
            "sqlite:///ledger.db",
            mode="private",
            host="10.0.0.10",
            port=0,
            public_base_url="http://10.0.0.10:49152",
        )
    with pytest.raises(ValueError, match="不能是 localhost"):
        plan_serve(
            "sqlite:///ledger.db",
            mode="private",
            host="10.0.0.10",
            port=49152,
            public_base_url="http://127.0.0.1:49152",
        )
    with pytest.raises(ValueError, match="公网"):
        plan_serve(
            "sqlite:///ledger.db",
            mode="private",
            host="0.0.0.0",
            port=49152,
            public_base_url="http://8.8.8.8:49152",
        )
    with pytest.raises(ValueError, match="数据库"):
        plan_serve(
            "file:.linope/resources.json",
            mode="private",
            host="10.0.0.10",
            port=49152,
            public_base_url="http://10.0.0.10:49152",
        )
    with pytest.raises(ValueError, match="网络共享盘"):
        plan_serve(r"file:\\server\share\ledger.json", mode="local", host="127.0.0.1", port=0)


def test_private_mode_accepts_an_internal_name_and_a_lan_address() -> None:
    named = plan_serve(
        "sqlite:///ledger.db",
        mode="private",
        host="0.0.0.0",
        port=49152,
        public_base_url="http://linope.internal:49152",
    )
    assert named.public_base == "http://linope.internal:49152"
    lan = plan_serve(
        "sqlite:///ledger.db",
        mode="private",
        host="10.0.0.10",
        port=49152,
        public_base_url="http://10.0.0.10:49152",
    )
    assert lan.bind_host == "10.0.0.10"
    assert lan.mode == "private"


def test_links_stay_on_loopback_until_a_private_host_is_configured() -> None:
    assert parse_resource_uri("http://127.0.0.1:9/resources/ab") == "ab"
    with pytest.raises(ValueError):
        parse_resource_uri("http://10.0.0.10:9/resources/ab")
    trust_host("10.0.0.10")
    try:
        assert parse_resource_uri("http://10.0.0.10:9/resources/ab") == "ab"
    finally:
        untrust_host("10.0.0.10")


def test_private_channels_advertise_the_configured_host_not_all_interfaces(monkeypatch) -> None:
    monkeypatch.setenv("LINOPE_NETWORK_MODE", "private")
    monkeypatch.setenv("LINOPE_PUBLIC_BASE_URL", "http://10.0.0.10:49152")
    assert channel_endpoints() == ("0.0.0.0", "10.0.0.10")
    with pytest.raises(RuntimeError, match="NATS"):
        nats_url("")
    assert nats_url("nats://10.0.0.10:4222") == "nats://10.0.0.10:4222"


def test_local_channels_remain_on_loopback(monkeypatch) -> None:
    monkeypatch.delenv("LINOPE_NETWORK_MODE", raising=False)
    monkeypatch.delenv("LINOPE_PUBLIC_BASE_URL", raising=False)
    assert channel_endpoints() == ("127.0.0.1", "127.0.0.1")
    assert nats_url("") == "nats://127.0.0.1:4222"
