# Methodology

## Design

Scoping review with a reproducible PRISMA-S identification process and staged
AI-assisted screening. The unit of retrieval is a bibliographic record; the
unit of inclusion is an eligible empirical report, linked to its study where
multiple reports describe the same experiment.

## Core Principles

1. Search by identification design, not only by words such as `causal`.
2. Preserve source-native queries, responses, counts, dates, and pagination.
3. Deduplicate conservatively after all source exports are frozen.
4. Ask reviewers for criterion judgments and evidence, never a bare label.
5. Apply inclusion/exclusion rules in deterministic code.
6. Escalate disagreement and `unclear`; optimize title/abstract screening for
   sensitivity.
7. Treat full text as mandatory for causal assumptions and evidence level.
8. Version prompts, schemas, gates, models, and decoding settings.
9. Measure both accuracy on a human benchmark and stability across repeats.
10. Report search calibration separately from formal PRISMA execution.

## Screening Topology

Round A runs two independent roles against the same title/abstract:

- `scope_reviewer`: empirical status, biological/health scope, actual
  multi-omics measurement or integration, and report-level exclusions.
- `causal_design_reviewer`: identification source, intervention/estimand
  evidence, assumptions visible in the abstract, and causal-design status.

Each role returns strict JSON. The gate maps each role to `include`, `exclude`,
or `unclear`. Concordant includes proceed to full-text retrieval; concordant
exclusions receive a controlled reason. Any uncertainty, schema failure, or
cross-role conflict goes to the adjudicator. The adjudicator resolves criteria,
not the final label; the same deterministic gate is applied again.

## Calibration Gate Before Deployment

Build a human-adjudicated benchmark containing:

- clear empirical multi-omics causal positives across each design family;
- reviews, protocols, resources, and method-only records;
- single-omics and parallel-omics-without-integration negatives;
- causal wording without identification;
- prediction/association papers;
- RCTs where molecular mediation is not identified;
- directed-model papers with and without an assessable causal argument;
- abstracts with insufficient detail that should remain `unclear`.

Required deployment checks are benchmark recall, per-criterion error analysis,
adjudication-trigger correctness, exclusion-reason validity, and repeat-run
agreement. Numerical thresholds must be declared before evaluating the held-out
deployment benchmark.

## Full-Text Assessment

Full text uses a section-aware two-pass workflow. A selector first identifies
Methods, Results, diagnostics, validation, and limitations sections by stable
section ID. Independent eligibility and causal-evidence reviewers then record
measured/integrated omics layers, population/model, exposure or intervention,
outcome, causal estimand, identification assumptions, sensitivity analyses,
replication/validation, and study-report linkage. A full-text adjudicator
resolves conflicts; Python derives the evidence level.

The evidence rubric is:

| Level | Interpretation |
|---|---|
| 0 | Context/method only or no empirical multi-omics integration. |
| 1 | Association or prediction without causal identification. |
| 2 | Directed/mechanistic hypothesis without an independent identification design. |
| 3 | Causal effect conditional on explicit design assumptions. |
| 4 | Level 3 plus replication, colocalization, orthogonal perturbation, or independent validation. |

An RCT identifies the randomized treatment contrast, not automatically a
molecular mediator. A DAG, pathway, or causal-discovery output is not causal
evidence without an identification argument and relevant assumptions.

Levels 2-4 enter the main scoping synthesis. Levels 0-1 remain in the audit as
context or exclusions. Colocalization is supporting validation rather than a
standalone identification design, and model-system perturbation is not assumed
to validate a population-level human effect.

## Model Dependence

Prompt regression uses three DeepSeek repeats and two GPT-OSS repeats. Full
deployment uses two runs each from DeepSeek V4 Flash, GPT-OSS 120B, and Nemotron
3 Super 120B. Only six-run unanimous exclusions with the same controlled code
are automatically excluded; any uncertainty or disagreement proceeds to full
text. This policy follows the observed model dependence in the reference
review, where cross-model disagreement was materially larger than simple
within-run label noise.
