from causal_multiomics_review.benchmark import (
    FULL_TEXT_ACCEPTANCE,
    TITLE_ACCEPTANCE,
    acceptance_report,
    evaluate_full_text,
    evaluate_title,
)


def test_title_acceptance_tracks_canonical_and_structured_success() -> None:
    expected = {
        "r1": {
            "expert_expected_decision": "seek_full_text",
            "expert_canonical_positive": "yes",
        },
        "r2": {
            "expert_expected_decision": "exclude",
            "expert_canonical_positive": "no",
        },
    }
    predicted = {
        "r1": {"final_decision": "seek_full_text"},
        "r2": {"final_decision": "exclude"},
    }
    metrics = evaluate_title(expected, predicted)
    report = acceptance_report(metrics, TITLE_ACCEPTANCE)
    assert metrics["canonical_positive_retention"] == 1.0
    assert report["overall"] == "pass"


def test_full_text_acceptance_rejects_unknown_section_citation() -> None:
    expected = {
        "r1": {
            "expert_causal_evidence_level": "3",
            "expert_primary_design_family": "genetic_instrument",
        }
    }
    predicted = {
        "r1": {
            "causal_evidence_level": 3,
            "section_selection": {"selected_sections": [{"section_id": "S1"}]},
            "selected_criteria": {
                "primary_design_family": "genetic_instrument",
                "evidence_spans": [{"section_id": "S9", "quote": "unsupported"}],
            },
        }
    }
    metrics = evaluate_full_text(expected, predicted)
    report = acceptance_report(metrics, FULL_TEXT_ACCEPTANCE)
    assert metrics["unsupported_section_references"] == ["r1:S9"]
    assert report["overall"] == "fail"
