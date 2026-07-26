# Prompt Benchmark Protocol

The files under `candidates/` are deterministic, annotation-pending samples
from the 1,620-record causal multi-omics ledger. Prior decisions are retained
only as sampling provenance. They are not ground truth.

## Candidate Sets

- `high_signal_development_25.csv`: prompt iteration only; every record has a
  nonempty title and abstract so the zero-manual-review stability gate tests
  model behavior rather than metadata availability. Never report final
  performance on this set.
- `title_abstract_regression_116.csv`: 42 candidate Levels 2-4, 42 candidate
  exclusions, and 32 boundary/unclear records.
- `full_text_benchmark_60.csv`: all available prior Levels 0-2 plus balanced
  samples of Levels 3-4 and rare design families.
- `section_selector_gold_20.csv`: subset for expert section-ID annotation.

## Expert Annotation

One domain expert re-annotates every record from the evidence supplied at the
relevant stage. Existing decision columns must remain hidden during annotation.
The expert records criterion values, evidence, uncertainty, exclusion code,
design family, and evidence level using the operative codebook. Canonical
positive controls are marked `yes` in `expert_canonical_positive`; this field
is part of the expert annotation and is never inferred from prior decisions.

After at least seven days, the expert blindly re-annotates a deterministic 20%
subset. Report exact agreement and weighted agreement before reconciling the
two passes. Reconciled expert fields become benchmark version `v1.0.0`.

## Acceptance Gates

Title/abstract:

- canonical positive retention: 100%;
- sensitivity for expert Levels 2-4: at least 0.98;
- direct-exclusion precision: at least 0.95;
- valid structured response after one retry: 100%.

Full text:

- eligibility sensitivity: at least 0.95;
- design-family macro-F1: at least 0.85;
- exact evidence-level agreement: at least 0.80;
- quadratic weighted kappa: at least 0.80;
- agreement within one evidence level: at least 0.95;
- unknown or unsupported section citations: zero.

The prompt manifest remains `draft_pending_stability_and_benchmark` until these
gates and the stability gate pass.
Prompt changes after looking at regression outcomes require a new prompt
version and a fresh held-out benchmark.

Run `scripts/evaluate_prompt_benchmark.py` after annotation and screening. Its
`acceptance` object reports each threshold and an overall `pass`, `fail`, or
`not_evaluable` status; blank expert fields intentionally remain not evaluable.

## Stability Gate

All seven agent roles use `gpt-5.6-terra` with medium reasoning effort. Run the
same frozen input five times with `scripts/run_stability.py`. Acceptance is
100% schema success, exact agreement for final decision, decisive criteria, and
full-text evidence level, plus a zero manual-review rate. The evaluator ignores
free-text rationale wording but reports every disagreed criterion path. A failed
gate means the task boundary or prompt is still under-specified: revise the
next prompt version, then repeat the frozen evaluation.
