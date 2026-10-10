import json
import os

from kernel.environment import HostExecutionPolicy, KernelEnvironment, ProcessEnvironment
from kernel.process.declaration import ProcessDeclaration, ResourceClaim
from kernel.process.process_creat.activation import ProcessActivation
from kernel.process.process_creat.instances import CapabilityDefinition, describe_instance
from kernel.process.reconcile import ProcessReconciler
from kernel.process.ledger import FileResourceStore
from kernel.resource.definition import ResourceKind
from kernel.resource.pool import ResourcePool


def test_environment_is_serializable_and_applied_in_child(tmp_path) -> None:
    definition = describe_instance("context.sliding_window")
    store = FileResourceStore(tmp_path / "resources.json")
    environment = ProcessEnvironment(
        process_id="environment-process",
        capability_id=definition.instance_id,
        cwd=str(tmp_path),
        env={"LINOPE_ENVIRONMENT_TEST": "enabled"},
    )
    declaration = ProcessDeclaration(
        capability="context.sliding_window",
        resources=(
            ResourceClaim(
                kind=ResourceKind.CONTEXT,
                identity={"window": "default"},
            ),
        ),
    )
    process = ProcessReconciler(ResourcePool(store)).start(
        declaration,
        process_id="environment-process",
        environment=environment,
    )
    try:
        ready = process.ready_message
        assert ready["cwd"] == str(tmp_path.resolve())
        assert ready["environment_keys"] == ["LINOPE_ENVIRONMENT_TEST"]
        assert "resource_id" not in ready["resource_context"]["grants"][0]
    finally:
        process.stop()
        store.close()


