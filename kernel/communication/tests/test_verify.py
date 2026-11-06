"""The kernel does not keep a second command parser. The agent loop writes command lines."""

from pathlib import Path


def test_communication_does_not_parse_model_output() -> None:
    root = Path(__file__).resolve().parents[1]
    for path in root.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "capability.loop" not in text
        assert "def verify(" not in text
