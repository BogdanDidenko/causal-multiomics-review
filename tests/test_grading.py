import pytest

from causal_multiomics_review.grading import (
    EvidenceReferenceError,
    derive_evidence_level,
    derive_exclusion_code,
    validate_evidence_references,
)


def base_answer() -> dict[str, object]:
    return {
        "empirical_primary": "yes",
        "bio_health_scope": "yes",
        "multiomics_status": "yes",
        "date_eligible": "yes",
        "english_language": "yes",
        "full_text_sufficient": "yes",
        "identification_status": "identified",
        "exposure_or_intervention": "genetically predicted expression",
        "outcome": "disease risk",
        "estimand": {
            "statement": "effect of expression on disease risk",
            "effect_measure_or_contrast": "odds ratio per expression unit",
        },
        "estimand_complete": "yes",
        "assumptions_assessable": "yes",
        "assumptions": [
            {
                "name": "instrument relevance",
                "status": "addressed",
                "assessment": "F statistic above 10",
                "section_ids": ["S1"],
            }
        ],
        "validations": [],
        "validation_strength": "none",
    }


@pytest.mark.parametrize(
    ("updates", "expected"),
    [
        ({"multiomics_status": "no"}, (0, "context_only")),
        ({"identification_status": "association_only"}, (1, "associational")),
        ({"identification_status": "hypothesis_only"}, (2, "causal_hypothesis")),
        ({}, (3, "causal_evidence")),
        (
            {
                "validation_strength": "independent_same_link",
                "validations": [
                    {
                        "type": "colocalization",
                        "independence": "independent",
                        "alignment": "same_causal_link",
                        "what_it_validates": "shared causal variant",
                        "section_ids": ["S2"],
                    }
                ],
            },
            (4, "causal_evidence"),
        ),
        (
            {"validation_strength": "independent_same_link", "validations": []},
            (3, "causal_evidence"),
        ),
        (
            {"estimand": {"statement": "", "effect_measure_or_contrast": ""}},
            (2, "causal_hypothesis"),
        ),
        ({"assumptions_assessable": "unclear"}, None),
    ],
)
def test_deterministic_evidence_levels(
    updates: dict[str, object],
    expected: tuple[int, str] | None,
) -> None:
    answer = {**base_answer(), **updates}
    assert derive_evidence_level(answer) == expected


def test_exclusion_code_is_criterion_derived() -> None:
    assert derive_exclusion_code({"report_type": "methods_only"}) == "EC2"
    assert derive_exclusion_code({"multiomics_status": "no"}) == "EC3"
    assert derive_exclusion_code({"identification_status": "association_only"}) == "EC5"


def test_unknown_section_reference_is_rejected() -> None:
    answer = {"evidence_spans": [{"section_id": "S9", "quote": "unsupported"}]}
    with pytest.raises(EvidenceReferenceError, match="S9"):
        validate_evidence_references(answer, {"S1", "S2"})
