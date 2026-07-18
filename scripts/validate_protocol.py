#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "protocol"
REQUIRED_PLACEHOLDERS = {"{{RECORD_ID}}", "{{TITLE}}", "{{ABSTRACT}}"}


def load_object(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def main() -> None:
    errors: list[str] = []
    search = load_object(PROTOCOL / "search_config.json")
    databases = search.get("databases", {})
    if not isinstance(databases, dict) or len(databases) != 7:
        errors.append("search_config.json must define exactly seven databases")
    else:
        for name, raw_config in databases.items():
            config = raw_config if isinstance(raw_config, dict) else {}
            query_path = PROTOCOL / str(config.get("query_file", ""))
            if not query_path.is_file() or not query_path.read_text(encoding="utf-8").strip():
                errors.append(f"{name}: missing or empty query file {query_path}")

    gate_path = PROTOCOL / "screening" / "gate_config.json"
    gate = load_object(gate_path)
    roles = {**gate.get("round_a", {}), "adjudicator": gate.get("adjudication", {})}
    for role, raw_config in roles.items():
        config = raw_config if isinstance(raw_config, dict) else {}
        for kind in ("prompt", "schema"):
            artifact = gate_path.parent / str(config.get(kind, ""))
            if not artifact.is_file():
                errors.append(f"{role}: missing {kind} artifact {artifact}")
        prompt = gate_path.parent / str(config.get("prompt", ""))
        if prompt.is_file() and role != "adjudicator":
            missing = REQUIRED_PLACEHOLDERS - set(prompt.read_text(encoding="utf-8").split())
            if missing:
                errors.append(f"{role}: missing prompt placeholders {sorted(missing)}")

    for path in PROTOCOL.rglob("*"):
        if path.is_file() and path.suffix in {".md", ".txt", ".json"}:
            text = path.read_text(encoding="utf-8")
            if "/Users/" in text:
                errors.append(f"absolute local path found in {path.relative_to(ROOT)}")

    if errors:
        raise SystemExit("Protocol validation failed:\n- " + "\n- ".join(errors))
    print(f"protocol_ok databases={len(databases)} roles={len(roles)}")


if __name__ == "__main__":
    main()
