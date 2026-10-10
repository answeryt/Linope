"""The service command only parses. It does not know a kind by name."""

from __future__ import annotations

import pytest

from kernel.command.service import list_kinds, parse_service_start, run


def test_service_start_splits_kind_members_changes_and_count() -> None:
    spec, options = parse_service_start(
        [
            "agent",
            "model.openai_chat_model",
            "tools.bash",
            "temperature",
            "change",
            "-",
            "0.2",
            "3",
            "--ping",
        ]
    )
    assert spec.kind == "agent"
    assert spec.members == ("model.openai_chat_model", "tools.bash")
    assert spec.changes == (("temperature", "0.2"),)
    assert spec.replica_count == 3
    assert options[2] is True


def test_an_unknown_kind_is_reported_with_the_known_names(capsys) -> None:
    assert run(["start", "no-such-kind"]) == 1
    err = capsys.readouterr().err
    assert "未知服务种类" in err
    assert "agent" in err


def test_services_lists_the_registered_kinds(capsys) -> None:
    assert list_kinds([]) == 0
    shown = capsys.readouterr().out.split()
    assert shown == ["agent", "capability", "mcp", "model"]


def test_services_takes_no_arguments() -> None:
    with pytest.raises(SystemExit):
        list_kinds(["extra"])


def test_service_without_start_is_refused() -> None:
    with pytest.raises(SystemExit):
        run([])
