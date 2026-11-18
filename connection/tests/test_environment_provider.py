"""Tests for environment references and temporary secret files."""

from __future__ import annotations

from pathlib import Path

import pytest

from connection.protocol.request import ProtocolError
from connection.semantic.environment_provider import (
    validate_environment_reference,
    write_secret_file,
)


def test_environment_reference_keeps_only_path_and_keys() -> None:
    assert validate_environment_reference(".env", ("TOKEN",)) == (".env", ("TOKEN",))


def test_secret_file_can_be_cleaned_up(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TMPDIR", str(tmp_path))
    secret = write_secret_file({"TOKEN": "value"})

    assert secret.path.is_file()
    assert secret.path.read_text(encoding="utf-8") == "TOKEN=value\n"
    secret.cleanup()
    assert not secret.path.exists()


def test_newline_in_secret_is_rejected() -> None:
    with pytest.raises(ProtocolError, match="newline"):
        write_secret_file({"TOKEN": "line\nbreak"})
