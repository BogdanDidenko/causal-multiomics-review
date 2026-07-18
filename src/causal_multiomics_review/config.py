from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_ROOT = REPO_ROOT / "protocol"


def load_json(path: str | Path) -> dict[str, Any]:
    with Path(path).open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object in {path}")
    return value


def load_gate_config(path: str | Path | None = None) -> dict[str, Any]:
    return load_json(path or PROTOCOL_ROOT / "screening" / "gate_config.json")


def resolve_screening_artifact(relative_path: str, config_path: str | Path | None = None) -> Path:
    base = Path(config_path).resolve().parent if config_path else PROTOCOL_ROOT / "screening"
    artifact = (base / relative_path).resolve()
    if base.resolve() not in artifact.parents:
        raise ValueError(f"Screening artifact escapes protocol directory: {relative_path}")
    return artifact
