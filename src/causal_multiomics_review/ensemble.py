from __future__ import annotations

from collections import Counter
from typing import Any


def aggregate_title_abstract_runs(
    rows: list[dict[str, Any]],
    expected_runs: int = 6,
) -> dict[str, Any]:
    if len(rows) != expected_runs:
        raise ValueError(f"Expected {expected_runs} run results, received {len(rows)}")
    record_ids = {str(row["record_id"]) for row in rows}
    if len(record_ids) != 1:
        raise ValueError("Ensemble rows must describe one record_id")

    decisions = [str(row["final_decision"]) for row in rows]
    exclusion_codes = [str(row.get("final_exclusion_code", "none")) for row in rows]
    unanimous_exclusion = (
        all(decision == "exclude" for decision in decisions)
        and len(set(exclusion_codes)) == 1
        and exclusion_codes[0] != "none"
    )
    return {
        "record_id": record_ids.pop(),
        "ensemble_decision": "exclude" if unanimous_exclusion else "seek_full_text",
        "ensemble_exclusion_code": exclusion_codes[0] if unanimous_exclusion else "none",
        "decision_counts": dict(Counter(decisions)),
        "exclusion_code_counts": dict(Counter(exclusion_codes)),
        "unanimous": len(set(decisions)) == 1,
        "has_uncertainty_or_disagreement": (
            len(set(decisions)) > 1 or any(item == "manual_review" for item in decisions)
        ),
    }
