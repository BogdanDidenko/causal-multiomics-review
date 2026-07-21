import json

from causal_multiomics_review.screening import run_stage_screening


class QueueProvider:
    model = "fake-model"
    url = "https://example.test/v1/chat/completions"
    temperature = 0.7
    top_p = 1.0
    seed = 0
    n = 1
    max_tokens = 16000
    response_format = "json_schema"

    def __init__(self, answers: dict[str, list[dict[str, object]]]) -> None:
        self.answers = answers
        self.calls: list[str] = []

    def complete_json(self, prompt, schema=None, schema_name="screening_response"):
        self.calls.append(schema_name)
        answer = self.answers[schema_name].pop(0)
        return answer, {"role": schema_name, "answer": answer}


def scope_answer() -> dict[str, object]:
    return {
        "report_type": "empirical_primary",
        "bio_health_scope": "yes",
        "multiomics_status": "yes",
        "integration_mode": "cross_dataset_integrated",
        "omics_layers": [
            {
                "layer": "genomics",
                "raw_term": "GWAS",
                "use_status": "external_dataset_analyzed",
                "analytic_role": "outcome associations",
            },
            {
                "layer": "transcriptomics",
                "raw_term": "eQTL",
                "use_status": "external_dataset_analyzed",
                "analytic_role": "molecular exposure",
            },
        ],
        "evidence_spans": [
            {"criterion": "multiomics_status", "source": "abstract", "quote": "GWAS and eQTL"}
        ],
        "boundary_case": "cross_dataset_multiomics",
        "uncertainty_reason": "",
        "concise_rationale": "Two molecular layers are analyzed together.",
    }


def causal_title_answer() -> dict[str, object]:
    return {
        "causal_claim_present": "yes",
        "identification_status": "identified",
        "design_families": ["genetic_instrument"],
        "design_role": "primary_identification",
        "exposure_or_intervention": "genetically predicted expression",
        "comparator": "per allele expression contrast",
        "outcome": "disease risk",
        "estimand_or_contrast": "effect of predicted expression on risk",
        "evidence_spans": [
            {
                "criterion": "identification_status",
                "source": "abstract",
                "quote": "Mendelian randomization",
            }
        ],
        "boundary_case": "clear_identified",
        "uncertainty_reason": "",
        "concise_rationale": "The abstract reports an MR effect.",
    }


def title_adjudication_answer(resolution_status: str) -> dict[str, object]:
    answer = {
        **scope_answer(),
        **causal_title_answer(),
        "boundary_cases": ["thin_abstract"],
        "resolution_status": resolution_status,
        "identification_status": "unclear",
        "uncertainty_reason": "The abstract does not report identification details.",
    }
    answer.pop("boundary_case")
    return answer


def selector_answer() -> dict[str, object]:
    return {
        "selected_sections": [
            {
                "section_id": "S1",
                "purposes": ["study_design", "omics_data"],
                "priority": "required",
            },
            {
                "section_id": "S2",
                "purposes": ["identification", "validation"],
                "priority": "required",
            },
        ],
        "coverage_status": "sufficient",
        "missing_evidence_categories": [],
        "concise_rationale": "Methods and Results contain decisive evidence.",
    }


def eligibility_answer() -> dict[str, object]:
    return {
        "report_type": "empirical_primary",
        "empirical_primary": "yes",
        "bio_health_scope": "yes",
        "multiomics_status": "yes",
        "integration_mode": "cross_dataset_integrated",
        "omics_layers": [
            {
                "layer": "genomics",
                "assay_or_data_source": "disease GWAS",
                "cohort_or_system": "consortium",
                "origin": "external_dataset_analyzed",
                "analytic_role": "outcome",
                "section_ids": ["S1"],
            },
            {
                "layer": "transcriptomics",
                "assay_or_data_source": "cis-eQTL",
                "cohort_or_system": "GTEx",
                "origin": "external_dataset_analyzed",
                "analytic_role": "exposure",
                "section_ids": ["S1"],
            },
        ],
        "relevant_causal_design": "yes",
        "date_eligible": "yes",
        "english_language": "yes",
        "full_text_sufficient": "yes",
        "first_failed_criterion": "none",
        "evidence_spans": [{"criterion": "IC2", "section_id": "S1", "quote": "GWAS and eQTL"}],
        "uncertainty_reason": "",
        "concise_rationale": "The report is eligible.",
    }


