"""The capability tree writes the table. The kernel is not asked to build it."""

from __future__ import annotations

import json
from pathlib import Path

from capability.catalog import build_table


def test_a_python_plugin_records_its_own_command(tmp_path: Path) -> None:
    root = tmp_path / "capability"
    plugin = root / "model" / "sample_model" / "sample_model_plugin.py"
    plugin.parent.mkdir(parents=True)
    plugin.write_text(
        "from kernel.process.declaration import ProcessDeclaration, ResourceClaim\n"
        "from kernel.resource.definition import ResourceKind\n"
        "CARD_CONFIG = {'model': 'demo', 'provider': 'local', 'api_key_env': 'DEMO_KEY',"
        " 'parameters': {'temperature': 'UNSET'}}\n"
        "def load(kind, body, call_params=None):\n"
        "    return body\n"
        "def capability_profile(capability_id, changes):\n"
        "    return ProcessDeclaration(\n"
        "        capability=capability_id,\n"
        "        resources=(ResourceClaim(kind=ResourceKind.NETWORK, identity={'channel': 'ledger'}),),\n"
        "        settings={'id': 'demo'},\n"
        "    )\n",
        encoding="utf-8",
    )
    table = build_table(root)
    assert "model.sample_model" not in table


def test_a_broken_profile_is_left_out(tmp_path: Path) -> None:
    root = tmp_path / "capability"
    plugin = root / "tools" / "broken_plugin.py"
    plugin.parent.mkdir(parents=True)
    plugin.write_text(
        "def load(kind, body, call_params=None):\n"
        "    return body\n"
        "def capability_profile(capability_id, changes):\n"
        "    raise RuntimeError('missing profile helper')\n",
        encoding="utf-8",
    )
    assert build_table(root) == {}


def test_a_tool_schema_is_stored_on_the_row(tmp_path: Path) -> None:
    root = tmp_path / "capability"
    plugin = root / "tools" / "read_plugin.py"
    plugin.parent.mkdir(parents=True)
    plugin.write_text(
        "from kernel.process.declaration import ProcessDeclaration, ResourceClaim\n"
        "from kernel.resource.definition import ResourceKind\n"
        "def load(kind, body, call_params=None):\n"
        "    return body\n"
        "def tool_schemas():\n"
        "    return [{'name': 'read', 'description': 'Read a file',\n"
        "             'parameters': {'type': 'object', 'properties': {'file_path': {'type': 'string'}},\n"
        "                            'required': ['file_path']}}]\n"
        "def capability_profile(capability_id, changes):\n"
        "    return ProcessDeclaration(\n"
        "        capability=capability_id,\n"
        "        resources=(ResourceClaim(kind=ResourceKind.TOOL, identity={'id': capability_id}),),\n"
        "    )\n",
        encoding="utf-8",
    )
    row = build_table(root)["tools.read"]
    assert row["schemas"][0]["parameters"]["required"] == ["file_path"]


def test_read_declares_a_read_only_workspace_and_its_schema() -> None:
    root = Path(__file__).resolve().parents[1]
    row = build_table(root)["tools.read"]
    assert row["argv"][:3] == ["python", "-m", "capability.program"]
    sandbox = row["resources"][1]
    assert sandbox["kind"] == "sandbox"
    assert sandbox["call_params"]["mode"] == "read-only"
    assert row["schemas"][0]["parameters"]["required"] == ["file_path"]


def test_a_manifest_keeps_its_own_command(tmp_path: Path) -> None:
    root = tmp_path / "capability"
    package = root / "tools" / "echo_node"
    package.mkdir(parents=True)
    (package / "linope.json").write_text(
        json.dumps(
            {
                "name": "tools.echo_node",
                "command": ["node", "echo.js"],
                "resources": [{"kind": "tool", "identity": {"id": "echo_node"}}],
                "secrets": ["NODE_TOKEN"],
                "changes": ["query"],
            }
        ),
        encoding="utf-8",
    )
    row = build_table(root)["tools.echo_node"]
    assert row["argv"] == ["node", "echo.js"]
    assert row["secret_names"] == ["NODE_TOKEN"]
    assert row["changes"] == ["query"]
    assert "capability.program" not in row["argv"]
