"""Compute U = Tbusy / Twall for one round or a directory of rounds."""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from example.utilization.common import load_events, summarize


def round_files(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    return sorted(item for item in path.glob("*.jsonl") if item.is_file())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("path")
    args = parser.parse_args(argv)
    files = round_files(Path(args.path))
    if not files:
        raise SystemExit(f"No JSONL rounds in {args.path}")
    rows = []
    for path in files:
        try:
            row = summarize(load_events(path))
        except (OSError, ValueError, json.JSONDecodeError, StopIteration) as exc:
            row = {"file": path.name, "valid": False, "error": str(exc)}
        row["file"] = path.name
        rows.append(row)
        print(json.dumps(row, ensure_ascii=False))
    grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in rows:
        if row.get("valid"):
            grouped[(str(row.get("arm")), str(row.get("group")))].append(row)
    summary = []
    for (arm, group), items in sorted(grouped.items()):
        mean_u = sum(float(item["u"]) for item in items) / len(items)
        mean_idle = sum(float(item["idle"]) for item in items) / len(items)
        summary.append({
            "arm": arm,
            "group": group,
            "rounds": len(items),
            "mean_u": mean_u,
            "mean_idle": mean_idle,
        })
    print(json.dumps({"summary": summary}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
