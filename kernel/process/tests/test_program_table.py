"""Starting a capability reads the table and runs the command written there."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from capability.catalog import build_table
from capability.model.model_provider.openai_chat_model.openai_chat_model_plugin import (
    capability_profile,
)
from kernel.command.process.clerk import KernelRuntime
from kernel.command.convention import UsageError
from kernel.process.declaration import ProcessDeclaration
from kernel.process.ledger import ProcessLedger
from kernel.process.process_creat.instances import (
    describe_instance,
    repo_root,
)
from kernel.process.profile import ProfileUnavailable, load_declaration
from kernel.process.reconcile import ProcessReconciler
from kernel.process.resource_record import ProcessResourceBook
from kernel.resource.lease import ResourceLeaseManager
from kernel.resource.pool import ResourcePool
from kernel.resource.resource_contract import kind_name


def test_the_model_card_accepts_runtime_changes() -> None:
    config = capability_profile(
        "model.openai_chat_model",
        (
            ("base_url", "https://api.deepseek.com"),
            ("model", "deepseek-flash"),
        ),
    )
    assert config.call_params["base_url"] == "https://api.deepseek.com"
    assert config.call_params["model"] == "deepseek-flash"
    assert config.api_key_env == "OPENAI_API_KEY"


def test_an_unknown_name_is_not_called_a_missing_profile() -> None:
    with pytest.raises(KeyError, match="Unknown capability instance 'model.missing'"):
        load_declaration("model.missing", ())
    assert not issubclass(KeyError, ProfileUnavailable)


def test_a_row_without_a_command_is_refused() -> None:
    definition = describe_instance(
        "tools.echo_node",
        catalog={"tools.echo_node": {"argv": [], "resources": [], "settings": {}, "changes": []}},
    )
    with pytest.raises(RuntimeError, match="This capability has no command: tools.echo_node"):
        definition.command()


def test_the_kernel_does_not_choose_the_program_language() -> None:
    root = repo_root()
    lookup = (root / "kernel" / "process" / "process_creat" / "instances.py").read_text(encoding="utf-8")
    starter = (root / "kernel" / "process" / "process_manager" / "capability_process.py").read_text(encoding="utf-8")
    assert "capability.program" not in lookup
    assert "capability.programs" not in lookup
    assert "subprocess" not in lookup
    assert "capability.program" not in starter
    assert "capability.programs" not in starter


def test_a_start_line_runs_the_table_command(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    clerk = KernelRuntime()
    try:
        with pytest.raises(UsageError, match="model use"):
            clerk.launch(
                [
                    "model.openai_chat_model",
                    "--change",
                    "base_url=https://api.deepseek.com",
                ]
            )
    finally:
        clerk.close()


def test_agent_loop_is_the_linope_command() -> None:
    table = build_table(repo_root() / "capability")
    row = table["agent_loop"]
    assert row["argv"] == ["python", "-m", "capability.agent_loop.linope"]
    assert row["resources"][0]["kind"] == "memory"
    assert row["resources"][0]["identity"]["scope"] == "chat"
    assert row["settings"]["model"] == "model.openai_chat_model"
    pi = table["agent_loop_pi"]
    assert pi["argv"] == ["node", "capability/agent_loop/pi/main.mjs"]
    assert pi["resources"][0]["kind"] == "memory"
    assert pi["settings"]["model"] == "model.openai_chat_model"


def test_file_tools_defer_scope_to_the_runtime_sandbox() -> None:
    table = build_table(repo_root() / "capability")
    row = table["tools.read"]
    sandbox = row["resources"][1]
    assert sandbox["kind"] == "sandbox"
    assert sandbox["identity"]["root"] == "host"
    assert sandbox["call_params"]["scope"] == "host"


def test_a_manifest_command_is_executed_unchanged(tmp_path: Path) -> None:
    root = tmp_path / "capability"
    package = root / "tools" / "echo_node"
    package.mkdir(parents=True)
    script = package / "echo.py"
    script.write_text(
        "import json, sys\n"
        "startup = json.loads(sys.stdin.readline())\n"
        "pid = int(startup['activation']['pid'])\n"
        "sys.stdout.write(json.dumps({'event': 'ready', 'pid': pid}) + '\\n')\n"
        "sys.stdout.flush()\n"
        "for line in sys.stdin:\n"
        "    if not line:\n"
        "        break\n",
        encoding="utf-8",
    )
    (package / "linope.json").write_text(
        json.dumps(
            {
                "name": "tools.echo_node",
                "command": [sys.executable, str(script)],
                "resources": [
                    {"kind": "network", "identity": {"channel": "ledger"}, "call_params": {}}
                ],
            }
        ),
        encoding="utf-8",
    )
    table = build_table(root)
    definition = describe_instance("tools.echo_node", catalog=table)
    assert definition.command() == (sys.executable, str(script))
    declaration = ProcessDeclaration.from_payload(
        {
            "capability": "tools.echo_node",
            "resources": table["tools.echo_node"]["resources"],
            "settings": {},
        }
    )
    book = ProcessResourceBook(ProcessLedger(tmp_path / "ledger.json"))
    process = ProcessReconciler(ResourcePool(ResourceLeaseManager()), book).start(
        declaration,
        definition=definition,
    )
    try:
        assert process.pid > 0
        assert list(process._child.args) == [sys.executable, str(script)]
    finally:
        process.stop()
