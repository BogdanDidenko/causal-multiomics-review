#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from causal_multiomics_review.config import DEFAULT_SUITE_CONFIG, load_stage_config
from causal_multiomics_review.stability import assess_stability


def read_jsonl(path: Path) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                row = json.loads(line)
                rows[str(row["record_id"])] = row
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Measure exact criterion-level stability across repeated screening runs"
    )
    parser.add_argument("--stage", choices=("title_abstract", "full_text"), required=True)
    parser.add_argument("--run", action="append", required=True, metavar="LABEL=RESULTS_JSONL")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--suite-config", type=Path, default=DEFAULT_SUITE_CONFIG)
    args = parser.parse_args()

    suite, _ = load_stage_config(args.stage, args.suite_config)
    policy = suite["stability_policy"]
    run_paths: dict[str, Path] = {}
    for specification in args.run:
        if "=" not in specification:
            raise SystemExit(f"Invalid --run value: {specification}")
        label, raw_path = specification.split("=", 1)
        if label in run_paths:
            raise SystemExit(f"Duplicate run label: {label}")
        run_paths[label] = Path(raw_path)
    if len(run_paths) != policy["repeats"]:
        raise SystemExit(f"Stability policy requires exactly {policy['repeats']} runs")

    for path in run_paths.values():
        _validate_run_manifest(
            path,
            suite,
        )
    run_results = {label: read_jsonl(path) for label, path in run_paths.items()}
    rows, summary = assess_stability(run_results, args.stage, policy["acceptance"])
    summary["model"] = suite["provider"]["model"]
    summary["model_display_name"] = suite["provider"]["display_name"]
    summary["suite_version"] = suite["suite_version"]
    args.output_dir.mkdir(parents=True, exist_ok=True)
    with (args.output_dir / "stability_results.jsonl").open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    (args.output_dir / "stability_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(summary["acceptance"]["overall"])


def _validate_run_manifest(
    result_path: Path,
    suite: dict[str, Any],
) -> None:
    manifest_path = result_path.parent / "manifest.json"
    if not manifest_path.is_file():
        raise SystemExit(f"Missing run manifest beside {result_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected_model = suite["provider"]["model"]
    if manifest.get("model") != expected_model:
        raise SystemExit(
            f"Run manifest {manifest_path} used {manifest.get('model')!r}, "
            f"expected {expected_model!r}"
        )
    runtime = manifest.get("runtime", {})
    expected_runtime = {
        "api_protocol": suite["runtime"]["provider_protocol"],
        "reasoning_effort": suite["runtime"]["reasoning_effort"],
        "context_window": suite["runtime"]["context_window"],
        "response_format": suite["runtime"]["response_format"],
        "sandbox": suite["provider"]["sandbox"],
        "approval_policy": suite["provider"]["approval_policy"],
        "ephemeral": suite["provider"]["ephemeral"],
        "ignore_user_config": suite["provider"]["ignore_user_config"],
        "ignore_rules": suite["provider"]["ignore_rules"],
    }
    for field, expected in expected_runtime.items():
        actual = runtime.get(field)
        if actual != expected:
            raise SystemExit(
                f"Run manifest {manifest_path} used {field}={actual!r}, "
                f"expected {expected!r}"
            )


if __name__ == "__main__":
    main()
