"""Command checks for room, thread show/idle, env files, and start knobs."""

from __future__ import annotations

import json
import os
from pathlib import Path

from kernel.command.env import run as env_command
from kernel.command.room import run as room_command
from kernel.command.start import run as start_command
from kernel.command.thread import run as thread_command
from kernel.environment import HostExecutionPolicy, KernelEnvironment, ProcessEnvironment
from kernel.process.declaration import ProcessDeclaration, ResourceClaim
from kernel.process.process_creat.instances import describe_instance
from kernel.process.profile import load_declaration
from kernel.process.reconcile import ProcessReconciler
from kernel.process.ledger import FileResourceStore
from kernel.process.process_manager.liveness import process_identity
from kernel.resource.store.locator import set_default_env_file
from kernel.resource.definition import ResourceKind
from kernel.resource.pool import ResourcePool


CAPABILITY = "model.openai_chat_model"


class _CapturedProcess:
    def __init__(self, activation, resource_pool=None) -> None:
        del resource_pool
        self.activation = activation
        self.pid = os.getpid()
        self.is_alive = False

    def start(self) -> dict:
        return {}

    def stop(self) -> None:
        return None


def _isolate_config(monkeypatch, tmp_path: Path) -> Path:
    config = tmp_path / "project" / ".linope" / "config.json"
    monkeypatch.setattr(
        "kernel.resource.store.locator.project_config_path",
        lambda: config,
    )
    return config


def _running(store: FileResourceStore, process_id: str, capability: str) -> None:
    store.register_process(process_id, capability, None, "starting")
    store.mark_running(
        process_id,
        os.getpid(),
        process_identity(os.getpid()),
        {"sync_thread_safe": True, "is_async": False},
    )


def test_room_lists_live_processes_and_hides_secret_values(tmp_path, capsys) -> None:
    path = tmp_path / "resources.json"
    store = FileResourceStore(path)
    definition = describe_instance("tools.bash")
    shell = ProcessEnvironment(
        process_id="p1",
        capability_id=definition.instance_id,
        cwd=str(tmp_path),
        env={"LINOPE_VISIBLE": "shown-name-only"},
    )
    room = KernelEnvironment.build(
        shell=shell,
        policy=HostExecutionPolicy(max_runtime_seconds=9),
        max_concurrent_tasks=2,
        max_sync_workers=3,
        channel_name="ledger",
        module_paths=definition.module_paths,
    )
    payload = {
        "process_id": "p1",
        "room": room.payload(),
    }
    payload["room"]["shell"]["env"]["LINOPE_SECRET"] = "hidden-room-secret"
    _running(store, "p1", "tools.bash")
    _running(store, "p2", "tools.write")
    store.update_process("p2", status="failed", exit_code=1)
    store.set_activation("p1", payload)
    store.close()
    locator = f"file:{path}"

    assert room_command(["--resource-store", locator]) == 0
    listed = capsys.readouterr().out
    assert "p1 tools.bash" in listed
    assert "p2" not in listed

    assert room_command(["p1", "--resource-store", locator]) == 0
    shown = capsys.readouterr().out
    assert f"工作目录: {tmp_path.resolve()}" in shown
    assert "LINOPE_SECRET" in shown
    assert "hidden-room-secret" not in shown
    assert "shown-name-only" not in shown
    assert "墙钟: 9" in shown
    assert room_command(["missing", "--resource-store", locator]) == 1


def test_start_writes_cwd_and_runtime_into_the_room(tmp_path, monkeypatch) -> None:
    seen: list = []

    class Remember(_CapturedProcess):
        def __init__(self, activation, resource_pool=None) -> None:
            super().__init__(activation, resource_pool)
            seen.append(activation)

    monkeypatch.setattr("kernel.process.reconcile.CapabilityProcess", Remember)
    work = tmp_path / "work"
    work.mkdir()
    code = start_command(
        [
            "context.sliding_window",
            "--cwd",
            str(work),
            "--max-runtime-seconds",
            "15",
            "--resource-store",
            f"file:{tmp_path / 'resources.json'}",
        ]
    )
    assert code == 0
    payload = seen[0].payload()
    assert payload["room"]["shell"]["cwd"] == str(work.resolve())
    assert payload["room"]["policy"]["max_runtime_seconds"] == 15
    assert payload["room"]["lifecycle"]["max_runtime_seconds"] == 15
    assert payload["host_policy"]["max_runtime_seconds"] == 15


def test_thread_show_prints_mailbox_counts(tmp_path, capsys) -> None:
    path = tmp_path / "resources.json"
    store = FileResourceStore(path)
    _running(store, "p1", CAPABILITY)
    store.set_worker_ceiling("p1", 4)
    store.set_inflight_ceiling("p1", 6)
    store.submit_request("p1", {"operation": "ping"})
    store.close()
    locator = f"file:{path}"
    assert thread_command(["show", CAPABILITY, "--resource-store", locator]) == 0
    shown = capsys.readouterr().out
    assert "p1 pending=1 claimed=0 worker_ceiling=4 inflight_ceiling=6" in shown


