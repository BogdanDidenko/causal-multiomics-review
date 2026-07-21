from __future__ import annotations

from typing import Any

LEVEL_LABELS = {
    0: "context_only",
    1: "associational",
    2: "causal_hypothesis",
    3: "causal_evidence",
    4: "causal_evidence",
}


class EvidenceReferenceError(ValueError):
    pass


def derive_exclusion_code(answer: dict[str, Any]) -> str:
    report_type = answer.get("report_type")
    if report_type in {"review_editorial", "protocol"}:
        return "EC1"
    if report_type in {"methods_only", "resource"}:
        return "EC2"
    if answer.get("empirical_primary") == "no":
        return "EC1"
    if answer.get("multiomics_status") == "no":
        return "EC3"
    if answer.get("bio_health_scope") == "no":
        return "EC4"
    if answer.get("identification_status") in {
        "association_only",
        "no_relevant_design",
        "not_applicable",
    }:
        return "EC5"
    if answer.get("date_eligible") == "no" or answer.get("english_language") == "no":
        return "EC6"
    return "none"


def derive_evidence_level(answer: dict[str, Any]) -> tuple[int, str] | None:
    decisive_fields = (
        "empirical_primary",
        "bio_health_scope",
        "multiomics_status",
        "date_eligible",
        "english_language",
        "full_text_sufficient",
    )
    if any(answer.get(field) == "unclear" for field in decisive_fields):
        return None
    if answer.get("full_text_sufficient") == "no":
        return None
    if any(
        answer.get(field) == "no"
        for field in (
            "empirical_primary",
            "bio_health_scope",
            "multiomics_status",
            "date_eligible",
            "english_language",
        )
    ):
        return 0, LEVEL_LABELS[0]

    status = answer.get("identification_status")
    if status == "unclear" or status is None:
        return None
    if status in {"association_only", "not_applicable"}:
        return 1, LEVEL_LABELS[1]
    if status == "hypothesis_only":
        return 2, LEVEL_LABELS[2]
    if status != "identified":
        return None

    estimand = answer.get("estimand_complete")
    assumptions = answer.get("assumptions_assessable")
    if "unclear" in {estimand, assumptions} or None in {estimand, assumptions}:
        return None
    if estimand == "no" or assumptions == "no":
        return 2, LEVEL_LABELS[2]
    if not _has_assessable_causal_profile(answer):
        return 2, LEVEL_LABELS[2]

    validation = answer.get("validation_strength")
    if validation == "unclear" or validation is None:
        return None
    level = (
        4
        if validation == "independent_same_link"
        and _has_independent_same_link_validation(answer)
        else 3
    )
    return level, LEVEL_LABELS[level]


def _has_assessable_causal_profile(answer: dict[str, Any]) -> bool:
    if not all(
        str(answer.get(field, "")).strip()
        for field in ("exposure_or_intervention", "outcome")
    ):
        return False
    estimand = answer.get("estimand", {})
    if not isinstance(estimand, dict) or not all(
        str(estimand.get(field, "")).strip()
        for field in ("statement", "effect_measure_or_contrast")
    ):
        return False
    assumptions = answer.get("assumptions", [])
    return isinstance(assumptions, list) and bool(assumptions)


def _has_independent_same_link_validation(answer: dict[str, Any]) -> bool:
    validations = answer.get("validations", [])
    return isinstance(validations, list) and any(
        isinstance(item, dict)
        and item.get("independence") == "independent"
        and item.get("alignment") == "same_causal_link"
        and bool(str(item.get("what_it_validates", "")).strip())
        and bool(item.get("section_ids"))
        for item in validations
    )


def validate_evidence_references(answer: dict[str, Any], valid_section_ids: set[str]) -> None:
    referenced = _collect_section_references(answer)
    unknown = sorted(referenced - valid_section_ids)
    if unknown:
        raise EvidenceReferenceError(f"Unknown evidence section IDs: {', '.join(unknown)}")


def build_ledger_fields(answer: dict[str, Any], level: int, label: str) -> dict[str, Any]:
    layers = []
    for item in answer.get("omics_layers", []):
        layer = item.get("layer", "")
        source = item.get("assay_or_data_source", "")
        layers.append(f"{layer}: {source}".strip(": "))

    designs = []
    primary = answer.get("primary_design_family")
    if primary not in {None, "", "none", "unclear"}:
        designs.append(primary)
    designs.extend(
        item for item in answer.get("supporting_design_families", []) if item not in designs
    )

    assumption_parts = [
        f"{item.get('name', '')} [{item.get('status', '')}]: {item.get('assessment', '')}"
        for item in answer.get("assumptions", [])
    ]
    diagnostic_parts = [
        f"{item.get('name', '')}: {item.get('result_or_role', '')}"
        for item in answer.get("diagnostics_and_sensitivity", [])
    ]
    estimand = answer.get("estimand", {})
    return {
        "verified_omics_layers": "; ".join(filter(None, layers)),
        "identification_source": ";".join(designs) or "none",
        "causal_estimand": estimand.get("statement", ""),
        "assumptions_and_sensitivity_checks": "; ".join(
            filter(None, assumption_parts + diagnostic_parts)
        ),
        "causal_evidence_level": level,
        "final_study_label": label,
    }


def _collect_section_references(value: Any, parent_key: str = "") -> set[str]:
    references: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            if key == "section_id" and isinstance(child, str) and child:
                references.add(child)
            elif key == "section_ids" and isinstance(child, list):
                references.update(item for item in child if isinstance(item, str) and item)
            else:
                references.update(_collect_section_references(child, key))
    elif isinstance(value, list):
        for child in value:
            references.update(_collect_section_references(child, parent_key))
    return references
