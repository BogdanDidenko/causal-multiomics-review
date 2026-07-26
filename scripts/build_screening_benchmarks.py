#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
from collections import defaultdict
from pathlib import Path
from typing import Any

from causal_multiomics_review.audit import sha256_file, write_manifest

TITLE_FIELDS = [
    "canonical_id",
    "title",
    "abstract",
    "year",
    "doi",
    "pmid",
    "lanes",
    "sampling_stratum",
    "prior_title_abstract_decision",
    "prior_title_abstract_exclusion_reason",
    "prior_final_study_label",
    "prior_causal_evidence_level",
    "expert_report_type",
    "expert_bio_health_scope",
    "expert_multiomics_status",
    "expert_identification_status",
    "expert_design_families",
    "expert_canonical_positive",
    "expert_expected_decision",
    "expert_exclusion_code",
    "expert_uncertainty_reason",
    "expert_notes",
]

FULL_TEXT_FIELDS = TITLE_FIELDS[:7] + [
    "sampling_stratum",
    "full_text_status",
    "full_text_location",
    "prior_identification_source",
    "prior_causal_evidence_level",
    "prior_final_study_label",
    "expert_verified_omics_layers",
    "expert_identification_status",
    "expert_primary_design_family",
    "expert_causal_estimand",
    "expert_assumptions",
    "expert_validation_strength",
    "expert_causal_evidence_level",
    "expert_final_study_label",
    "expert_evidence_section_ids",
    "expert_notes",
]


