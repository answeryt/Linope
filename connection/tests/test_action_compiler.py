"""Tests for deterministic semantic action compilation."""

from __future__ import annotations

import shlex

import pytest

from connection.protocol.request import ProtocolError, parse_request
from connection.semantic.action_compiler import compile_action
from connection.semantic.action_types import EnvironmentDefaults


def request(action: str, payload: dict) -> object:
    return parse_request(
        {
            "version": 1,
            "request_id": "test-request",
            "action": action,
            "payload": payload,
        }
    )


def test_chat_send_compiles_to_global_model_task() -> None:
    compiled = compile_action(request("chat.send", {"text": "你好"}))

    assert shlex.split(compiled.commands[0]) == ["model", "run", "--", "你好"]
    assert compiled.completion == "turn"


def test_process_send_keeps_process_target_explicit() -> None:
    compiled = compile_action(
        request(
            "process.send",
            {"pid": 7, "addresses": ["chat/message/0"], "text": "读取文件"},
        )
    )

    assert shlex.split(compiled.commands[0]) == [
        "load",
        "message",
        "7",
        "chat/message/0",
        "--",
        "读取文件",
    ]


def test_process_create_uses_loaded_environment_defaults() -> None:
    compiled = compile_action(
        request(
            "process.create",
            {
                "capability": "tools.read",
                "changes": [{"topic": "mode", "value": "safe"}],
                "count": 2,
            },
        ),
        EnvironmentDefaults(path=".env", keys=("OPENAI_API_KEY",)),
    )

    words = shlex.split(compiled.commands[0])
    assert words[:3] == ["process", "start", "tools.read"]
    assert "--change" in words
    assert "--count" in words
    assert "--env-file" in words
    assert "--env" in words


def test_model_configuration_compiles_in_order() -> None:
    compiled = compile_action(
        request(
            "model.configure",
            {
                "capability": "model.openai_chat_model",
                "cores": 2,
                "changes": [{"topic": "temperature", "value": "0.2"}],
            },
        )
    )

    assert [shlex.split(command)[:3] for command in compiled.commands] == [
        ["model", "cores", "2"],
        ["model", "use", "model.openai_chat_model"],
    ]


def test_memory_configuration_compiles_to_backend_command() -> None:
    compiled = compile_action(
        request("memory.configure", {"backend": "local", "path": "D:/linope-memory"})
    )

    assert shlex.split(compiled.commands[0]) == [
        "memory",
        "backend",
        "local",
        "--path",
        "D:/linope-memory",
    ]
    assert compiled.completion == "command"
    memory = compile_action(request("memory.configure", {"backend": "memory"}))
    assert shlex.split(memory.commands[0]) == ["memory", "backend", "memory"]


def test_memory_configuration_requires_a_local_path() -> None:
    with pytest.raises(ProtocolError, match="path must be a non-empty string"):
        compile_action(request("memory.configure", {"backend": "local"}))


def test_invalid_environment_keys_are_rejected() -> None:
    with pytest.raises(ProtocolError, match="envKeys requires"):
        compile_action(
            request(
                "process.create",
                {"capability": "tools.read", "envKeys": ["TOKEN"]},
            )
        )
