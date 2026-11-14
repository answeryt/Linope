"""Measure one model request, then choose the controlled tool wait."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from example.utilization.common import RUNS, fingerprint, openai_tools, prompt_text, wait_seconds
from example.utilization.proxy import Proxy, post_chat


def measure_once(base_url: str, model: str, api_key: str) -> float:
    """Duration of one request that must not call a tool."""

    started = time.time()
    post_chat(
        base_url,
        {
            "model": model,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": prompt_text()},
                {"role": "user", "content": "Reply with the single word pong. Do not call a tool."},
            ],
            "tools": openai_tools(),
        },
        task_id="calibration",
        api_key=api_key,
    )
    return time.time() - started


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=os.environ.get("UTILIZATION_MODEL", "deepseek-flash"))
    parser.add_argument("--samples", type=int, default=5)
    parser.add_argument("--mock", action="store_true")
    parser.add_argument("--upstream", default=os.environ.get("UTILIZATION_UPSTREAM", ""))
    parser.add_argument("--mock-seconds", type=float, default=0.05)
    parser.add_argument("--out", default=str(RUNS / "calibration.json"))
    args = parser.parse_args(argv)
    log_path = RUNS / "calibration-requests.jsonl"
    if log_path.exists():
        log_path.unlink()
    proxy = Proxy(
        log_path,
        mock=args.mock,
        upstream=args.upstream,
        mock_seconds=args.mock_seconds,
    )
    base_url = proxy.start()
    try:
        samples = [
            measure_once(base_url, args.model, os.environ.get("OPENAI_API_KEY", ""))
            for _ in range(args.samples)
        ]
    finally:
        proxy.close()
    chosen = wait_seconds(samples)
    payload = {
        "fingerprint": fingerprint(),
        "model": args.model,
        "samples": samples,
        "wait_seconds": chosen,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
