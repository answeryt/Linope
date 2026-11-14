"""Run the same two-task round through the real Cordis agent loop."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from example.utilization.common import HERE, append_event, fingerprint, prompt_text, tasks_for
from example.utilization.proxy import Proxy

HARNESS = HERE.parents[1] / "deepseek-harness-master"
RUNNER = HARNESS / "examples" / "utilization-dsh.ts"


def run(
    *,
    group: str,
    nonce: str,
    seconds: float,
    log_path: Path,
    upstream: str,
    model: str,
    api_key: str,
    serial: bool = False,
) -> None:
    tasks = tasks_for(group, seconds, nonce)
    log_path = log_path.resolve()
    if log_path.exists():
        log_path.unlink()
    proxy = Proxy(log_path, upstream=upstream, serial=serial)
    base_url = proxy.start()
    append_event(log_path, {
        "kind": "round",
        "arm": "dsh-async" if serial else "dsh",
        "group": group,
        "nonce": nonce,
        "fingerprint": fingerprint(),
        "t": time.time(),
    })
    environment = os.environ.copy()
    environment.update({
        "OPENAI_API_KEY": api_key,
        "DEEPSEEK_API_KEY": api_key,
        "DSH_BASE_URL": base_url,
        "ROUND_LOG": str(log_path),
        "PROMPT_FILE": str(HERE / "prompt.txt"),
        "TOOLS_JSON": str(HERE / "tools.json"),
        "SLOW_READ": str(HERE / "slow_read.py"),
        "TASKS_JSON": json.dumps([{"id": item["id"], "text": item["text"]} for item in tasks]),
        "UTILIZATION_MODEL": model,
        "PYTHON": sys.executable,
    })
    try:
        node = shutil.which("node")
        tsx = HARNESS / "node_modules" / "tsx" / "dist" / "cli.mjs"
        if node is None or not tsx.is_file():
            raise RuntimeError("node or tsx is not available")
        completed = subprocess.run(
            [node, str(tsx), str(RUNNER)],
            cwd=HARNESS,
            env=environment,
            check=False,
        )
    finally:
        proxy.close()
    if completed.returncode != 0:
        raise RuntimeError(f"dsh agent loop exited {completed.returncode}")
    if prompt_text() == "":
        raise RuntimeError("shared prompt is empty")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--group", choices=("mechanism", "real"), required=True)
    parser.add_argument("--nonce", required=True)
    parser.add_argument("--seconds", type=float, default=0)
    parser.add_argument("--log", required=True)
    parser.add_argument("--model", default=os.environ.get("UTILIZATION_MODEL", "deepseek-flash"))
    parser.add_argument("--upstream", default=os.environ.get("UTILIZATION_UPSTREAM", "https://api.deepseek.com"))
    parser.add_argument("--serial", action="store_true")
    args = parser.parse_args(argv)
    key_line = ""
    for line in (HERE.parents[1] / ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith("OPENAI_API_KEY="):
            key_line = line.split("=", 1)[1]
            break
    if not key_line:
        raise RuntimeError("OPENAI_API_KEY is missing")
    run(
        group=args.group,
        nonce=args.nonce,
        seconds=args.seconds,
        log_path=Path(args.log),
        upstream=args.upstream,
        model=args.model,
        api_key=key_line,
        serial=args.serial,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