def read_ledger(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def normalized_text(value: str) -> str:
    return " ".join(value.split())


def stable_order(rows: list[dict[str, str]], seed: str) -> list[dict[str, str]]:
    def key(row: dict[str, str]) -> str:
        identifier = row.get("canonical_id") or row.get("doi") or row.get("title", "")
        return hashlib.sha256(f"{seed}|{identifier}".encode()).hexdigest()

    return sorted(rows, key=key)


def design_bucket(row: dict[str, str]) -> str:
    text = " ".join(
        [
            row.get("identification_source", ""),
            row.get("lanes", ""),
            row.get("title", ""),
        ]
    ).lower()
    rules = (
        ("direct_perturbation", ("perturb", "crispr")),
        ("randomized_intervention", ("randomized", "randomised", " rct", "trial")),
        ("nonrandomized_intervention", ("nonrandomized", "nonrandomised", "quasi")),
        ("temporal_design", ("temporal", "longitudinal", "time series")),
        ("formal_mediation", ("mediation", "indirect effect")),
        (
            "graphical_or_directed_model",
            ("bayesian network", "dag", "graphical", "structural equation"),
        ),
        ("genetic_instrument", ("genetic_instrument", "mendelian", "smr", "heidi", "qtl")),
    )
    for bucket, terms in rules:
        if any(term in text for term in terms):
            return bucket
    return "other"


def round_robin(
    rows: list[dict[str, str]],
    count: int,
    seed: str,
) -> list[dict[str, str]]:
    buckets: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in stable_order(rows, seed):
        buckets[design_bucket(row)].append(row)
    selected: list[dict[str, str]] = []
    ordered_buckets = sorted(buckets, key=lambda item: (len(buckets[item]), item))
    while len(selected) < count and ordered_buckets:
        remaining = []
        for bucket in ordered_buckets:
            if buckets[bucket] and len(selected) < count:
                selected.append(buckets[bucket].pop(0))
            if buckets[bucket]:
                remaining.append(bucket)
        ordered_buckets = remaining
    return selected


def unique_extend(
    selected: list[dict[str, str]],
    candidates: list[dict[str, str]],
    count: int,
) -> None:
    seen = {row.get("canonical_id") for row in selected}
    for row in candidates:
        if len(selected) >= count:
            return
        if row.get("canonical_id") not in seen:
            selected.append(row)
            seen.add(row.get("canonical_id"))


def build_high_signal(rows: list[dict[str, str]], seed: str) -> list[dict[str, str]]:
    eligible = [
        row
        for row in rows
        if normalized_text(row.get("title", ""))
        and normalized_text(row.get("abstract", ""))
    ]
    selected: list[dict[str, str]] = []
    groups = [
        [
            row
            for row in eligible
            if row.get("final_study_label") == "causal_hypothesis"
        ],
        [
            row
            for row in eligible
            if row.get("title_abstract_decision") == "exclude"
        ],
        [
            row
            for row in eligible
            if row.get("final_study_label") == "causal_evidence"
            and design_bucket(row) != "genetic_instrument"
        ],
        [
            row
            for row in eligible
            if row.get("title_abstract_decision") in {"pending", "seek_full_text"}
            and len(row.get("abstract", "")) < 500
        ],
        [
            row
            for row in eligible
            if any(
                term in (row.get("title", "") + " " + row.get("abstract", "")).lower()
                for term in ("colocal", "bayesian network", "mediation", "randomized", "randomised")
            )
        ],
    ]
    for index, group in enumerate(groups):
        target = (index + 1) * 5
        unique_extend(selected, stable_order(group, f"{seed}-high-{index}"), target)
    if len(selected) < 25:
        unique_extend(selected, stable_order(eligible, f"{seed}-high-fill"), 25)
    return [dict(row) for row in selected[:25]]


def build_regression(rows: list[dict[str, str]], seed: str) -> list[dict[str, str]]:
    selected: list[dict[str, str]] = []
    positive_pool = [
        row
        for row in rows
        if row.get("final_study_label") in {"causal_evidence", "causal_hypothesis"}
        or row.get("title_abstract_decision") == "seek_full_text"
    ]
    positives = [
        dict(row) for row in round_robin(positive_pool, 42, f"{seed}-positive")
    ]
    for row in positives:
        row["_sampling_stratum"] = "candidate_levels_2_to_4"
    selected.extend(positives)

    exclusion_pool = [
        row
        for row in rows
        if row.get("title_abstract_decision") == "exclude"
        or row.get("final_study_label") in {"context_only", "associational"}
    ]
    exclusions = [dict(row) for row in stable_order(exclusion_pool, f"{seed}-exclude")]
    for row in exclusions:
        row["_sampling_stratum"] = "candidate_exclusion"
    unique_extend(selected, exclusions, 84)

    boundary_pool = [
        row
        for row in rows
        if row.get("canonical_id") not in {item.get("canonical_id") for item in selected}
        and (
            row.get("title_abstract_decision") == "pending"
            or len(row.get("abstract", "")) < 700
            or any(
                term in (row.get("title", "") + " " + row.get("abstract", "")).lower()
                for term in ("colocal", "network", "mediation", "causal", "multi-omic")
            )
        )
    ]
    boundaries = [
        dict(row) for row in round_robin(boundary_pool, 32, f"{seed}-boundary")
    ]
    for row in boundaries:
        row["_sampling_stratum"] = "candidate_boundary_or_unclear"
    unique_extend(selected, boundaries, 116)
    if len(selected) != 116:
        raise ValueError(f"Could not build 116 regression candidates; selected {len(selected)}")
    return selected


def build_full_text(rows: list[dict[str, str]], seed: str) -> list[dict[str, str]]:
    assessed = [
        row
        for row in rows
        if row.get("full_text_status") == "retrieved"
        and row.get("final_study_label") != "pending"
    ]
    quotas = {"0": 2, "1": 2, "2": 11, "3": 22, "4": 23}
    selected: list[dict[str, str]] = []
    for level, count in quotas.items():
        group = [row for row in assessed if row.get("causal_evidence_level") == level]
        chosen = [
            dict(row)
            for row in round_robin(group, count, f"{seed}-level-{level}")
        ]
        for row in chosen:
            row["_sampling_stratum"] = f"prior_level_{level}"
        selected.extend(chosen)
    if len(selected) != 60:
        raise ValueError(f"Could not build 60 full-text candidates; selected {len(selected)}")
    return selected


def title_row(row: dict[str, str]) -> dict[str, Any]:
    values = {
        "canonical_id": row.get("canonical_id", ""),
        "title": normalized_text(row.get("title", "")),
        "abstract": normalized_text(row.get("abstract", "")),
        "year": row.get("year", ""),
        "doi": row.get("doi", ""),
        "pmid": row.get("pmid", ""),
        "lanes": row.get("lanes", ""),
        "sampling_stratum": row.get("_sampling_stratum", "high_signal_development"),
        "prior_title_abstract_decision": row.get("title_abstract_decision", ""),
        "prior_title_abstract_exclusion_reason": row.get("title_abstract_exclusion_reason", ""),
        "prior_final_study_label": row.get("final_study_label", ""),
        "prior_causal_evidence_level": row.get("causal_evidence_level", ""),
    }
    return {field: values.get(field, "") for field in TITLE_FIELDS}


def full_text_row(row: dict[str, str]) -> dict[str, Any]:
    values = title_row(row)
    values.update(
        {
            "full_text_status": row.get("full_text_status", ""),
            "full_text_location": row.get("full_text_location", ""),
            "prior_identification_source": row.get("identification_source", ""),
        }
    )
    return {field: values.get(field, "") for field in FULL_TEXT_FIELDS}


def write_csv(path: Path, fields: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build annotation-pending prompt benchmark candidates"
    )
    parser.add_argument("ledger", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--seed", default="causal-multiomics-benchmark-v0.1.0")
    args = parser.parse_args()

    rows = read_ledger(args.ledger)
    high_signal = build_high_signal(rows, args.seed)
    regression = build_regression(rows, args.seed)
    full_text = build_full_text(rows, args.seed)
    section_gold = round_robin(full_text, 20, f"{args.seed}-section-gold")

    high_signal_path = args.output_dir / "high_signal_development_25.csv"
    regression_path = args.output_dir / "title_abstract_regression_116.csv"
    full_text_path = args.output_dir / "full_text_benchmark_60.csv"
    section_gold_path = args.output_dir / "section_selector_gold_20.csv"

    write_csv(
        high_signal_path,
        TITLE_FIELDS,
        [title_row(row) for row in high_signal],
    )
    write_csv(
        regression_path,
        TITLE_FIELDS,
        [title_row(row) for row in regression],
    )
    write_csv(
        full_text_path,
        FULL_TEXT_FIELDS,
        [full_text_row(row) for row in full_text],
    )
    write_csv(
        section_gold_path,
        FULL_TEXT_FIELDS,
        [full_text_row(row) for row in section_gold],
    )
    write_manifest(
        args.output_dir / "manifest.json",
        {
            "benchmark_version": "candidate_sets_v0.1.1",
            "status": "annotation_pending",
            "input_file": args.ledger.name,
            "input_sha256": sha256_file(args.ledger),
            "seed": args.seed,
            "development_set_eligibility": "nonempty_title_and_abstract",
            "counts": {
                "high_signal_development": len(high_signal),
                "title_abstract_regression": len(regression),
                "full_text_benchmark": len(full_text),
                "section_selector_gold": len(section_gold),
            },
            "output_sha256": {
                high_signal_path.name: sha256_file(high_signal_path),
                regression_path.name: sha256_file(regression_path),
                full_text_path.name: sha256_file(full_text_path),
                section_gold_path.name: sha256_file(section_gold_path),
            },
            "ground_truth_policy": (
                "Existing decisions are sampling hints only; expert fields require "
                "fresh annotation."
            ),
        },
    )


if __name__ == "__main__":
    main()
