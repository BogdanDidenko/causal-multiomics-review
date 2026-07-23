#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from causal_multiomics_review.config import DEFAULT_SUITE_CONFIG, REPO_ROOT, load_stage_config


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the active single-model screening suite repeatedly and assess stability"
    )
    parser.add_argument("input", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--stage", choices=("title_abstract", "full_text"), required=True)
    parser.add_argument("--suite-config", type=Path, default=DEFAULT_SUITE_CONFIG)
    parser.add_argument("--api-key-env")
    parser.add_argument("--base-url")
    parser.add_argument("--model")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    suite, _ = load_stage_config(args.stage, args.suite_config)
    repeats = suite["stability_policy"]["repeats"]
    run_script = REPO_ROOT / "scripts" / "run_screening.py"
    result_paths: list[tuple[str, Path]] = []
    for index in range(1, repeats + 1):
        label = f"replicate-{index:02d}"
        run_dir = args.output_dir / "replicates" / label
        result_path = run_dir / "screening_results.jsonl"
        if result_path.exists() and not args.resume:
            raise SystemExit(f"Refusing to overwrite existing run: {result_path}")
        command = [
            sys.executable,
            str(run_script),
            str(args.input),
            str(run_dir),
            "--stage",
            args.stage,
            "--suite-config",
            str(args.suite_config),
        ]
        _append_option(command, "--api-key-env", args.api_key_env)
        _append_option(command, "--base-url", args.base_url)
        _append_option(command, "--model", args.model)
        _append_option(command, "--limit", args.limit)
        if args.resume:
            command.append("--resume")
        subprocess.run(command, check=True)
        result_paths.append((label, result_path))

    assess_command = [
        sys.executable,
        str(REPO_ROOT / "scripts" / "assess_screening_stability.py"),
        "--stage",
        args.stage,
        "--output-dir",
        str(args.output_dir),
        "--suite-config",
        str(args.suite_config),
    ]
    for label, result_path in result_paths:
        assess_command.extend(("--run", f"{label}={result_path}"))
    subprocess.run(assess_command, check=True)


def _append_option(command: list[str], flag: str, value: str | int | None) -> None:
    if value is not None:
        command.extend((flag, str(value)))


if __name__ == "__main__":
    main()
