#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
from pathlib import Path

from causal_multiomics_review.llm import OpenAICompatibleProvider
from causal_multiomics_review.screening import run_screening


def main() -> None:
    parser = argparse.ArgumentParser(description="Run criterion-level screening")
    parser.add_argument("input", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--model", required=True)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--api-key-env", default="SCREENING_API_KEY")
    parser.add_argument("--config", type=Path)
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()

    api_key = os.environ.get(args.api_key_env)
    if not api_key:
        raise SystemExit(f"Missing API key in {args.api_key_env}")
    provider = OpenAICompatibleProvider(args.base_url, api_key, args.model)
    counts = run_screening(
        args.input,
        args.output_dir,
        provider,
        config_path=args.config,
        limit=args.limit,
    )
    print(" ".join(f"{decision}={count}" for decision, count in sorted(counts.items())))


if __name__ == "__main__":
    main()
