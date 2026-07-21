#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
from pathlib import Path

from causal_multiomics_review.config import DEFAULT_SUITE_CONFIG, load_stage_config
from causal_multiomics_review.llm import OpenAICompatibleProvider
from causal_multiomics_review.screening import run_screening, run_stage_screening


def main() -> None:
    parser = argparse.ArgumentParser(description="Run criterion-level screening")
    parser.add_argument("input", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--model", required=True)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--api-key-env", default="SCREENING_API_KEY")
    parser.add_argument(
        "--stage",
        choices=("title_abstract", "full_text"),
        default="title_abstract",
    )
    parser.add_argument("--suite-config", type=Path, default=DEFAULT_SUITE_CONFIG)
    parser.add_argument(
        "--config",
        type=Path,
        help="run the immutable legacy title/abstract contract with this gate config",
    )
    parser.add_argument("--limit", type=int)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--temperature", type=float)
    parser.add_argument("--top-p", type=float)
    parser.add_argument("--seed", type=int)
    parser.add_argument("--max-tokens", type=int)
    parser.add_argument(
        "--response-format",
        choices=("json_schema", "json_object"),
    )
    args = parser.parse_args()

    api_key = os.environ.get(args.api_key_env)
    if not api_key:
        raise SystemExit(f"Missing API key in {args.api_key_env}")
    if args.config:
        provider = OpenAICompatibleProvider(
            args.base_url,
            api_key,
            args.model,
            temperature=args.temperature if args.temperature is not None else 0.0,
            top_p=args.top_p if args.top_p is not None else 1.0,
            seed=args.seed if args.seed is not None else 0,
            max_tokens=args.max_tokens,
            response_format=args.response_format or "json_object",
        )
        counts = run_screening(
            args.input,
            args.output_dir,
            provider,
            config_path=args.config,
            limit=args.limit,
        )
        print(" ".join(f"{key}={value}" for key, value in sorted(counts.items())))
        return

    suite, stage_config = load_stage_config(args.stage, args.suite_config)
    runtime = suite["runtime"]
    provider = OpenAICompatibleProvider(
        args.base_url,
        api_key,
        args.model,
        temperature=args.temperature if args.temperature is not None else runtime["temperature"],
        top_p=args.top_p if args.top_p is not None else runtime["top_p"],
        seed=args.seed if args.seed is not None else runtime["seed"],
        n=runtime["n"],
        max_tokens=args.max_tokens or stage_config["max_tokens"],
        response_format=args.response_format or runtime["response_format"],
    )
    counts = run_stage_screening(
        args.input,
        args.output_dir,
        provider,
        stage=args.stage,
        suite_config_path=args.suite_config,
        limit=args.limit,
        resume=args.resume,
    )
    print(" ".join(f"{decision}={count}" for decision, count in sorted(counts.items())))


if __name__ == "__main__":
    main()
