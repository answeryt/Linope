"""A capability command line is executed by the same door a person uses."""

import json
import sys
from pathlib import Path

from kernel.command.process.listen import hold
from kernel.process.declaration import ProcessDeclaration, ResourceClaim
from kernel.process.ledger import ProcessLedger
from kernel.process.process_creat.instances import CapabilityDefinition
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
        if text.startswith("model use "):
            return {"configured": True}
        if text.startswith("process start tools.ask_user"):
            return {"processes": [{"pid": 8, "capability": "tools.ask_user"}]}
        if text.startswith("load tool "):
            return "read-only file system"
        if text.startswith("model run -- "):
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
    pool = ResourcePool(ResourceLeaseManager())
    book = ProcessResourceBook(ProcessLedger(tmp_path / "ledger.json"))
    process = ProcessReconciler(pool, book).start(
        ProcessDeclaration(
            capability="agent_loop",
            resources=(ResourceClaim(kind="memory", identity={"scope": "chat"}),),
            settings={
                "model": "model.openai_chat_model",
                "tools": ["tools.ask_user"],
            },
        ),
        definition=CapabilityDefinition(
            instance_id="agent_loop",
            argv=(sys.executable, "-m", "capability.agent_loop.linope"),
        ),
    )

    class _Service:
        def __init__(self, *items: object) -> None:
            self._processes = {"capability": items}
            self.events: list[dict] = []

        def processes(self) -> tuple:
            return tuple(self._processes["capability"])

        def emit(self, kind: str, data: dict | None = None, **fields: object) -> None:
            self.events.append({"kind": kind, "data": dict(data or {}), **fields})

        def close(self) -> None:
            for item in self._processes["capability"]:
                item.stop()

    service = _Service(process)
    try:
        hold(service, lines=[f"load message {process.pid} -- read the file outside the room"], timeout=20)
    finally:
        service.close()
    rendered = json.dumps(
        [event["data"].get("value") for event in service.events],
        ensure_ascii=False,
    )
    assert "The file is blocked." in rendered
    assert any(line == "model use model.openai_chat_model" for line in seen)
    assert any(line.startswith("load tool 8 -- ") for line in seen)
    assert all("bwrap" not in line for line in seen)
