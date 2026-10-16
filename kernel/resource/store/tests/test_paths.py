"""Project files stay portable, and a user's secret path stays with that user."""

import json
from pathlib import Path

from kernel.resource.store.locator import (
    default_env_file,
    default_store_locator,
    env_file_problem,
    local_path,
    project_config_path,
    set_default_env_file,
    set_default_store_locator,
    user_config_path,
)


def _isolate(monkeypatch, tmp_path: Path) -> tuple[Path, Path]:
    project = tmp_path / "project" / ".linope" / "config.json"
    user = tmp_path / "user" / "config.json"
    monkeypatch.setattr("kernel.resource.store.locator.project_config_path", lambda: project)
    monkeypatch.setattr("kernel.resource.store.locator.user_config_path", lambda: user)
    monkeypatch.setattr("kernel.resource.store.locator.project_root", lambda: tmp_path / "project")
    return project, user


def test_relative_ledger_follows_the_project_root_not_the_working_directory(monkeypatch, tmp_path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    monkeypatch.setattr("kernel.resource.store.locator.project_root", lambda: project)
    assert local_path("file:.linope/resources.json") == project / ".linope" / "resources.json"


def test_an_env_path_is_user_config_and_absent_from_the_project(monkeypatch, tmp_path) -> None:
    project, user = _isolate(monkeypatch, tmp_path)
    secret = tmp_path / "secrets.env"
    secret.write_text("OPENAI_API_KEY=hidden\n", encoding="utf-8")
    assert set_default_env_file(secret) == str(secret.resolve())
    assert default_env_file() == str(secret.resolve())
    saved = json.loads(user.read_text(encoding="utf-8"))
    assert saved["env_file"] == str(secret.resolve())
    assert not project.exists()


def test_a_foreign_absolute_env_path_is_not_reused(monkeypatch, tmp_path) -> None:
    project, user = _isolate(monkeypatch, tmp_path)
    project.parent.mkdir(parents=True)
    project.write_text(
        json.dumps(
            {
                "env_file": "C:/missing-user/Linope/capability/.env",
                "resource_store": "file:.linope/agent-cluster.json",
            }
        ),
        encoding="utf-8",
    )
    assert default_env_file() == ""
    assert "重新选择" in env_file_problem()
    saved = json.loads(project.read_text(encoding="utf-8"))
    assert "env_file" not in saved
    assert saved["resource_store"] == "file:.linope/agent-cluster.json"
    assert "env_notice" in json.loads(user.read_text(encoding="utf-8"))


def test_an_in_project_absolute_store_becomes_relative(monkeypatch, tmp_path) -> None:
    project_dir = tmp_path / "project"
    ledger = project_dir / ".linope" / "agent-cluster.json"
    ledger.parent.mkdir(parents=True)
    ledger.write_text("{}", encoding="utf-8")
    project, _user = _isolate(monkeypatch, tmp_path)
    project.write_text(
        json.dumps({"resource_store": "file:" + str(ledger)}),
        encoding="utf-8",
    )
    assert default_store_locator() == "file:.linope/agent-cluster.json"
    assert set_default_store_locator("file:.linope/resources.json") == "file:.linope/resources.json"


def test_commands_use_the_recorded_user_file_without_repeating_it(monkeypatch, tmp_path) -> None:
    _isolate(monkeypatch, tmp_path)
    secret = tmp_path / "b.env"
    secret.write_text("OPENAI_API_KEY=from-b\n", encoding="utf-8")
    set_default_env_file(secret)
    monkeypatch.delenv("LINOPE_ENV_FILE", raising=False)
    assert default_env_file() == str(secret.resolve())
    assert user_config_path() != project_config_path()
