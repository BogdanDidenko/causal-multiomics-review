from __future__ import annotations

from typing import Any

TITLE_ACCEPTANCE = {
    "canonical_positive_retention": (">=", 1.0),
    "sensitivity": (">=", 0.98),
    "direct_exclusion_precision": (">=", 0.95),
    "structured_response_success_rate": (">=", 1.0),
}

FULL_TEXT_ACCEPTANCE = {
    "eligibility_sensitivity": (">=", 0.95),
    "design_family_macro_f1": (">=", 0.85),
    "exact_level_agreement": (">=", 0.80),
    "quadratic_weighted_kappa": (">=", 0.80),
    "within_one_level_agreement": (">=", 0.95),
    "unsupported_section_citations": ("==", 0),
}


def ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def evaluate_title(
    expected: dict[str, dict[str, str]],
    predicted: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    labeled = [
        (identifier, row)
        for identifier, row in expected.items()
        if row.get("expert_expected_decision")
    ]
    positives = [
        identifier
        for identifier, row in labeled
        if row["expert_expected_decision"] in {"seek_full_text", "manual_review"}
    ]
    exclusions = [
        identifier
        for identifier, row in labeled
        if row["expert_expected_decision"] == "exclude"
    ]
    retained = sum(
        predicted[item]["final_decision"] != "exclude"
        for item in positives
        if item in predicted
    )
    labeled_ids = {identifier for identifier, _ in labeled}
    predicted_exclusions = [
        item
        for item in predicted
        if item in labeled_ids and predicted[item]["final_decision"] == "exclude"
    ]
    correct_exclusions = sum(item in exclusions for item in predicted_exclusions)
    canonical_positives = [
        identifier
        for identifier, row in labeled
        if row.get("expert_canonical_positive", "").strip().lower()
        in {"1", "true", "yes"}
    ]
    canonical_retained = sum(
        predicted[item]["final_decision"] != "exclude"
        for item in canonical_positives
        if item in predicted
    )
    attempted = [
        row
        for row in predicted.values()
        if row.get("manual_review_reason") != "missing_abstract"
    ]
    structured_successes = sum(
        row.get("manual_review_reason") != "role_execution_failed" for row in attempted
    )
    return {
        "labeled_records": len(labeled),
        "positive_records": len(positives),
        "sensitivity": ratio(retained, len(positives)) if positives else None,
        "canonical_positive_records": len(canonical_positives),
        "canonical_positive_retention": (
            ratio(canonical_retained, len(canonical_positives))
            if canonical_positives
            else None
        ),
        "predicted_exclusions": len(predicted_exclusions),
        "direct_exclusion_precision": (
            ratio(correct_exclusions, len(predicted_exclusions))
            if predicted_exclusions
            else None
        ),
        "structured_response_success_rate": (
            ratio(structured_successes, len(attempted)) if attempted else None
        ),
        "manual_review_rate": ratio(
            sum(row["final_decision"] == "manual_review" for row in predicted.values()),
            len(predicted),
        ),
    }


def evaluate_full_text(
    expected: dict[str, dict[str, str]],
    predicted: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    pairs = []
    family_pairs = []
    for identifier, expected_row in expected.items():
        expected_level = expected_row.get("expert_causal_evidence_level")
        predicted_row = predicted.get(identifier)
        if (
            expected_level
            and predicted_row
            and predicted_row.get("causal_evidence_level") is not None
        ):
            pairs.append((int(expected_level), int(predicted_row["causal_evidence_level"])))
        expected_family = expected_row.get("expert_primary_design_family")
        selected = predicted_row.get("selected_criteria", {}) if predicted_row else {}
        predicted_family = selected.get("primary_design_family")
        if expected_family and predicted_family:
            family_pairs.append((expected_family, predicted_family))

    exact = sum(left == right for left, right in pairs)
    within_one = sum(abs(left - right) <= 1 for left, right in pairs)
    eligible = [(left >= 2, right >= 2) for left, right in pairs]
    eligibility_true = sum(left for left, _ in eligible)
    eligibility_retained = sum(left and right for left, right in eligible)
    unsupported_citations = find_unsupported_citations(predicted)
    return {
        "level_pairs": len(pairs),
        "exact_level_agreement": ratio(exact, len(pairs)) if pairs else None,
        "within_one_level_agreement": ratio(within_one, len(pairs)) if pairs else None,
        "quadratic_weighted_kappa": quadratic_weighted_kappa(pairs),
        "eligibility_sensitivity": (
            ratio(eligibility_retained, eligibility_true)
            if eligibility_true
            else None
        ),
        "design_family_macro_f1": macro_f1(family_pairs),
        "unsupported_section_citations": len(unsupported_citations),
        "unsupported_section_references": unsupported_citations,
    }


def quadratic_weighted_kappa(
    pairs: list[tuple[int, int]], levels: int = 5
) -> float | None:
    if not pairs:
        return None
    observed = [[0 for _ in range(levels)] for _ in range(levels)]
    left_counts = [0 for _ in range(levels)]
    right_counts = [0 for _ in range(levels)]
    for left, right in pairs:
        observed[left][right] += 1
        left_counts[left] += 1
        right_counts[right] += 1
    weighted_observed = 0.0
    weighted_expected = 0.0
    total = len(pairs)
    for left in range(levels):
        for right in range(levels):
            weight = ((left - right) ** 2) / ((levels - 1) ** 2)
            weighted_observed += weight * observed[left][right]
            weighted_expected += weight * left_counts[left] * right_counts[right] / total
    return 1.0 - weighted_observed / weighted_expected if weighted_expected else 1.0


def macro_f1(pairs: list[tuple[str, str]]) -> float | None:
    if not pairs:
        return None
    labels = sorted({item for pair in pairs for item in pair})
    scores = []
    for label in labels:
        true_positive = sum(left == label and right == label for left, right in pairs)
        false_positive = sum(left != label and right == label for left, right in pairs)
        false_negative = sum(left == label and right != label for left, right in pairs)
        precision = ratio(true_positive, true_positive + false_positive)
        recall = ratio(true_positive, true_positive + false_negative)
        scores.append(ratio(2 * precision * recall, precision + recall))
    return sum(scores) / len(scores)


def find_unsupported_citations(
    predicted: dict[str, dict[str, Any]],
) -> list[str]:
    unsupported: list[str] = []
    for identifier, row in predicted.items():
        selection = row.get("section_selection", {})
        valid_ids = {
            item.get("section_id")
            for item in selection.get("selected_sections", [])
            if item.get("section_id")
        }
        references = _section_references(
            {
                "round_a": row.get("round_a", {}),
                "adjudication": row.get("adjudication"),
                "selected_criteria": row.get("selected_criteria", {}),
            }
        )
        unsupported.extend(
            f"{identifier}:{section_id}"
            for section_id in sorted(references - valid_ids)
        )
    return sorted(set(unsupported))


def _section_references(value: Any) -> set[str]:
    references: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            if key == "section_id" and isinstance(child, str) and child:
                references.add(child)
            elif key == "section_ids" and isinstance(child, list):
                references.update(item for item in child if isinstance(item, str) and item)
            else:
                references.update(_section_references(child))
    elif isinstance(value, list):
        for child in value:
            references.update(_section_references(child))
    return references


def acceptance_report(
    metrics: dict[str, Any], thresholds: dict[str, tuple[str, float]]
) -> dict[str, Any]:
    gates: dict[str, dict[str, Any]] = {}
    for metric, (operator, threshold) in thresholds.items():
        value = metrics.get(metric)
        passed = None
        if value is not None:
            passed = value >= threshold if operator == ">=" else value == threshold
        gates[metric] = {
            "value": value,
            "operator": operator,
            "threshold": threshold,
            "passed": passed,
        }
    outcomes = [gate["passed"] for gate in gates.values()]
    if any(outcome is False for outcome in outcomes):
        overall = "fail"
    elif any(outcome is None for outcome in outcomes):
        overall = "not_evaluable"
    else:
        overall = "pass"
    return {"overall": overall, "gates": gates}
