"""Profile boundary: missing or failing profiles never reach the reconciler."""

import pytest

from kernel.process.declaration import ProcessDeclaration, ResourceClaim
from kernel.process.process_creat.instances import describe_instance, discover_instances
from kernel.command import main, parse_start
from kernel.process.profile import ProfileUnavailable, declaration_from_modules, load_declaration
from kernel.process.reconcile import ProcessReconciler
from kernel.resource.definition import ResourceKind
from kernel.resource.pool import ResourcePool
from kernel.process.ledger import FileResourceStore


class _NoProfile:
    pass


class _Boom:
    @staticmethod
    def capability_profile(capability_id, changes):
        raise RuntimeError("card missing")


class _Recording:
    seen = None

    @classmethod
    def capability_profile(cls, capability_id, changes):
        cls.seen = (capability_id, changes)
        return ProcessDeclaration(
            capability=capability_id,
            resources=(
                ResourceClaim(kind=ResourceKind.CONTEXT, identity={"id": "from-function"}),
            ),
        )


def test_change_clauses_are_forwarded_unchanged() -> None:
    changes = (("model", "gpt-4o"), ("temperature", "0.2"))
    declaration = declaration_from_modules([_Recording()], "model.example", changes)
    assert _Recording.seen == ("model.example", changes)
    assert declaration.resources[0].identity == {"id": "from-function"}


def test_missing_profile_stops_before_reconciler(monkeypatch) -> None:
    called = False

    def fail(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("reconciler must not run")

    monkeypatch.setattr(
        "kernel.process.reconcile.ProcessReconciler",
        fail,
    )
    with pytest.raises(ProfileUnavailable):
        declaration_from_modules([_NoProfile()], "tools.bash", ())

    def no_profile(instance_id: str):
        from kernel.process.process_creat.instances import describe_instance

        return [_NoProfile()], describe_instance(instance_id)

    monkeypatch.setattr(
        "kernel.process.process_creat.instances.load_capability",
        no_profile,
    )
    assert main(["process", "start", "tools.bash"]) == 1
    assert called is False


def test_profile_error_stops_at_the_boundary() -> None:
    with pytest.raises(ProfileUnavailable) as raised:
        declaration_from_modules([_Boom()], "model.openai_chat_model", ())
    assert isinstance(raised.value.__cause__, RuntimeError)


def test_load_declaration_scans_the_catalog_once(monkeypatch) -> None:
    calls = 0
    real = discover_instances

    def counted(root=None):
        nonlocal calls
        calls += 1
        return real(root)

    monkeypatch.setattr(
        "kernel.process.process_creat.instances.discover_instances",
        counted,
    )
    declaration, definition = load_declaration("model.openai_chat_model", ())
    assert calls == 1
    assert declaration.capability == "model.openai_chat_model"
    assert definition.instance_id == "model.openai_chat_model"
    assert definition.module_paths


def test_reconciler_reuses_the_definition(tmp_path, monkeypatch) -> None:
    definition = describe_instance("context.sliding_window")

    def scanned_again(*_args, **_kwargs):
        raise AssertionError("catalog scanned again")

    monkeypatch.setattr("kernel.process.reconcile.describe_instance", scanned_again)
    store = FileResourceStore(tmp_path / "resources.json")
    declaration = ProcessDeclaration(
        capability="context.sliding_window",
        resources=(
            ResourceClaim(kind=ResourceKind.CONTEXT, identity={"window": "default"}),
        ),
    )
    process = ProcessReconciler(ResourcePool(store)).start(
        declaration,
        definition=definition,
    )
    try:
        assert process.send({"operation": "ping"})["event"] == "pong"
    finally:
        process.stop()
        store.close()


def test_parse_start_keeps_change_clauses() -> None:
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


def test_parse_start_takes_a_count_and_leaves_change_values() -> None:
    from kernel.command.parser import UsageError

    _capability, changes, _ping, _store, replica_count, _env_file, _env_keys = parse_start(
        ["model.openai_chat_model", "--change", "model=10", "--count", "10"]
    )
    assert changes == (("model", "10"),)
    assert replica_count == 10

    _capability, changes, _ping, _store, replica_count, _env_file, _env_keys = parse_start(
        ["model.openai_chat_model", "--change", "model=10"]
    )
    assert changes == (("model", "10"),)
    assert replica_count is None


def test_parse_start_selects_keys_from_an_env_file() -> None:
    capability, _changes, ping, _store, replica_count, env_file, env_keys = parse_start(
        ["tools.bash", "--env-file", "capability/.env", "--env", "ANTHROPIC_API_KEY", "--ping"]
    )
    assert capability == "tools.bash"
    assert ping is True
    assert replica_count is None
    assert env_file == "capability/.env"
    assert env_keys == ("ANTHROPIC_API_KEY",)


def test_parse_start_rejects_an_env_value_on_the_command() -> None:
    from kernel.command.parser import UsageError

    with pytest.raises(UsageError, match="值放在环境文件里"):
        parse_start(["tools.bash", "--env-file", "capability/.env", "--env", "TOKEN=secret"])


def test_parse_start_rejects_a_count_below_one() -> None:
    from kernel.command.parser import UsageError

    with pytest.raises(UsageError, match="份数至少为 1"):
        parse_start(["model.openai_chat_model", "--count", "0"])
