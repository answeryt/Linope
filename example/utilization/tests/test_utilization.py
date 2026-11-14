"""The utilization definition and one mocked pair of rounds."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from example.utilization.analyze import main as analyze_main
from example.utilization.common import fingerprint, load_events, summarize, wait_seconds
from example.utilization.proxy import Proxy
from example.utilization.run_linope import run


def test_wait_tracks_the_slow_requests() -> None:
    assert wait_seconds([1, 2, 3, 4, 10]) == pytest.approx(10 * 1.75)


def test_overlap_is_not_a_usable_round(tmp_path: Path) -> None:
    path = tmp_path / "round.jsonl"
    rows = [
        {"kind": "round", "arm": "harness", "group": "mechanism", "t": 0},
        {"kind": "tasks_submitted", "t": 1},
        {"kind": "request_start", "id": "a1", "task": "a", "t": 1},
        {"kind": "request_start", "id": "b1", "task": "b", "t": 1.1},
        {"kind": "request_end", "id": "a1", "task": "a", "t": 2},
        {"kind": "request_end", "id": "b1", "task": "b", "t": 2.1},
        {"kind": "request_start", "id": "a2", "task": "a", "t": 3},
        {"kind": "request_end", "id": "a2", "task": "a", "t": 4},
        {"kind": "request_start", "id": "b2", "task": "b", "t": 4},
        {"kind": "request_end", "id": "b2", "task": "b", "t": 5},
        {"kind": "task_finished", "task": "a", "t": 4},
        {"kind": "task_finished", "task": "b", "t": 5},
    ]
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    summary = summarize(rows)
    assert summary["overlap"] is True
    assert summary["valid"] is False
    assert analyze_main([str(path)]) == 0


def test_linope_round_keeps_one_request(tmp_path: Path) -> None:
    log = tmp_path / "linope.jsonl"
    proxy = Proxy(log, mock=True, mock_seconds=0.05)
    base_url = proxy.start()
    try:
        run(
            group="mechanism",
            nonce="n1",
            seconds=0.2,
            log_path=log,
            base_url=base_url,
            model="mock",
        )
    finally:
        proxy.close()
    summary = summarize(load_events(log))
    assert summary["valid"] is True
    assert summary["overlap"] is False
    assert summary["requests"] == 4
    assert 0 < summary["u"] < 1
    assert summary["idle"] == pytest.approx(summary["twall"] - summary["tbusy"])


def test_prompt_hash_matches_the_harness_reader() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")
    completed = subprocess.run(
        [node, str(ROOT / "example" / "utilization" / "run_harness.mjs"), "--fingerprint"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(completed.stdout) == fingerprint()
    raw = (ROOT / "example" / "utilization" / "prompt.txt").read_bytes()
    assert fingerprint()["prompt"] == hashlib.sha256(raw).hexdigest()


def test_harness_overlap_is_rejected(tmp_path: Path) -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")
    log = tmp_path / "harness.jsonl"
    proxy = Proxy(log, mock=True, mock_seconds=0.05)
    base_url = proxy.start()
    try:
        completed = subprocess.run(
            [
                node,
                str(ROOT / "example" / "utilization" / "run_harness.mjs"),
                "--group",
                "mechanism",
                "--nonce",
                "n1",
                "--seconds",
                "0.2",
                "--log",
                str(log),
                "--proxy",
                base_url,
                "--model",
                "mock",
            ],
            check=False,
            capture_output=True,
            text=True,
        )
    finally:
        proxy.close()
    assert completed.returncode == 0, completed.stderr
    summary = summarize(load_events(log))
    assert summary["overlap"] is True
    assert summary["valid"] is False
