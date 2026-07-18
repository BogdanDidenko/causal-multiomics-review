#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


def read_decisions(path: Path) -> dict[str, str]:
    decisions: dict[str, str] = {}
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            decisions[str(row["record_id"])] = str(row["final_decision"])
    return decisions


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare two screening replicate JSONL files")
    parser.add_argument("left", type=Path)
    parser.add_argument("right", type=Path)
    args = parser.parse_args()

    left, right = read_decisions(args.left), read_decisions(args.right)
    shared = sorted(set(left) & set(right))
    pairs = Counter((left[item], right[item]) for item in shared)
    agreements = sum(count for (a, b), count in pairs.items() if a == b)
    rate = agreements / len(shared) if shared else 0.0

    print(f"shared={len(shared)} agreement={agreements} rate={rate:.4f}")
    for (left_value, right_value), count in sorted(pairs.items()):
        print(f"{left_value}\t{right_value}\t{count}")


if __name__ == "__main__":
    main()
