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
    parser.add_argument("--model")
    parser.add_argument("--base-url")
    parser.add_argument("--api-key-env")
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
        "--reasoning-effort",
        choices=("none", "low", "medium", "high", "xhigh", "max"),
    )
    parser.add_argument("--text-verbosity", choices=("low", "medium", "high"))
    parser.add_argument(
        "--response-format",
        choices=("json_schema", "json_object"),
    )
    args = parser.parse_args()

    if args.config:
        if not args.model or not args.base_url:
            raise SystemExit("--model and --base-url are required with --config")
        api_key_env = args.api_key_env or "SCREENING_API_KEY"
        api_key = os.environ.get(api_key_env)
        if not api_key:
            raise SystemExit(f"Missing API key in {api_key_env}")
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
    provider_config = suite["provider"]
    api_key_env = args.api_key_env or provider_config["api_key_env"]
    api_key = os.environ.get(api_key_env)
    if not api_key:
        raise SystemExit(f"Missing API key in {api_key_env}")
    runtime = suite["runtime"]
    configured_model = provider_config["model"]
    if args.model and args.model != configured_model:
        raise SystemExit(
            f"Active suite requires {configured_model}; model override is not permitted"
        )
    provider = OpenAICompatibleProvider(
        args.base_url or provider_config["base_url"],
        api_key,
        configured_model,
        temperature=(
            args.temperature
            if args.temperature is not None
            else runtime.get("temperature", 0.0)
        ),
        top_p=args.top_p if args.top_p is not None else runtime.get("top_p", 1.0),
        seed=args.seed if args.seed is not None else runtime.get("seed", 0),
        n=runtime.get("n", 1),
        max_tokens=args.max_tokens or stage_config["max_tokens"],
        response_format=args.response_format or runtime["response_format"],
        api_protocol=runtime["provider_protocol"],
        reasoning_effort=args.reasoning_effort or runtime.get("reasoning_effort"),
        text_verbosity=args.text_verbosity or runtime.get("text_verbosity"),
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
