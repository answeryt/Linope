"""Linux-style commands reject markers and keep options explicit."""

import pytest

from kernel.command.convention import UsageError, parse
from kernel.command.parser import parse_changes
from kernel.command.start import parse_start


def test_process_start_reads_changes_count_and_env() -> None:
    capability, changes, ping, _store, replica_count, env_file, env_keys = parse_start(
        [
            "model.openai_chat_model",
            "--ping",
            "--change",
            "model=gpt-4o",
            "--change",
            "temperature=0.2",
        ]
    )
    assert capability == "model.openai_chat_model"
    assert ping is True
    assert changes == (("model", "gpt-4o"), ("temperature", "0.2"))
    assert replica_count is None
    assert env_file == ""
    assert env_keys == ()

    _capability, changes, _ping, _store, replica_count, _env_file, _env_keys = parse_start(
        ["model.openai_chat_model", "--change", "model=10", "--count", "10"]
    )
    assert changes == (("model", "10"),)
    assert replica_count == 10

    capability, _changes, ping, _store, replica_count, env_file, env_keys = parse_start(
        ["tools.bash", "--env-file", "capability/.env", "--env", "ANTHROPIC_API_KEY", "--ping"]
    )
    assert capability == "tools.bash"
    assert ping is True
    assert replica_count is None
    assert env_file == "capability/.env"
    assert env_keys == ("ANTHROPIC_API_KEY",)


def test_process_start_rejects_a_secret_and_a_zero_count() -> None:
    with pytest.raises(UsageError, match="值放在环境文件里"):
        parse_start(["tools.bash", "--env-file", "capability/.env", "--env", "TOKEN=secret"])
    with pytest.raises(UsageError, match="份数至少为 1"):
        parse_start(["model.openai_chat_model", "--count", "0"])


def test_change_options_need_a_name() -> None:
    with pytest.raises(UsageError, match="主题=值"):
        parse_changes(["=gpt-4o"])


def test_service_create_records_an_empty_service(tmp_path) -> None:
    from kernel.command import main
    from kernel.process.ledger import FileResourceStore

    path = tmp_path / "resources.json"
    locator = f"file:{path}"
    assert main(["service", "create", "coder", "--resource-store", locator, "--json"]) == 0
    store = FileResourceStore(path)
    try:
        assert store.service_record("coder") == {"name": "coder"}
        assert store.service_members("coder") == ()
    finally:
        store.close()


def test_unknown_object_exits_with_usage(capsys) -> None:
    from kernel.command import main

    assert main(["start", "tools.bash"]) == 2
    assert "service" in capsys.readouterr().err


def test_parse_rejects_an_unknown_option() -> None:
    with pytest.raises(UsageError, match="不认识的选项"):
        parse(["--cap", "tools.bash"], flags={}, usage="用法")
