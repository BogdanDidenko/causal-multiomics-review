# Title/Abstract Stability Calibration Report

Date: 2026-07-26

Model/runtime: `gpt-5.6-terra`, reasoning effort `medium`, Codex CLI
`0.145.0`, isolated home, five independent runs.

## Anti-overfitting boundary

Prompt changes used only `high_signal_development_25.csv` and targeted subsets
derived from it. The sealed
`title_abstract_stability_holdout_25.csv` was generated before the final
calibration rounds, is disjoint from development-25, regression-116, and
full-text-60, and has SHA-256
`ce97ec41681bc9efa2833eaa7942700bd374bdc3070a1b22e924ac9f0e41e947`.
Its records and record-level outputs were not inspected, and the suite was not
run against it because the development gate did not pass.

## Results

| Suite | Evaluation set | Exact decisive criteria | Final decision | Schema | Manual review | Status |
|---|---|---:|---:|---:|---:|---|
| 0.11.0 | targeted 7 | 28.6% | 100% | 100% | 0% | fail |
| 0.12.0 | targeted 5 | 80.0% | 100% | 100% | 0% | fail |
| 0.13.0 | targeted 1 | 100% | 100% | 100% | 0% | pass |
| 0.13.0 | development 25 | 68.0% | 100% | 100% | 0% | fail |
| 0.14.0 | targeted 8 | 87.5% | 100% | 100% | 0% | fail |
| 0.15.0 | targeted 8 | 75.0% | 100% | 100% | 0% | fail |

The full `0.13.0` development run produced the same route counts in all five
runs: 9 exclusions and 16 records seeking full text. Eight records still
varied in at least one audited criterion.

## Failure analysis

Generalized decision tables stabilized the original integration-mode,
editorial applicability, randomization, and multiple-design-family boundaries.
The remaining instability moved among fields that combine several semantic
questions:

- whether a validation experiment is a primary or supporting report-level
  design;
- whether an induced disease model is itself an intervention;
- whether mechanistic "mediated by" wording denotes formal mediation;
- whether omics validation establishes joint or unclear integration;
- whether a review's proposed causal validation constitutes a causal claim;
- whether contextual or proposed methods belong in an applied design-family
  array.

Version `0.15.0` separates applied design families from contextual method
mentions. This is a cleaner contract, but repeated runs still disagreed on
integration mode and review-level causal-claim status. Adding more lexical
exceptions to the same development records would risk overfitting without
demonstrating generalization.

## Decision

The prompt suite remains `draft_pending_stability_and_benchmark`. The sealed
holdout is preserved for a future architecture-level candidate. The next
iteration should change the task decomposition rather than add examples:

1. split compound profile fields into smaller binary or ternary criterion
   contracts;
2. distinguish applied, supporting, and mentioned designs structurally;
3. apply deterministic Python consistency rules only to logical dependencies,
   while retaining raw model outputs in the audit trail;
4. calibrate the revised architecture on development data, freeze it, and then
   evaluate the sealed holdout exactly once.
