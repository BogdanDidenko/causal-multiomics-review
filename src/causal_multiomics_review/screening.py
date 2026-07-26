from __future__ import annotations

import csv
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .audit import git_revision, sha256_file, write_manifest
from .config import (
    DEFAULT_SUITE_CONFIG,
    REPO_ROOT,
    load_gate_config,
    load_json,
    load_stage_config,
    resolve_screening_artifact,
    resolve_suite_artifact,
)
from .gates import route_adjudicated, route_round_a
from .grading import (
    EvidenceReferenceError,
    build_ledger_fields,
    derive_evidence_level,
    derive_exclusion_code,
    validate_evidence_references,
)
from .llm import OpenAICompatibleProvider, ProviderError
from .schema import SchemaError, validate_object

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
    for field in ("record_id", "canonical_id", "source_record_id", "id", "doi", "pmid"):
        if str(record.get(field, "")).strip():
            return str(record[field]).strip()
    raise ValueError(
        "Record has no record_id, canonical_id, source_record_id, id, DOI, or PMID"
    )


def read_records(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def read_jsonl_records(path: str | Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with Path(path).open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as error:
                records.append(
                    {
                        "record_id": f"invalid-jsonl-line-{line_number:06d}",
                        "_input_error": f"JSONL line {line_number}: {error}",
                    }
                )
                continue
            if not isinstance(value, dict):
                records.append(
                    {
                        "record_id": f"invalid-jsonl-line-{line_number:06d}",
                        "_input_error": f"JSONL line {line_number} is not an object",
                    }
                )
                continue
            records.append(value)
    return records


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
            "temperature": getattr(provider, "temperature", 0),
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


class RoleExecutionError(RuntimeError):
    def __init__(self, role: str, errors: list[str]) -> None:
        self.role = role
        self.errors = errors
        super().__init__(f"{role} failed after {len(errors)} attempts: {errors[-1]}")


def run_stage_screening(
    input_path: str | Path,
    output_dir: str | Path,
    provider: OpenAICompatibleProvider,
    stage: str = "title_abstract",
    suite_config_path: str | Path | None = None,
    limit: int | None = None,
    resume: bool = False,
) -> dict[str, int]:
    config_path = Path(suite_config_path or DEFAULT_SUITE_CONFIG).resolve()
    suite, stage_config = load_stage_config(stage, config_path)
    records: list[dict[str, Any]]
    if stage_config["input_format"] == "csv":
        records = list(read_records(input_path))
    elif stage_config["input_format"] == "jsonl":
        records = read_jsonl_records(input_path)
    else:
        raise ValueError(f"Unsupported input format: {stage_config['input_format']}")
    if limit is not None:
        records = records[:limit]

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    result_path = output / "screening_results.jsonl"
    raw_path = output / "raw_provider_responses.jsonl"
    completed_ids = _completed_record_ids(result_path) if resume else set()
    mode = "a" if resume else "w"
    artifacts = _load_stage_artifacts(stage_config)
    counts = _existing_decision_counts(result_path) if resume else {}
    processed_now = 0

    with result_path.open(mode, encoding="utf-8") as results, raw_path.open(
        mode, encoding="utf-8"
    ) as raw_results:
        for position, source_record in enumerate(records, start=1):
            record = source_record
            try:
                identifier = record_id(record)
            except ValueError as error:
                identifier = f"invalid-{stage}-record-{position:06d}"
                record = {**record, "record_id": identifier, "_input_error": str(error)}
            if identifier in completed_ids:
                continue
            processed_now += 1
            try:
                if record.get("_input_error"):
                    result = _manual_review_result(
                        record,
                        stage,
                        "invalid_input_record",
                        {"error": str(record["_input_error"])},
                    )
                elif not str(record.get("abstract", "")).strip():
                    result = _manual_review_result(
                        record,
                        stage,
                        "missing_abstract",
                    )
                elif stage == "title_abstract":
                    result = _process_title_abstract_record(
                        record,
                        stage_config,
                        artifacts,
                        provider,
                        raw_results,
                        suite["runtime"]["max_retries"],
                    )
                elif stage == "full_text":
                    result = _process_full_text_record(
                        record,
                        stage_config,
                        artifacts,
                        provider,
                        raw_results,
                        suite["runtime"]["max_retries"],
                    )
                else:
                    raise ValueError(f"Unsupported stage: {stage}")
            except RoleExecutionError as error:
                result = _manual_review_result(
                    record,
                    stage,
                    "role_execution_failed",
                    {"role": error.role, "errors": error.errors},
                )
            except (ValueError, EvidenceReferenceError) as error:
                result = _manual_review_result(
                    record,
                    stage,
                    "record_validation_failed",
                    {"error": str(error)},
                )

            results.write(json.dumps(result, ensure_ascii=False) + "\n")
            results.flush()
            decision = str(result["final_decision"])
            counts[decision] = counts.get(decision, 0) + 1

    write_manifest(
        output / "manifest.json",
        {
            "git_revision": git_revision(REPO_ROOT),
            "suite_id": suite["suite_id"],
            "suite_version": suite["suite_version"],
            "stage": stage,
            "suite_config_path": str(config_path.relative_to(REPO_ROOT)),
            "suite_config_sha256": sha256_file(config_path),
            "input_path": str(Path(input_path).resolve()),
            "input_sha256": sha256_file(input_path),
            "model": provider.model,
            "provider_url": provider.url,
            "runtime": _provider_runtime(provider),
            "artifacts": _manifest_artifacts(artifacts),
            "resume": resume,
            "input_record_count": len(records),
            "processed_now": processed_now,
            "decision_counts": counts,
        },
    )
    return counts


def _process_title_abstract_record(
    record: dict[str, Any],
    stage_config: dict[str, Any],
    artifacts: dict[str, dict[str, Any]],
    provider: OpenAICompatibleProvider,
    raw_results: Any,
    max_retries: int,
) -> dict[str, Any]:
    answers: dict[str, dict[str, Any]] = {}
    for role in stage_config["roles"]:
        prompt = render_prompt(artifacts[role]["prompt"], record)
        answers[role] = _call_role(
            provider,
            role,
            prompt,
            artifacts[role]["schema"],
            record_id(record),
            raw_results,
            max_retries,
        )

    route, role_gates = route_round_a(answers, stage_config)
    adjudication = None
    selected = _merge_answers(*answers.values())
    if route == "adjudicate":
        extra = {
            "SCOPE_REVIEW": json.dumps(answers["scope_reviewer"], ensure_ascii=False),
            "CAUSAL_REVIEW": json.dumps(
                answers["causal_design_reviewer"], ensure_ascii=False
            ),
        }
        prompt = render_prompt(artifacts["adjudicator"]["prompt"], record, extra)
        adjudication = _call_role(
            provider,
            "adjudicator",
            prompt,
            artifacts["adjudicator"]["schema"],
            record_id(record),
            raw_results,
            max_retries,
        )
        route, adjudicator_gate = route_adjudicated(adjudication, stage_config)
        role_gates["adjudicator"] = adjudicator_gate
        selected = adjudication
        if adjudication.get("resolution_status") == "conflict_unresolved":
            route = "manual_review"

    return {
        "record_id": record_id(record),
        "stage": "title_abstract",
        "title": record.get("title", ""),
        "round_a": answers,
        "gates": role_gates,
        "adjudication": adjudication,
        "selected_criteria": selected,
        "final_decision": route,
        "final_exclusion_code": derive_exclusion_code(selected) if route == "exclude" else "none",
    }


def _process_full_text_record(
    record: dict[str, Any],
    stage_config: dict[str, Any],
    artifacts: dict[str, dict[str, Any]],
    provider: OpenAICompatibleProvider,
    raw_results: Any,
    max_retries: int,
) -> dict[str, Any]:
    sections = record.get("sections")
    if not isinstance(sections, list) or not sections:
        return _manual_review_result(record, "full_text", "missing_full_text_sections")
    valid_section_ids = _validate_sections(sections)
    selector_prompt = render_prompt(
        artifacts["section_selector"]["prompt"],
        record,
        {"SECTION_CATALOG": _format_sections(sections)},
    )
    selection = _call_role(
        provider,
        "section_selector",
        selector_prompt,
        artifacts["section_selector"]["schema"],
        record_id(record),
        raw_results,
        max_retries,
        lambda answer: validate_evidence_references(answer, valid_section_ids),
    )
    if selection["coverage_status"] != "sufficient":
        return _manual_review_result(
            record,
            "full_text",
            "insufficient_selected_full_text",
            {"section_selection": selection},
        )

    selected_ids = {
        item["section_id"] for item in selection["selected_sections"]
    }
    selected_sections = [
        section for section in sections if section["section_id"] in selected_ids
    ]
    selected_context = _format_sections(selected_sections)
    answers: dict[str, dict[str, Any]] = {}

    eligibility_prompt = render_prompt(
        artifacts["eligibility_reviewer"]["prompt"],
        record,
        {"SELECTED_SECTIONS": selected_context},
    )
    answers["eligibility_reviewer"] = _call_role(
        provider,
        "eligibility_reviewer",
        eligibility_prompt,
        artifacts["eligibility_reviewer"]["schema"],
        record_id(record),
        raw_results,
        max_retries,
        lambda answer: validate_evidence_references(answer, selected_ids),
    )

    causal_prompt = render_prompt(
        artifacts["causal_evidence_reviewer"]["prompt"],
        record,
        {
            "SELECTED_SECTIONS": selected_context,
            "ELIGIBILITY_REVIEW": json.dumps(
                answers["eligibility_reviewer"], ensure_ascii=False
            ),
        },
    )
    answers["causal_evidence_reviewer"] = _call_role(
        provider,
        "causal_evidence_reviewer",
        causal_prompt,
        artifacts["causal_evidence_reviewer"]["schema"],
        record_id(record),
        raw_results,
        max_retries,
        lambda answer: validate_evidence_references(answer, selected_ids),
    )

    route, role_gates = route_round_a(answers, stage_config)
    adjudication = None
    selected = _merge_answers(*answers.values())
    if route == "adjudicate":
        prompt = render_prompt(
            artifacts["adjudicator"]["prompt"],
            record,
            {
                "SELECTED_SECTIONS": selected_context,
                "ELIGIBILITY_REVIEW": json.dumps(
                    answers["eligibility_reviewer"], ensure_ascii=False
                ),
                "CAUSAL_REVIEW": json.dumps(
                    answers["causal_evidence_reviewer"], ensure_ascii=False
                ),
            },
        )
        adjudication = _call_role(
            provider,
            "adjudicator",
            prompt,
            artifacts["adjudicator"]["schema"],
            record_id(record),
            raw_results,
            max_retries,
            lambda answer: validate_evidence_references(answer, selected_ids),
        )
        route, adjudicator_gate = route_adjudicated(adjudication, stage_config)
        role_gates["adjudicator"] = adjudicator_gate
        selected = adjudication

    grade = derive_evidence_level(selected)
    if route == "manual_review" or grade is None:
        final_decision = "manual_review"
        ledger_fields = None
        level = None
        label = "pending"
    else:
        level, label = grade
        final_decision = "assessed"
        ledger_fields = build_ledger_fields(selected, level, label)

    return {
        "record_id": record_id(record),
        "stage": "full_text",
        "title": record.get("title", ""),
        "section_selection": selection,
        "round_a": answers,
        "gates": role_gates,
        "adjudication": adjudication,
        "selected_criteria": selected,
        "causal_evidence_level": level,
        "final_study_label": label,
        "ledger_fields": ledger_fields,
        "final_exclusion_code": derive_exclusion_code(selected),
        "final_decision": final_decision,
    }


def _call_role(
    provider: OpenAICompatibleProvider,
    role: str,
    prompt: str,
    schema: dict[str, Any],
    identifier: str,
    raw_results: Any,
    max_retries: int,
    post_validate: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    errors: list[str] = []
    for attempt in range(max_retries + 1):
        raw: Any | None = None
        attempt_prompt = prompt
        if attempt:
            attempt_prompt += (
                "\n\nCORRECTION: The previous response failed validation: "
                f"{errors[-1]}. Return a corrected JSON object only."
            )
        try:
            answer, raw = provider.complete_json(
                attempt_prompt,
                schema=schema,
                schema_name=role,
            )
            validate_object(answer, schema)
            if post_validate:
                post_validate(answer)
            raw_results.write(
                json.dumps(
                    {
                        "record_id": identifier,
                        "role": role,
                        "attempt": attempt + 1,
                        "status": "ok",
                        "response": raw,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
            raw_results.flush()
            return answer
        except (ProviderError, SchemaError, EvidenceReferenceError, ValueError) as error:
            errors.append(str(error))
            failed_response = raw
            if isinstance(error, ProviderError) and error.raw_response is not None:
                failed_response = error.raw_response
            audit_row = {
                "record_id": identifier,
                "role": role,
                "attempt": attempt + 1,
                "status": "error",
                "error": str(error),
            }
            if failed_response is not None:
                audit_row["response"] = failed_response
            raw_results.write(
                json.dumps(
                    audit_row,
                    ensure_ascii=False,
                )
                + "\n"
            )
            raw_results.flush()
    raise RoleExecutionError(role, errors)


def _load_stage_artifacts(stage_config: dict[str, Any]) -> dict[str, dict[str, Any]]:
    role_configs: dict[str, dict[str, Any]] = dict(stage_config["roles"])
    role_configs["adjudicator"] = stage_config["adjudication"]
    if "section_selector" in stage_config:
        role_configs["section_selector"] = stage_config["section_selector"]

    artifacts: dict[str, dict[str, Any]] = {}
    for role, role_config in role_configs.items():
        prompt_path = resolve_suite_artifact(role_config["prompt"])
        schema_path = resolve_suite_artifact(role_config["schema"])
        artifacts[role] = {
            "prompt_path": prompt_path,
            "schema_path": schema_path,
            "prompt": prompt_path.read_text(encoding="utf-8"),
            "schema": load_json(schema_path),
        }
    return artifacts


def _manifest_artifacts(
    artifacts: dict[str, dict[str, Any]],
) -> dict[str, dict[str, str]]:
    return {
        role: {
            "prompt_path": str(artifact["prompt_path"].relative_to(REPO_ROOT)),
            "prompt_sha256": sha256_file(artifact["prompt_path"]),
            "schema_path": str(artifact["schema_path"].relative_to(REPO_ROOT)),
            "schema_sha256": sha256_file(artifact["schema_path"]),
        }
        for role, artifact in artifacts.items()
    }


def _provider_runtime(provider: OpenAICompatibleProvider) -> dict[str, Any]:
    return {
        "api_protocol": getattr(provider, "api_protocol", "unknown"),
        "temperature": getattr(provider, "temperature", None),
        "top_p": getattr(provider, "top_p", None),
        "seed": getattr(provider, "seed", None),
        "n": getattr(provider, "n", None),
        "max_tokens": getattr(provider, "max_tokens", None),
        "response_format": getattr(provider, "response_format", None),
        "reasoning_effort": getattr(provider, "reasoning_effort", None),
        "text_verbosity": getattr(provider, "text_verbosity", None),
        "context_window": getattr(provider, "context_window", None),
        "codex_bin": getattr(provider, "codex_bin", None),
        "codex_cli_version": getattr(provider, "codex_version", None),
        "codex_timeout_seconds": getattr(provider, "timeout", None),
        "sandbox": getattr(provider, "sandbox", None),
        "approval_policy": getattr(provider, "approval_policy", None),
        "ephemeral": getattr(provider, "ephemeral", None),
        "ignore_user_config": getattr(provider, "ignore_user_config", None),
        "ignore_rules": getattr(provider, "ignore_rules", None),
        "isolated_home": getattr(provider, "isolated_home", None),
    }


def _merge_answers(*answers: dict[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    evidence: list[dict[str, Any]] = []
    for answer in answers:
        for key, value in answer.items():
            if key == "evidence_spans":
                evidence.extend(value)
            elif key in {"uncertainty_reason", "concise_rationale"} and key in merged:
                merged[key] = " | ".join(filter(None, [str(merged[key]), str(value)]))
            else:
                merged[key] = value
    if evidence:
        merged["evidence_spans"] = evidence
    return merged


def _validate_sections(sections: list[Any]) -> set[str]:
    identifiers: list[str] = []
    for index, section in enumerate(sections):
        if not isinstance(section, dict):
            raise ValueError(f"Section {index} is not an object")
        identifier = str(section.get("section_id", "")).strip()
        if not identifier:
            raise ValueError(f"Section {index} has no section_id")
        if not str(section.get("text", "")).strip():
            raise ValueError(f"Section {identifier} has no text")
        identifiers.append(identifier)
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("Full-text section IDs must be unique")
    return set(identifiers)


def _format_sections(sections: list[dict[str, Any]]) -> str:
    blocks = []
    for section in sections:
        identifier = str(section["section_id"])
        heading = str(section.get("heading", ""))
        text = str(section.get("text", ""))
        blocks.append(
            f'<section id="{identifier}" heading="{heading}">\n{text}\n</section>'
        )
    return "\n\n".join(blocks)


def _manual_review_result(
    record: dict[str, Any],
    stage: str,
    reason: str,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "record_id": record_id(record),
        "stage": stage,
        "title": record.get("title", ""),
        "final_decision": "manual_review",
        "manual_review_reason": reason,
        "manual_review_details": details or {},
    }


def _completed_record_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    with path.open(encoding="utf-8") as handle:
        return {
            str(row["record_id"])
            for line in handle
            if line.strip() and (row := json.loads(line))
        }


def _existing_decision_counts(path: Path) -> dict[str, int]:
    counts: dict[str, int] = {}
    if not path.exists():
        return counts
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            decision = str(json.loads(line)["final_decision"])
            counts[decision] = counts.get(decision, 0) + 1
    return counts
