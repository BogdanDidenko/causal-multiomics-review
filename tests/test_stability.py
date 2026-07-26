import json
import subprocess
import sys

from causal_multiomics_review.config import REPO_ROOT
from causal_multiomics_review.stability import assess_stability

TITLE_ACCEPTANCE = {
    "schema_success_rate": 1.0,
    "final_decision_exact_agreement": 1.0,
    "decisive_criteria_exact_agreement": 1.0,
    "causal_evidence_level_exact_agreement": 1.0,
    "manual_review_rate": 0.0,
}


def title_result(identification_status: str = "identified") -> dict[str, object]:
    return {
        "record_id": "r1",
        "final_decision": "seek_full_text",
        "final_exclusion_code": "none",
        "selected_criteria": {
            "report_type": "empirical_primary",
            "bio_health_scope": "yes",
            "multiomics_status": "yes",
            "integration_mode": "cross_dataset_integrated",
            "identification_status": identification_status,
            "design_families": ["genetic_instrument"],
            "design_role": "primary_identification",
            "evidence_spans": [{"quote": "Different phrasing is ignored."}],
        },
    }


def test_stability_uses_decisive_criteria_not_free_text() -> None:
    runs = {f"replicate-{index}": {"r1": title_result()} for index in range(1, 6)}
    rows, summary = assess_stability(runs, "title_abstract", TITLE_ACCEPTANCE)
    assert rows[0]["stable"] is True
    assert summary["acceptance"]["overall"] == "pass"


def test_stability_localizes_disagreeing_criterion() -> None:
    runs = {f"replicate-{index}": {"r1": title_result()} for index in range(1, 6)}
    runs["replicate-5"] = {"r1": title_result("hypothesis_only")}
    rows, summary = assess_stability(runs, "title_abstract", TITLE_ACCEPTANCE)
    assert rows[0]["stable"] is False
    assert "selected_criteria.identification_status" in rows[0]["disagreements"]
    assert summary["acceptance"]["overall"] == "fail"


def test_stability_cli_requires_matching_terra_manifests(tmp_path) -> None:
    run_args: list[str] = []
    for index in range(1, 6):
        run_dir = tmp_path / f"replicate-{index:02d}"
        run_dir.mkdir()
        result_path = run_dir / "screening_results.jsonl"
        result_path.write_text(json.dumps(title_result()) + "\n", encoding="utf-8")
        (run_dir / "manifest.json").write_text(
            json.dumps(
                {
                    "model": "gpt-5.6-terra",
                    "runtime": {
                        "api_protocol": "codex_cli",
                        "reasoning_effort": "medium",
                        "context_window": 32768,
                        "response_format": "json_schema",
                        "sandbox": "read-only",
                        "approval_policy": "never",
                        "ephemeral": True,
                        "ignore_user_config": True,
                        "ignore_rules": True,
                    },
                }
            ),
            encoding="utf-8",
        )
        run_args.extend(("--run", f"replicate-{index:02d}={result_path}"))
    output_dir = tmp_path / "assessment"
    completed = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "assess_screening_stability.py"),
            "--stage",
            "title_abstract",
            "--output-dir",
            str(output_dir),
            *run_args,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    summary = json.loads((output_dir / "stability_summary.json").read_text())
    assert completed.stdout.strip() == "pass"
    assert summary["acceptance"]["overall"] == "pass"


def test_stability_cli_rejects_reasoning_effort_drift(tmp_path) -> None:
    run_args: list[str] = []
    for index in range(1, 6):
        run_dir = tmp_path / f"replicate-{index:02d}"
        run_dir.mkdir()
        result_path = run_dir / "screening_results.jsonl"
        result_path.write_text(json.dumps(title_result()) + "\n", encoding="utf-8")
        reasoning_effort = "high" if index == 5 else "medium"
        (run_dir / "manifest.json").write_text(
            json.dumps(
                {
                    "model": "gpt-5.6-terra",
                    "runtime": {
                        "api_protocol": "codex_cli",
                        "reasoning_effort": reasoning_effort,
                        "context_window": 32768,
                        "response_format": "json_schema",
                        "sandbox": "read-only",
                        "approval_policy": "never",
                        "ephemeral": True,
                        "ignore_user_config": True,
                        "ignore_rules": True,
                    },
                }
            ),
            encoding="utf-8",
        )
        run_args.extend(("--run", f"replicate-{index:02d}={result_path}"))

    completed = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "assess_screening_stability.py"),
            "--stage",
            "title_abstract",
            "--output-dir",
            str(tmp_path / "assessment"),
            *run_args,
        ],
        capture_output=True,
        text=True,
    )
    assert completed.returncode != 0
    assert "reasoning_effort='high'" in completed.stderr
