#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "protocol"
REQUIRED_PLACEHOLDERS = {"{{RECORD_ID}}", "{{TITLE}}", "{{ABSTRACT}}"}


def load_object(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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
            prompt_text = prompt.read_text(encoding="utf-8")
            missing = {
                placeholder
                for placeholder in REQUIRED_PLACEHOLDERS
                if placeholder not in prompt_text
            }
            if missing:
                errors.append(f"{role}: missing prompt placeholders {sorted(missing)}")

    screening_root = PROTOCOL / "screening"
    suite_path = screening_root / "configs" / "prompt_suite_v0.7.0.json"
    suite = load_object(suite_path)
    expected_runtime = {
        "provider_protocol": "codex_cli",
        "reasoning_effort": "medium",
        "context_window": 32768,
        "codex_timeout_seconds": 900,
        "max_retries": 1,
    }
    for field, expected in expected_runtime.items():
        if suite.get("runtime", {}).get(field) != expected:
            errors.append(f"suite runtime {field} must be {expected}")
    expected_provider = {
        "protocol": "codex_cli",
        "codex_cli_version": "codex-cli 0.145.0",
        "model": "gpt-5.6-terra",
        "display_name": "GPT 5.6 Terra Medium",
        "sandbox": "read-only",
        "approval_policy": "never",
        "ephemeral": True,
        "ignore_user_config": True,
        "ignore_rules": True,
        "isolated_home": True,
    }
    for field, expected in expected_provider.items():
        if suite.get("provider", {}).get(field) != expected:
            errors.append(f"suite provider {field} must be {expected}")
    stability_policy = suite.get("stability_policy", {})
    if stability_policy.get("model") != "gpt-5.6-terra":
        errors.append("stability policy must use gpt-5.6-terra")
    if stability_policy.get("repeats") != 5:
        errors.append("stability policy must require five runs")
    expected_agents = [
        "scope_reviewer",
        "causal_design_reviewer",
        "title_abstract_adjudicator",
        "section_selector",
        "fulltext_eligibility_reviewer",
        "causal_evidence_reviewer",
        "fulltext_adjudicator",
    ]
    if stability_policy.get("agent_stages") != expected_agents:
        errors.append("stability policy must cover all seven agent stages")
    required_acceptance = {
        "schema_success_rate": 1.0,
        "final_decision_exact_agreement": 1.0,
        "decisive_criteria_exact_agreement": 1.0,
        "causal_evidence_level_exact_agreement": 1.0,
        "manual_review_rate": 0.0,
    }
    if stability_policy.get("acceptance") != required_acceptance:
        errors.append("stability policy acceptance thresholds are not exact")
    for stage, raw_stage_config in suite.get("stages", {}).items():
        stage_config = raw_stage_config if isinstance(raw_stage_config, dict) else {}
        artifact_configs = dict(stage_config.get("roles", {}))
        artifact_configs["adjudicator"] = stage_config.get("adjudication", {})
        if "section_selector" in stage_config:
            artifact_configs["section_selector"] = stage_config["section_selector"]
        for role, raw_config in artifact_configs.items():
            config = raw_config if isinstance(raw_config, dict) else {}
            prompt_path = screening_root / str(config.get("prompt", ""))
            schema_path = screening_root / str(config.get("schema", ""))
            if not prompt_path.is_file():
                errors.append(f"{stage}.{role}: missing prompt {prompt_path}")
                continue
            if not schema_path.is_file():
                errors.append(f"{stage}.{role}: missing schema {schema_path}")
                continue
            prompt_text = prompt_path.read_text(encoding="utf-8")
            missing = {
                placeholder
                for placeholder in REQUIRED_PLACEHOLDERS
                if placeholder not in prompt_text
            }
            if missing:
                errors.append(f"{stage}.{role}: missing placeholders {sorted(missing)}")
            if "PROMPT_ID:" not in prompt_text or "PROMPT_VERSION:" not in prompt_text:
                errors.append(f"{stage}.{role}: prompt lacks ID/version headers")
            if "STABILITY CONTRACT" not in prompt_text:
                errors.append(f"{stage}.{role}: prompt lacks stability contract")
            try:
                Draft202012Validator.check_schema(load_object(schema_path))
            except Exception as error:
                errors.append(f"{stage}.{role}: invalid JSON schema: {error}")

    required_extra_placeholders = {
        "full_text.section_selector": {"{{SECTION_CATALOG}}"},
        "full_text.eligibility_reviewer": {"{{SELECTED_SECTIONS}}"},
        "full_text.causal_evidence_reviewer": {
            "{{SELECTED_SECTIONS}}",
            "{{ELIGIBILITY_REVIEW}}",
        },
        "full_text.adjudicator": {
            "{{SELECTED_SECTIONS}}",
            "{{ELIGIBILITY_REVIEW}}",
            "{{CAUSAL_REVIEW}}",
        },
        "title_abstract.adjudicator": {"{{SCOPE_REVIEW}}", "{{CAUSAL_REVIEW}}"},
    }
    for key, placeholders in required_extra_placeholders.items():
        stage, role = key.split(".", 1)
        stage_config = suite["stages"][stage]
        role_config = (
            stage_config.get(role)
            or stage_config.get("roles", {}).get(role)
            or stage_config.get("adjudication")
        )
        prompt_path = screening_root / role_config["prompt"]
        prompt_text = prompt_path.read_text(encoding="utf-8")
        missing = {
            placeholder for placeholder in placeholders if placeholder not in prompt_text
        }
        if missing:
            errors.append(f"{key}: missing placeholders {sorted(missing)}")

    manifest_path = screening_root / "prompt_manifest.json"
    manifest = load_object(manifest_path)
    config_entry = manifest.get("suite_config", {})
    if sha256(suite_path) != config_entry.get("sha256"):
        errors.append("prompt_manifest.json has a stale suite config hash")
    for artifact in manifest.get("artifacts", []):
        prompt_path = screening_root / artifact["prompt_path"]
        schema_path = screening_root / artifact["schema_path"]
        if sha256(prompt_path) != artifact["prompt_sha256"]:
            errors.append(f"stale prompt hash for {artifact['prompt_id']}")
        if sha256(schema_path) != artifact["schema_sha256"]:
            errors.append(f"stale schema hash for {artifact['prompt_id']}")
        prompt_text = prompt_path.read_text(encoding="utf-8")
        if f"PROMPT_VERSION: {artifact['version']}" not in prompt_text:
            errors.append(f"manifest version mismatch for {artifact['prompt_id']}")

    benchmark_dir = screening_root / "benchmarks" / "candidates"
    benchmark_manifest = load_object(benchmark_dir / "manifest.json")
    expected_benchmark_version = (
        f"{benchmark_manifest.get('benchmark_version')}_annotation_pending"
    )
    if manifest.get("benchmark_version") != expected_benchmark_version:
        errors.append(
            "prompt manifest benchmark version does not match candidate manifest"
        )
    benchmark_counts = {
        "high_signal_development_25.csv": 25,
        "title_abstract_regression_116.csv": 116,
        "full_text_benchmark_60.csv": 60,
        "section_selector_gold_20.csv": 20,
    }
    expected_strata = {
        "title_abstract_regression_116.csv": {
            "candidate_levels_2_to_4": 42,
            "candidate_exclusion": 42,
            "candidate_boundary_or_unclear": 32,
        },
        "full_text_benchmark_60.csv": {
            "prior_level_0": 2,
            "prior_level_1": 2,
            "prior_level_2": 11,
            "prior_level_3": 22,
            "prior_level_4": 23,
        },
    }
    for filename, expected_count in benchmark_counts.items():
        path = benchmark_dir / filename
        if not path.is_file():
            errors.append(f"missing benchmark candidate set {filename}")
            continue
        with path.open(newline="", encoding="utf-8-sig") as handle:
            rows = list(csv.DictReader(handle))
        actual_count = len(rows)
        if actual_count != expected_count:
            errors.append(
                f"{filename}: expected {expected_count} records, found {actual_count}"
            )
        expected_hash = benchmark_manifest.get("output_sha256", {}).get(filename)
        if expected_hash != sha256(path):
            errors.append(f"{filename}: stale or missing candidate manifest hash")
        if filename == "high_signal_development_25.csv":
            incomplete = [
                row.get("canonical_id", "")
                for row in rows
                if not row.get("title", "").strip()
                or not row.get("abstract", "").strip()
            ]
            if incomplete:
                errors.append(
                    f"{filename}: title/abstract required for {len(incomplete)} records"
                )
        if filename in expected_strata:
            actual_strata = Counter(row.get("sampling_stratum", "") for row in rows)
            if dict(actual_strata) != expected_strata[filename]:
                errors.append(
                    f"{filename}: expected strata {expected_strata[filename]}, "
                    f"found {dict(actual_strata)}"
                )

    for path in PROTOCOL.rglob("*"):
        if path.is_file() and path.suffix in {".md", ".txt", ".json"}:
            text = path.read_text(encoding="utf-8")
            if "/Users/" in text:
                errors.append(f"absolute local path found in {path.relative_to(ROOT)}")

    if errors:
        raise SystemExit("Protocol validation failed:\n- " + "\n- ".join(errors))
    print(
        f"protocol_ok databases={len(databases)} legacy_roles={len(roles)} "
        f"suite_stages={len(suite['stages'])} suite_prompts={len(manifest['artifacts'])}"
    )


if __name__ == "__main__":
    main()
