from causal_multiomics_review.config import load_gate_config
from causal_multiomics_review.gates import gate_answer, route_adjudicated, route_round_a


def test_round_a_advances_only_when_both_roles_include() -> None:
    config = load_gate_config()
    answers = {
        "scope_reviewer": {
            "paper_type": "empirical_primary",
            "bio_health_scope": "yes",
            "multiomics_present": "yes",
        },
        "causal_design_reviewer": {"causal_design_present": "yes"},
    }
    route, decisions = route_round_a(answers, config)
    assert route == "seek_full_text"
    assert decisions == {
        "scope_reviewer": "include",
        "causal_design_reviewer": "include",
    }


def test_unclear_has_priority_over_exclusion() -> None:
    config = load_gate_config()
    answer = {
        "paper_type": "review_editorial",
        "bio_health_scope": "yes",
        "multiomics_present": "unclear",
    }
    assert gate_answer(answer, config["round_a"]["scope_reviewer"]) == "unclear"


def test_active_suite_can_prioritize_explicit_exclusion() -> None:
    config = load_gate_config()
    config["gate_precedence"] = "exclude_then_unclear"
    answer = {
        "paper_type": "review_editorial",
        "bio_health_scope": "yes",
        "multiomics_present": "unclear",
        "causal_design_present": "unclear",
    }
    assert route_adjudicated(answer, config) == ("exclude", "exclude")


def test_adjudicator_routes_failed_causal_design_to_exclusion() -> None:
    config = load_gate_config()
    answer = {
        "paper_type": "empirical_primary",
        "bio_health_scope": "yes",
        "multiomics_present": "yes",
        "causal_design_present": "no",
    }
    assert route_adjudicated(answer, config) == ("exclude", "exclude")


def test_adjudicator_preserves_uncertainty_for_manual_review() -> None:
    config = load_gate_config()
    answer = {
        "paper_type": "empirical_primary",
        "bio_health_scope": "yes",
        "multiomics_present": "yes",
        "causal_design_present": "unclear",
    }
    assert route_adjudicated(answer, config) == ("manual_review", "unclear")