def causal_full_text_answer() -> dict[str, object]:
    return {
        "causal_claim_present": "yes",
        "identification_status": "identified",
        "primary_design_family": "genetic_instrument",
        "supporting_design_families": [],
        "design_role": "primary_identification",
        "population_or_model": "European ancestry participants",
        "exposure_or_intervention": "genetically predicted expression",
        "comparator": "per allele contrast",
        "outcome": "disease risk",
        "time_horizon": "lifelong genetic exposure",
        "estimand": {
            "statement": "effect of predicted expression on disease risk",
            "effect_measure_or_contrast": "odds ratio per expression unit",
        },
        "estimand_complete": "yes",
        "assumptions_assessable": "yes",
        "assumptions": [
            {
                "name": "instrument relevance",
                "status": "addressed",
                "assessment": "F statistics exceeded 10",
                "section_ids": ["S2"],
            }
        ],
        "diagnostics_and_sensitivity": [
            {"name": "MR-Egger", "result_or_role": "pleiotropy check", "section_ids": ["S2"]}
        ],
        "validations": [
            {
                "type": "colocalization",
                "independence": "independent",
                "alignment": "same_causal_link",
                "what_it_validates": "shared variant for expression and disease",
                "section_ids": ["S2"],
            }
        ],
        "validation_strength": "independent_same_link",
        "limitations": ["Ancestry transportability is limited."],
        "evidence_spans": [
            {"criterion": "identification_status", "section_id": "S2", "quote": "two-sample MR"}
        ],
        "uncertainty_reason": "",
        "concise_rationale": "MR with aligned independent validation.",
    }


def test_title_stage_retries_invalid_response_and_resumes(tmp_path) -> None:
    input_path = tmp_path / "records.csv"
    input_path.write_text(
        "record_id,title,abstract,year,source\n"
        'r1,"Multi-omics MR","GWAS and eQTL Mendelian randomization.",2024,PubMed\n',
        encoding="utf-8",
    )
    invalid_scope = {**scope_answer(), "multiomics_status": "maybe"}
    provider = QueueProvider(
        {
            "scope_reviewer": [invalid_scope, scope_answer()],
            "causal_design_reviewer": [causal_title_answer()],
        }
    )
    output = tmp_path / "run"
    counts = run_stage_screening(input_path, output, provider)
    assert counts == {"seek_full_text": 1}
    assert provider.calls.count("scope_reviewer") == 2
    raw_rows = [
        json.loads(line)
        for line in (output / "raw_provider_responses.jsonl").read_text().splitlines()
    ]
    assert raw_rows[0]["status"] == "error"
    assert raw_rows[0]["response"]["answer"]["multiomics_status"] == "maybe"
    assert raw_rows[1]["status"] == "ok"

    resumed_provider = QueueProvider({})
    resumed_counts = run_stage_screening(
        input_path,
        output,
        resumed_provider,
        resume=True,
    )
    assert resumed_counts == {"seek_full_text": 1}
    assert resumed_provider.calls == []


