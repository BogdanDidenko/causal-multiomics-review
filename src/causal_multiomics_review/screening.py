from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from .audit import git_revision, sha256_file, write_manifest
from .config import REPO_ROOT, load_gate_config, load_json, resolve_screening_artifact
from .gates import route_adjudicated, route_round_a
from .llm import OpenAICompatibleProvider
from .schema import validate_object

PLACEHOLDERS = ("RECORD_ID", "TITLE", "ABSTRACT", "YEAR", "SOURCE")


def render_prompt(
    template: str,
    record: dict[str, Any],
    extra: dict[str, str] | None = None,
) -> str:
    values = {
        "RECORD_ID": record_id(record),
        "TITLE": str(record.get("title", "")),
        "ABSTRACT": str(record.get("abstract", "")),
        "YEAR": str(record.get("year", "")),
        "SOURCE": str(record.get("source", record.get("provenance_sources", ""))),
        **(extra or {}),
    }
    rendered = template
    for key, value in values.items():
        rendered = rendered.replace("{{" + key + "}}", value)
    return rendered


def record_id(record: dict[str, Any]) -> str:
    for field in ("record_id", "id", "doi", "pmid"):
        if str(record.get(field, "")).strip():
            return str(record[field]).strip()
    raise ValueError("Record has no record_id, id, DOI, or PMID")


def read_records(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def run_screening(
    input_path: str | Path,
    output_dir: str | Path,
    provider: OpenAICompatibleProvider,
    config_path: str | Path | None = None,
    limit: int | None = None,
) -> dict[str, int]:
    config_path = Path(config_path).resolve() if config_path else None
    config = load_gate_config(config_path)
    records = read_records(input_path)
    if limit is not None:
        records = records[:limit]

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    result_path = output / "screening_results.jsonl"
    raw_path = output / "raw_provider_responses.jsonl"
    counts: dict[str, int] = {}

    artifacts: dict[str, dict[str, Any]] = {}
    for role, role_config in {**config["round_a"], "adjudicator": config["adjudication"]}.items():
        prompt_path = resolve_screening_artifact(role_config["prompt"], config_path)
        schema_path = resolve_screening_artifact(role_config["schema"], config_path)
        artifacts[role] = {
            "prompt_path": str(prompt_path.relative_to(REPO_ROOT)),
            "prompt_sha256": sha256_file(prompt_path),
            "schema_path": str(schema_path.relative_to(REPO_ROOT)),
            "schema_sha256": sha256_file(schema_path),
            "prompt": prompt_path.read_text(encoding="utf-8"),
            "schema": load_json(schema_path),
        }

    with result_path.open("w", encoding="utf-8") as results, raw_path.open(
        "w", encoding="utf-8"
    ) as raw_results:
        for record in records:
            answers: dict[str, dict[str, Any]] = {}
            role_gates: dict[str, str] = {}
            for role in config["round_a"]:
                prompt = render_prompt(artifacts[role]["prompt"], record)
                answer, raw = provider.complete_json(prompt)
                validate_object(answer, artifacts[role]["schema"])
                answers[role] = answer
                raw_results.write(
                    json.dumps(
                        {"record_id": record_id(record), "role": role, "response": raw}
                    )
                    + "\n"
                )

            route, decisions = route_round_a(answers, config)
            role_gates.update(decisions)
            adjudication = None
            if route == "adjudicate":
                extra = {
                    "SCOPE_REVIEW": json.dumps(answers["scope_reviewer"], ensure_ascii=False),
                    "CAUSAL_REVIEW": json.dumps(
                        answers["causal_design_reviewer"], ensure_ascii=False
                    ),
                }
                prompt = render_prompt(artifacts["adjudicator"]["prompt"], record, extra)
                adjudication, raw = provider.complete_json(prompt)
                validate_object(adjudication, artifacts["adjudicator"]["schema"])
                raw_results.write(
                    json.dumps(
                        {
                            "record_id": record_id(record),
                            "role": "adjudicator",
                            "response": raw,
                        }
                    )
                    + "\n"
                )
                route, adjudication_gate = route_adjudicated(adjudication, config)
                role_gates["adjudicator"] = adjudication_gate

            result = {
                "record_id": record_id(record),
                "title": record.get("title", ""),
                "round_a": answers,
                "gates": role_gates,
                "adjudication": adjudication,
                "final_decision": route,
            }
            results.write(json.dumps(result, ensure_ascii=False) + "\n")
            counts[route] = counts.get(route, 0) + 1
            results.flush()
            raw_results.flush()

    write_manifest(
        output / "manifest.json",
        {
            "git_revision": git_revision(REPO_ROOT),
            "input_path": str(Path(input_path).resolve()),
            "input_sha256": sha256_file(input_path),
            "model": provider.model,
            "provider_url": provider.url,
            "temperature": 0,
            "gate_config_sha256": sha256_file(
                config_path or REPO_ROOT / "protocol" / "screening" / "gate_config.json"
            ),
            "artifacts": {
                role: {
                    key: value
                    for key, value in artifact.items()
                    if key not in {"prompt", "schema"}
                }
                for role, artifact in artifacts.items()
            },
            "record_count": len(records),
            "decision_counts": counts,
        },
    )
    return counts