def test_apply_loads_named_keys_and_leaves_values_out_of_the_payload(tmp_path, monkeypatch) -> None:
    env_path = tmp_path / "process.env"
    env_path.write_text(
        "# comment\nLINOPE_SECRET=hidden-value\nLINOPE_OTHER_SECRET=other-secret-value\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("LINOPE_SECRET", "old")
    monkeypatch.delenv("LINOPE_OTHER_SECRET", raising=False)
    environment = ProcessEnvironment(
        process_id="env-file",
        capability_id="context.sliding_window",
        cwd=tmp_path,
        env_file=str(env_path),
        env_file_keys=("LINOPE_SECRET",),
    )
    previous = os.getcwd()
    try:
        environment.apply()
        assert os.environ["LINOPE_SECRET"] == "hidden-value"
        assert "LINOPE_OTHER_SECRET" not in os.environ
    finally:
        os.chdir(previous)
    payload = json.dumps(environment.payload())
    assert "hidden-value" not in payload
    assert "other-secret-value" not in payload
    assert environment.env_file_keys == ("LINOPE_SECRET",)


def test_env_file_is_applied_for_a_non_model_process(tmp_path) -> None:
    env_path = tmp_path / "process.env"
    env_path.write_text(
        "LINOPE_SECRET=hidden-value\nLINOPE_OTHER_SECRET=other-secret-value\n",
        encoding="utf-8",
    )
    store = FileResourceStore(tmp_path / "resources.json")
    declaration = ProcessDeclaration(
        capability="context.sliding_window",
        resources=(
            ResourceClaim(
                kind=ResourceKind.CONTEXT,
                identity={"window": "default"},
            ),
        ),
    )
    process = ProcessReconciler(ResourcePool(store)).start(
        declaration,
        process_id="env-file-process",
        env_file=str(env_path),
        env_file_keys=("LINOPE_SECRET",),
    )
    try:
        ready = process.ready_message
        assert ready["env_file_keys"] == ["LINOPE_SECRET"]
        assert ready["env_file"].endswith("process.env")
        stored = json.dumps(store.activation_for("env-file-process"))
        assert "hidden-value" not in stored
        assert "other-secret-value" not in stored
    finally:
        process.stop()
        store.close()


def test_missing_env_file_key_fails_before_the_plugin_serves(tmp_path) -> None:
    env_path = tmp_path / "process.env"
    env_path.write_text("OTHER=1\n", encoding="utf-8")
    definition = describe_instance("context.sliding_window")
    store = FileResourceStore(tmp_path / "resources.json")
    declaration = ProcessDeclaration(
        capability="context.sliding_window",
        resources=(
            ResourceClaim(
                kind=ResourceKind.CONTEXT,
                identity={"window": "default"},
            ),
        ),
    )
    try:
        try:
            ProcessReconciler(ResourcePool(store)).start(
                declaration,
                process_id="missing-env-key",
                definition=definition,
                env_file=str(env_path),
                env_file_keys=("MISSING",),
            )
        except RuntimeError:
            return
        raise AssertionError("missing env file key was accepted")
    finally:
        store.close()


def test_host_policy_rejects_negative_limits() -> None:
    try:
        HostExecutionPolicy(max_memory_bytes=-1)
    except ValueError as error:
        assert "max_memory_bytes" in str(error)
    else:
        raise AssertionError("negative host memory limit was accepted")


def test_path_outside_workspace_is_rejected(tmp_path) -> None:
    workspace = tmp_path / "work"
    workspace.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("secret", encoding="utf-8")
    room = _room(workspace)
    try:
        room.file_io.resolve(str(outside), write=False)
    except PermissionError:
        pass
    else:
        raise AssertionError("path outside the workspace was accepted")
    inside = workspace / "notes.txt"
    room.file_io.write_text("notes.txt", "hello")
    assert inside.read_text(encoding="utf-8") == "hello"
    assert room.file_io.read_text("notes.txt") == "hello"


def test_secret_names_stay_out_of_the_startup_package(tmp_path) -> None:
    definition = CapabilityDefinition(
        instance_id="context.sliding_window",
        module_paths=(str(tmp_path / "plugin.py"),),
    )
    environment = ProcessEnvironment(
        process_id="secret-process",
        capability_id=definition.instance_id,
        cwd=tmp_path,
        env={"OPENAI_API_KEY": "sk-live", "PLAIN": "yes"},
    )
    activation = ProcessActivation(
        definition=definition,
        process_id="secret-process",
        environment=environment,
    )
    stored = json.dumps(activation.payload())
    assert "OPENAI_API_KEY" not in stored
    assert "sk-live" not in stored
    assert "PLAIN" in stored


def test_subprocess_env_is_scrubbed(tmp_path) -> None:
    room = _room(tmp_path)
    scrubbed = room.identity.scrub_env(
        {"PATH": "C:\\Windows", "OPENAI_API_KEY": "sk", "DB_PASSWORD": "hidden", "OK": "1"}
    )
    assert "OPENAI_API_KEY" not in scrubbed
    assert "DB_PASSWORD" not in scrubbed
    assert scrubbed["OK"] == "1"
    assert "Windows" in scrubbed["PATH"]


def test_missing_isolator_refuses_a_bare_run(tmp_path) -> None:
    room = _room(tmp_path)
    try:
        room.compute.prepare(("echo", "hi"), cwd=str(tmp_path), timeout_seconds=1, isolate=True)
    except RuntimeError as error:
        assert "没有隔离器" in str(error)
    else:
        raise AssertionError("bare run was accepted without an isolator")


def test_wall_clock_asks_the_process_to_stop() -> None:
    door = KernelEnvironment.build(
        shell=ProcessEnvironment(
            process_id="clock",
            capability_id="context.sliding_window",
            cwd=".",
        ),
        policy=HostExecutionPolicy(
            max_runtime_seconds=5,
            max_memory_bytes=10,
            heartbeat_interval_seconds=1,
            heartbeat_timeout_seconds=2,
        ),
        max_concurrent_tasks=1,
        max_sync_workers=1,
        channel_name="ledger",
    ).lifecycle

    class Stub:
        desired = ""

        def set_desired(self, process_id: str, desired: str) -> None:
            self.desired = desired

    stub = Stub()
    assert door.ask_stop(stub, "clock", 10, now=14) is False
    assert stub.desired == ""
    assert door.ask_stop(stub, "clock", 10, now=15) is True
    assert stub.desired == "stop"
    assert door.memory_over_limit(11) is True
    assert door.memory_over_limit(10) is False
    assert door.heartbeat_late(0, now=3) is True
    assert door.heartbeat_late(0, now=1) is False


def _room(workspace):
    shell = ProcessEnvironment(
        process_id="room",
        capability_id="tools.bash",
        cwd=workspace,
    )
    return KernelEnvironment.build(
        shell=shell,
        policy=HostExecutionPolicy(),
        max_concurrent_tasks=1,
        max_sync_workers=1,
        channel_name="ledger",
    )
