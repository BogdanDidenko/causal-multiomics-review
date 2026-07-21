import pytest

from causal_multiomics_review.ensemble import aggregate_title_abstract_runs


def test_six_matching_exclusions_are_automated() -> None:
    rows = [
        {"record_id": "r1", "final_decision": "exclude", "final_exclusion_code": "EC3"}
        for _ in range(6)
    ]
    result = aggregate_title_abstract_runs(rows)
    assert result["ensemble_decision"] == "exclude"
    assert result["ensemble_exclusion_code"] == "EC3"


def test_any_disagreement_retains_for_full_text() -> None:
    rows = [
        {"record_id": "r1", "final_decision": "exclude", "final_exclusion_code": "EC3"}
        for _ in range(5)
    ] + [{"record_id": "r1", "final_decision": "manual_review"}]
    result = aggregate_title_abstract_runs(rows)
    assert result["ensemble_decision"] == "seek_full_text"
    assert result["has_uncertainty_or_disagreement"] is True


def test_ensemble_requires_six_complete_runs() -> None:
    with pytest.raises(ValueError, match="Expected 6"):
        aggregate_title_abstract_runs([], expected_runs=6)