def test_thread_idle_stops_only_an_empty_process(tmp_path, capsys) -> None:
    path = tmp_path / "resources.json"
    store = FileResourceStore(path)
    _running(store, "p1", CAPABILITY)
    _running(store, "p2", CAPABILITY)
    store.submit_request("p1", {"operation": "ping"})
    store.close()
    locator = f"file:{path}"
    assert thread_command(["idle", CAPABILITY, "--resource-store", locator]) == 0
    assert "p2" in capsys.readouterr().out
    again = FileResourceStore(path)
    try:
        assert again.get_process("p1").get("desired") != "stop"
        assert again.get_process("p2")["desired"] == "stop"
    finally:
        again.close()


def test_env_init_creates_an_empty_file_and_does_not_overwrite(
    tmp_path, monkeypatch, capsys
) -> None:
    _isolate_config(monkeypatch, tmp_path)
    secret = tmp_path / "outside" / "linope.env"
    assert env_command(["init", str(secret)]) == 0
    assert secret.read_text(encoding="utf-8") == ""
    capsys.readouterr()
    secret.write_text("ANTHROPIC_API_KEY=keep-me\n", encoding="utf-8")
    assert env_command(["init", str(secret)]) == 0
    assert secret.read_text(encoding="utf-8") == "ANTHROPIC_API_KEY=keep-me\n"
    noticed = capsys.readouterr().out
    assert "未覆盖" in noticed
    assert "keep-me" not in noticed


def test_env_use_records_a_path_and_models_take_only_their_key(
    tmp_path, monkeypatch
) -> None:
    config = _isolate_config(monkeypatch, tmp_path)
    secret = tmp_path / "elsewhere.env"
    secret.write_text(
        "ANTHROPIC_API_KEY=secret-value\nOPENAI_API_KEY=other-secret\n",
        encoding="utf-8",
    )
    assert env_command(["use", str(secret)]) == 0
    saved = json.loads(config.read_text(encoding="utf-8"))
    assert saved["env_file"] == str(secret.resolve())
    assert secret.read_text(encoding="utf-8").startswith("ANTHROPIC_API_KEY=secret-value")

    monkeypatch.setattr("kernel.process.reconcile.CapabilityProcess", _CapturedProcess)
    declaration, definition = load_declaration("model.anthropic_model", ())
    store = FileResourceStore(tmp_path / "resources.json")
    process = ProcessReconciler(ResourcePool(store)).start(
        declaration,
        definition=definition,
    )
    payload = process.activation.payload()
    store.close()
    blob = json.dumps(payload)
    shell = payload["environment"]
    assert shell["env_file"] == str(secret.resolve())
    assert shell["env_file_keys"] == ["ANTHROPIC_API_KEY"]
    assert "OPENAI_API_KEY" not in shell["env_file_keys"]
    assert "secret-value" not in blob
    assert "other-secret" not in blob

    plain = ProcessDeclaration(
        capability="context.sliding_window",
        resources=(
            ResourceClaim(
                kind=ResourceKind.CONTEXT,
                identity={"window": "default"},
            ),
        ),
    )
    other = FileResourceStore(tmp_path / "other.json")
    skipped = ProcessReconciler(ResourcePool(other)).start(
        plain,
        definition=describe_instance("context.sliding_window"),
    )
    skipped_shell = skipped.activation.payload()["environment"]
    other.close()
    assert skipped_shell["env_file"] == ""
    assert skipped_shell["env_file_keys"] == []


def test_explicit_env_file_still_overrides_the_recorded_path(tmp_path, monkeypatch) -> None:
    _isolate_config(monkeypatch, tmp_path)
    recorded = tmp_path / "recorded.env"
    recorded.write_text("ANTHROPIC_API_KEY=from-recorded\n", encoding="utf-8")
    chosen = tmp_path / "chosen.env"
    chosen.write_text("OPENAI_API_KEY=from-chosen\n", encoding="utf-8")
    set_default_env_file(recorded)
    monkeypatch.setattr("kernel.process.reconcile.CapabilityProcess", _CapturedProcess)
    declaration, definition = load_declaration("model.anthropic_model", ())
    store = FileResourceStore(tmp_path / "resources.json")
    process = ProcessReconciler(ResourcePool(store)).start(
        declaration,
        definition=definition,
        env_file=str(chosen),
        env_file_keys=("OPENAI_API_KEY",),
    )
    shell = process.activation.payload()["environment"]
    store.close()
    assert shell["env_file"] == str(chosen.resolve())
    assert shell["env_file_keys"] == ["OPENAI_API_KEY"]
    assert "from-chosen" not in json.dumps(shell)
