#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
from pathlib import Path

from causal_multiomics_review.deduplication import deduplicate


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Conservatively deduplicate normalized records")
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--log", type=Path, required=True)
    args = parser.parse_args()

    source = read_csv(args.input)
    canonical, log = deduplicate(source)
    write_csv(args.output, canonical)
    write_csv(args.log, log)
    print(f"input={len(source)} canonical={len(canonical)} duplicates={len(log)}")


if __name__ == "__main__":
    main()
