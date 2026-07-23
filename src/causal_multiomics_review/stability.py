from __future__ import annotations

import json
from typing import Any

TITLE_DECISIVE_PATHS = (
    "round_a.scope_reviewer.report_type",
    "round_a.scope_reviewer.bio_health_scope",
    "round_a.scope_reviewer.multiomics_status",
    "round_a.scope_reviewer.integration_mode",
    "round_a.causal_design_reviewer.causal_claim_present",
    "round_a.causal_design_reviewer.identification_status",
    "round_a.causal_design_reviewer.design_families",
    "round_a.causal_design_reviewer.design_role",
    "adjudication.report_type",
    "adjudication.bio_health_scope",
    "adjudication.multiomics_status",
    "adjudication.integration_mode",
    "adjudication.identification_status",
    "adjudication.design_families",
    "adjudication.design_role",
    "selected_criteria.report_type",
    "selected_criteria.bio_health_scope",
    "selected_criteria.multiomics_status",
    "selected_criteria.integration_mode",
    "selected_criteria.identification_status",
    "selected_criteria.design_families",
    "selected_criteria.design_role",
    "final_decision",
    "final_exclusion_code",
)

FULL_TEXT_DECISIVE_PATHS = (
    "section_selection.selected_sections",
    "section_selection.coverage_status",
    "round_a.eligibility_reviewer.empirical_primary",
    "round_a.eligibility_reviewer.bio_health_scope",
    "round_a.eligibility_reviewer.multiomics_status",
    "round_a.eligibility_reviewer.date_eligible",
    "round_a.eligibility_reviewer.english_language",
    "round_a.eligibility_reviewer.full_text_sufficient",
    "round_a.causal_evidence_reviewer.identification_status",
    "round_a.causal_evidence_reviewer.primary_design_family",
    "round_a.causal_evidence_reviewer.supporting_design_families",
    "round_a.causal_evidence_reviewer.estimand_complete",
    "round_a.causal_evidence_reviewer.assumptions_assessable",
    "round_a.causal_evidence_reviewer.validation_strength",
    "adjudication.empirical_primary",
    "adjudication.bio_health_scope",
    "adjudication.multiomics_status",
    "adjudication.identification_status",
    "adjudication.primary_design_family",
    "adjudication.estimand_complete",
    "adjudication.assumptions_assessable",
    "adjudication.validation_strength",
    "selected_criteria.empirical_primary",
    "selected_criteria.bio_health_scope",
    "selected_criteria.multiomics_status",
    "selected_criteria.date_eligible",
    "selected_criteria.english_language",
    "selected_criteria.full_text_sufficient",
    "selected_criteria.identification_status",
    "selected_criteria.primary_design_family",
    "selected_criteria.supporting_design_families",
    "selected_criteria.estimand_complete",
    "selected_criteria.assumptions_assessable",
    "selected_criteria.validation_strength",
    "causal_evidence_level",
    "final_study_label",
    "final_decision",
    "final_exclusion_code",
)


def decisive_paths(stage: str) -> tuple[str, ...]:
    if stage == "title_abstract":
        return TITLE_DECISIVE_PATHS
    if stage == "full_text":
        return FULL_TEXT_DECISIVE_PATHS
    raise ValueError(f"Unsupported screening stage: {stage}")


def assess_stability(
    run_results: dict[str, dict[str, dict[str, Any]]],
    stage: str,
    acceptance: dict[str, float],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if len(run_results) < 2:
        raise ValueError("Stability assessment requires at least two runs")
    labels = sorted(run_results)
    identifier_sets = [set(run_results[label]) for label in labels]
    if any(items != identifier_sets[0] for items in identifier_sets[1:]):
        raise ValueError("Stability runs contain different record IDs")

    paths = decisive_paths(stage)
    rows: list[dict[str, Any]] = []
    schema_successes = 0
    manual_results = 0
    for identifier in sorted(identifier_sets[0]):
        by_run = {label: run_results[label][identifier] for label in labels}
        values = {
            path: {label: _normalized_path(row, path) for label, row in by_run.items()}
            for path in paths
        }
        disagreements = {
            path: run_values
            for path, run_values in values.items()
            if len({_json(value) for value in run_values.values()}) > 1
        }
        manual_labels = [
            label
            for label, row in by_run.items()
            if row.get("final_decision") == "manual_review"
        ]
        schema_successes += sum(
            row.get("manual_review_reason") != "role_execution_failed"
            for row in by_run.values()
        )
        manual_results += len(manual_labels)
        rows.append(
            {
                "record_id": identifier,
                "stage": stage,
                "stable": not disagreements and not manual_labels,
                "decisive_criteria_stable": not disagreements,
                "final_decision_stable": "final_decision" not in disagreements,
                "causal_evidence_level_stable": (
                    "causal_evidence_level" not in disagreements
                    if stage == "full_text"
                    else True
                ),
                "manual_review_runs": manual_labels,
                "disagreements": disagreements,
            }
        )

    record_count = len(rows)
    run_count = len(labels)
    metrics = {
        "schema_success_rate": schema_successes / (record_count * run_count),
        "final_decision_exact_agreement": _rate(
            row["final_decision_stable"] for row in rows
        ),
        "decisive_criteria_exact_agreement": _rate(
            row["decisive_criteria_stable"] for row in rows
        ),
        "causal_evidence_level_exact_agreement": _rate(
            row["causal_evidence_level_stable"] for row in rows
        ),
        "manual_review_rate": manual_results / (record_count * run_count),
        "fully_stable_record_rate": _rate(row["stable"] for row in rows),
    }
    gates = {
        metric: {
            "value": metrics[metric],
            "threshold": threshold,
            "passed": (
                metrics[metric] <= threshold
                if metric == "manual_review_rate"
                else metrics[metric] >= threshold
            ),
        }
        for metric, threshold in acceptance.items()
    }
    return rows, {
        "stage": stage,
        "run_labels": labels,
        "record_count": record_count,
        "run_count": run_count,
        "metrics": metrics,
        "acceptance": {
            "overall": "pass" if all(gate["passed"] for gate in gates.values()) else "fail",
            "gates": gates,
        },
    }


def _normalized_path(row: dict[str, Any], path: str) -> Any:
    value: Any = row
    for part in path.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return _normalize(value)


def _normalize(value: Any) -> Any:
    if isinstance(value, list):
        return sorted((_normalize(item) for item in value), key=_json)
    if isinstance(value, dict):
        return {key: _normalize(item) for key, item in sorted(value.items())}
    return value


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _rate(values: Any) -> float:
    items = list(values)
    return sum(bool(item) for item in items) / len(items) if items else 0.0
