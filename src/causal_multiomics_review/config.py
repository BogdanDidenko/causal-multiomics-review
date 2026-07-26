from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_ROOT = REPO_ROOT / "protocol"
SCREENING_ROOT = PROTOCOL_ROOT / "screening"
DEFAULT_SUITE_CONFIG = SCREENING_ROOT / "configs" / "prompt_suite_v0.8.0.json"


def load_json(path: str | Path) -> dict[str, Any]:
    with Path(path).open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object in {path}")
    return value


def load_gate_config(path: str | Path | None = None) -> dict[str, Any]:
    return load_json(path or PROTOCOL_ROOT / "screening" / "gate_config.json")


def load_suite_config(path: str | Path | None = None) -> dict[str, Any]:
    return load_json(path or DEFAULT_SUITE_CONFIG)


def load_stage_config(
    stage: str,
    path: str | Path | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    suite = load_suite_config(path)
    try:
        stage_config = suite["stages"][stage]
    except KeyError as error:
        available = ", ".join(sorted(suite.get("stages", {})))
        raise ValueError(
            f"Unknown screening stage {stage!r}; expected one of: {available}"
        ) from error
    return suite, stage_config


def resolve_screening_artifact(relative_path: str, config_path: str | Path | None = None) -> Path:
    base = Path(config_path).resolve().parent if config_path else PROTOCOL_ROOT / "screening"
    artifact = (base / relative_path).resolve()
    if base.resolve() not in artifact.parents:
        raise ValueError(f"Screening artifact escapes protocol directory: {relative_path}")
    return artifact


def resolve_suite_artifact(relative_path: str) -> Path:
    artifact = (SCREENING_ROOT / relative_path).resolve()
    if SCREENING_ROOT.resolve() not in artifact.parents:
        raise ValueError(f"Suite artifact escapes screening directory: {relative_path}")
    return artifact
