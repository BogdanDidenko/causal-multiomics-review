#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

from causal_multiomics_review.ensemble import aggregate_title_abstract_runs


def read_jsonl(path: Path) -> dict[str, dict[str, object]]:
    rows: dict[str, dict[str, object]] = {}
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            rows[str(row["record_id"])] = row
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Apply the conservative six-run title/abstract ensemble policy"
    )
    parser.add_argument(
        "--run",
        action="append",
        required=True,
        metavar="LABEL=RESULTS_JSONL",
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    args = parser.parse_args()

    run_paths: dict[str, Path] = {}
    for specification in args.run:
        if "=" not in specification:
            raise SystemExit(f"Invalid --run value: {specification}")
        label, raw_path = specification.split("=", 1)
        if label in run_paths:
            raise SystemExit(f"Duplicate run label: {label}")
        run_paths[label] = Path(raw_path)
    if len(run_paths) != 6:
        raise SystemExit("The deployment policy requires exactly six runs")

    by_record: dict[str, list[dict[str, object]]] = defaultdict(list)
    expected_ids: set[str] | None = None
    for label, path in run_paths.items():
        rows = read_jsonl(path)
        current_ids = set(rows)
        if expected_ids is None:
            expected_ids = current_ids
        elif current_ids != expected_ids:
            missing = sorted(expected_ids - current_ids)
            extra = sorted(current_ids - expected_ids)
            raise SystemExit(
                f"Run {label} has a different record set; missing={missing[:5]} extra={extra[:5]}"
            )
        for identifier, row in rows.items():
            by_record[identifier].append(row)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    counts: dict[str, int] = defaultdict(int)
    with args.output.open("w", encoding="utf-8") as handle:
        for identifier in sorted(by_record):
            result = aggregate_title_abstract_runs(by_record[identifier])
            result["run_labels"] = sorted(run_paths)
            handle.write(json.dumps(result, ensure_ascii=False) + "\n")
            counts[result["ensemble_decision"]] += 1

    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.summary.write_text(
        json.dumps(
            {
                "run_count": len(run_paths),
                "record_count": len(by_record),
                "decision_counts": dict(counts),
                "policy": "exclude only when all six runs exclude with the same code",
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