def test_full_text_stage_derives_level_four_and_ledger_fields(tmp_path) -> None:
    input_path = tmp_path / "fulltext.jsonl"
    record = {
        "record_id": "r1",
        "title": "Multi-omics MR study",
        "abstract": "GWAS and eQTL MR analysis.",
        "year": 2024,
        "source": "PubMed",
        "sections": [
            {"section_id": "S1", "heading": "Methods", "text": "GWAS and eQTL data."},
            {"section_id": "S2", "heading": "Results", "text": "MR and colocalization results."},
        ],
    }
    input_path.write_text(json.dumps(record) + "\n", encoding="utf-8")
    provider = QueueProvider(
        {
            "section_selector": [selector_answer()],
            "eligibility_reviewer": [eligibility_answer()],
            "causal_evidence_reviewer": [causal_full_text_answer()],
        }
    )
    output = tmp_path / "run"
    counts = run_stage_screening(
        input_path,
        output,
        provider,
        stage="full_text",
    )
    result = json.loads((output / "screening_results.jsonl").read_text())
    assert counts == {"assessed": 1}
    assert result["causal_evidence_level"] == 4
    assert result["final_study_label"] == "causal_evidence"
    assert result["ledger_fields"]["identification_source"] == "genetic_instrument"


def test_missing_abstract_routes_to_manual_review_without_model_call(tmp_path) -> None:
    input_path = tmp_path / "records.csv"
    input_path.write_text(
        "record_id,title,abstract,year,source\nr1,No abstract,,2024,Scopus\n",
        encoding="utf-8",
    )
    provider = QueueProvider({})
    output = tmp_path / "run"
    counts = run_stage_screening(input_path, output, provider)
    result = json.loads((output / "screening_results.jsonl").read_text())
    assert counts == {"manual_review": 1}
    assert result["manual_review_reason"] == "missing_abstract"
    assert provider.calls == []


def test_thin_abstract_uncertainty_proceeds_to_full_text(tmp_path) -> None:
    input_path = tmp_path / "records.csv"
    input_path.write_text(
        "record_id,title,abstract,year,source\n"
        'r1,"Thin multi-omics study","GWAS and eQTL were integrated.",2024,PubMed\n',
        encoding="utf-8",
    )
    unclear_causal = {
        **causal_title_answer(),
        "identification_status": "unclear",
        "boundary_case": "thin_abstract",
    }
    provider = QueueProvider(
        {
            "scope_reviewer": [scope_answer()],
            "causal_design_reviewer": [unclear_causal],
            "adjudicator": [title_adjudication_answer("insufficient_title_abstract")],
        }
    )
    counts = run_stage_screening(input_path, tmp_path / "run", provider)
    assert counts == {"seek_full_text": 1}


def test_unresolved_decisive_conflict_routes_to_manual_review(tmp_path) -> None:
    input_path = tmp_path / "records.csv"
    input_path.write_text(
        "record_id,title,abstract,year,source\n"
        'r1,"Ambiguous study","GWAS and eQTL analysis.",2024,PubMed\n',
        encoding="utf-8",
    )
    unclear_causal = {
        **causal_title_answer(),
        "identification_status": "unclear",
        "boundary_case": "thin_abstract",
    }
    provider = QueueProvider(
        {
            "scope_reviewer": [scope_answer()],
            "causal_design_reviewer": [unclear_causal],
            "adjudicator": [title_adjudication_answer("conflict_unresolved")],
        }
    )
    counts = run_stage_screening(input_path, tmp_path / "run", provider)
    assert counts == {"manual_review": 1}


def test_malformed_jsonl_and_missing_identifier_are_not_lost(tmp_path) -> None:
    input_path = tmp_path / "fulltext.jsonl"
    input_path.write_text(
        '{"title": "Missing identifier", "abstract": "Present"}\n{bad json}\n',
        encoding="utf-8",
    )
    provider = QueueProvider({})
    output = tmp_path / "run"
    counts = run_stage_screening(
        input_path,
        output,
        provider,
        stage="full_text",
    )
    results = [
        json.loads(line)
        for line in (output / "screening_results.jsonl").read_text().splitlines()
    ]
    assert counts == {"manual_review": 2}
    assert [row["record_id"] for row in results] == [
        "invalid-full_text-record-000001",
        "invalid-jsonl-line-000002",
    ]
    assert all(row["manual_review_reason"] == "invalid_input_record" for row in results)
    assert provider.calls == []
