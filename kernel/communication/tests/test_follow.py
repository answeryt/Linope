"""A capability command line is executed by the same door a person uses."""

import json
from pathlib import Path

from kernel.command.process.listen import hold
from kernel.process.declaration import ProcessDeclaration, ResourceClaim
from kernel.process.ledger import ProcessLedger
from kernel.process.process_creat.instances import CapabilityDefinition, repo_root
from kernel.process.reconcile import ProcessReconciler
from kernel.process.resource_record import ProcessResourceBook
from kernel.resource.lease import ResourceLeaseManager
from kernel.resource.pool import ResourcePool


def test_agent_loop_commands_use_the_same_door(tmp_path: Path, monkeypatch, capsys) -> None:
    seen: list[str] = []
    answers = {"loads": 0}

    def execute_line(text: str, service=None) -> str:
        del service
        seen.append(text)
        if text == "list":
            return ""
        if text.startswith("process start model."):
            return "pid=7 capability=model.openai_chat_model"
        if text.startswith("process start tools.ask_user"):
            return "pid=8 capability=tools.ask_user"
        if text.startswith("load tool "):
            return "read-only file system"
        if text.startswith("load message "):
            answers["loads"] += 1
            if answers["loads"] == 1:
                return json.dumps(
                    {
                        "type": "model_turn",
                        "blocks": [
                            {
                                "type": "tool-call",
                                "id": "call-1",
                                "name": "tools_ask_user",
                                "arguments": {"file_path": "../outside"},
                            }
                        ],
                    },
                    ensure_ascii=False,
                )
            return "The file is blocked."
        return ""

    monkeypatch.setattr("kernel.command.process.clerk.execute_line", execute_line)
    root = repo_root()
    pool = ResourcePool(ResourceLeaseManager())
    book = ProcessResourceBook(ProcessLedger(tmp_path / "ledger.json"))
    process = ProcessReconciler(pool, book).start(
        ProcessDeclaration(
            capability="agent_loop",
            resources=(ResourceClaim(kind="memory", identity={"scope": "chat"}),),
            settings={"model": "model.openai_chat_model"},
        ),
        definition=CapabilityDefinition(
            instance_id="agent_loop",
            argv=("node", str(root / "capability" / "agent_loop" / "pi" / "main.mjs")),
        ),
    )

    class _Service:
        def __init__(self, *items: object) -> None:
            self._processes = {"capability": items}

        def processes(self) -> tuple:
            return tuple(self._processes["capability"])

        def close(self) -> None:
            for item in self._processes["capability"]:
                item.stop()

    service = _Service(process)
    try:
        hold(service, lines=[f"load message {process.pid} -- read the file outside the room"], timeout=20)
    finally:
        service.close()
    captured = capsys.readouterr()
    assert "The file is blocked." in captured.out, captured.err
    assert any(line.startswith("process start model.openai_chat_model") for line in seen)
    assert any(line.startswith("load tool 8 -- ") for line in seen)
    assert all("bwrap" not in line for line in seen)
