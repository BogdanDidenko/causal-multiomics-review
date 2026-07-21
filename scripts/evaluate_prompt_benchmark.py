#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from causal_multiomics_review.benchmark import (
    FULL_TEXT_ACCEPTANCE,
    TITLE_ACCEPTANCE,
    acceptance_report,
    evaluate_full_text,
    evaluate_title,
)


def read_csv(path: Path) -> dict[str, dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return {str(row["canonical_id"]): row for row in csv.DictReader(handle)}


def read_jsonl(path: Path) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                row = json.loads(line)
                rows[str(row["record_id"])] = row
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate screening output against expert labels")
    parser.add_argument("benchmark", type=Path)
    parser.add_argument("results", type=Path)
    parser.add_argument("--stage", choices=("title_abstract", "full_text"), required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    expected, predicted = read_csv(args.benchmark), read_jsonl(args.results)
    metrics = (
        evaluate_title(expected, predicted)
        if args.stage == "title_abstract"
        else evaluate_full_text(expected, predicted)
    )
    thresholds = (
        TITLE_ACCEPTANCE if args.stage == "title_abstract" else FULL_TEXT_ACCEPTANCE
    )
    metrics["acceptance"] = acceptance_report(metrics, thresholds)
    text = json.dumps(metrics, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")


if __name__ == "__main__":
    main()
