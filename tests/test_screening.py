import json

from causal_multiomics_review.screening import run_screening


class FakeProvider:
    model = "fake-model"
    url = "https://example.test/v1/chat/completions"

    def complete_json(self, prompt: str):
        if "scope reviewer" in prompt:
            answer = {
                "paper_type": "empirical_primary",
                "bio_health_scope": "yes",
                "multiomics_present": "yes",
                "omics_layers": ["transcriptomics", "proteomics"],
                "report_level_multiomics_evidence": "Both layers were measured.",
                "primary_exclusion_code": "none",
                "uncertainty_reason": "",
                "rationale": "Primary multi-omics study.",
            }
        elif "causal-design reviewer" in prompt:
            answer = {
                "causal_design_present": "yes",
                "design_families": ["direct_perturbation"],
                "intervention_or_instrument": "CRISPR perturbation",
                "estimand_evidence": "Perturbed versus control cells.",
                "assumptions_visible": "unclear",
                "causal_design_evidence": "Direct perturbation was reported.",
                "primary_exclusion_code": "none",
                "uncertainty_reason": "Full assumptions require full text.",
                "rationale": "The design contains a controlled perturbation.",
            }
        else:
            raise AssertionError("Adjudication should not be needed")
        return answer, {"fake": True}


def test_run_screening_writes_audited_result(tmp_path) -> None:
    input_path = tmp_path / "records.csv"
    input_path.write_text(
        "record_id,title,abstract,year,source\n"
        'r1,"Perturb-seq multi-omics","We measured RNA and proteins.",2024,PubMed\n',
        encoding="utf-8",
    )
    output = tmp_path / "run"
    counts = run_screening(input_path, output, FakeProvider())

    result = json.loads((output / "screening_results.jsonl").read_text())
    manifest = json.loads((output / "manifest.json").read_text())
    assert counts == {"seek_full_text": 1}
    assert result["final_decision"] == "seek_full_text"
    assert manifest["record_count"] == 1
    assert manifest["artifacts"]["scope_reviewer"]["prompt_sha256"]
