"""Creating a file and pointing process start at it."""

from pathlib import Path

from kernel.command.dispatch import main
from kernel.process.declaration import ProcessDeclaration, ResourceClaim
from kernel.process.process_creat.instances import CapabilityDefinition
from kernel.process.reconcile import ProcessReconciler
from kernel.process.resource_record import ProcessResourceBook
from kernel.resource.lease import ResourceLeaseManager
from kernel.resource.pool import ResourcePool


def test_create_writes_one_line_and_hides_the_value(tmp_path: Path, capsys, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["create", ".env", "--", "OPENAI_API_KEY=sk-test"]) == 0
    text = (tmp_path / ".env").read_text(encoding="utf-8")
    assert "OPENAI_API_KEY=sk-test" in text
    assert "sk-test" not in capsys.readouterr().out
    assert main(["create", ".env", "--", "OTHER=1"]) == 0
    text = (tmp_path / ".env").read_text(encoding="utf-8")
    assert "OPENAI_API_KEY=sk-test" in text
    assert "OTHER=1" in text


def test_load_env_names_an_existing_file(tmp_path: Path, capsys, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    env = tmp_path / ".env"
    env.write_text("OPENAI_API_KEY=sk-test\n", encoding="utf-8")
    assert main(["load", "env", ".env"]) == 0
    assert capsys.readouterr().out.strip() == f"env_file={env.resolve()}"
    assert main(["load", "message", "--", "你好"]) == 2


def test_started_process_uses_that_env_file(tmp_path: Path) -> None:
    plugin = tmp_path / "card.py"
    plugin.write_text('"api_key_env": "OPENAI_API_KEY"\n', encoding="utf-8")
    env = tmp_path / ".env"
    env.write_text("OPENAI_API_KEY=sk-test\n", encoding="utf-8")
    book = ProcessResourceBook()
    process = ProcessReconciler(ResourcePool(ResourceLeaseManager()), book).start(
        ProcessDeclaration(
            capability="sample.capability",
            resources=(ResourceClaim(kind="network", identity={"channel": "ledger"}),),
        ),
        definition=CapabilityDefinition(
            instance_id="sample.capability",
            module_paths=(str(plugin),),
        ),
        env_file=str(env),
    )
    shell = process.activation.environment
    assert shell is not None
    assert Path(shell.env_file) == env.resolve()
    assert shell.env_file_keys == ("OPENAI_API_KEY",)


def test_the_capability_program_gets_only_its_own_secret(tmp_path: Path) -> None:
    plugin = tmp_path / "card.py"
    plugin.write_text('"api_key_env": "OPENAI_API_KEY"\n', encoding="utf-8")
    env = tmp_path / ".env"
    env.write_text("OPENAI_API_KEY=sk-test\nOTHER_SECRET=nope\n", encoding="utf-8")
    process = ProcessReconciler(ResourcePool(ResourceLeaseManager()), ProcessResourceBook()).start(
        ProcessDeclaration(
            capability="sample.capability",
            resources=(ResourceClaim(kind="network", identity={"channel": "ledger"}),),
        ),
        definition=CapabilityDefinition(
            instance_id="sample.capability",
            module_paths=(str(plugin),),
        ),
        env_file=str(env),
    )
    payload = process._child_payload()
    copied = Path(payload["environment"]["env_file"])
    text = copied.read_text(encoding="utf-8")
    assert "OPENAI_API_KEY=sk-test" in text
    assert "OTHER_SECRET" not in text
    assert copied != env.resolve()
    door = payload["room"]["identity"]
    assert door["secret_names"] == ["OPENAI_API_KEY"]
    process.stop()
    assert not copied.exists()
