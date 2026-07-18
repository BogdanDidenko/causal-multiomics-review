# Reference Repository Audit

## Scope

Reference: [`BogdanDidenko/text-bio-fundational-models-review`](https://github.com/BogdanDidenko/text-bio-fundational-models-review),
audited at commit `75e51c21` (2026-07-09).

The repository contains 4,489 tree entries and roughly 680 MB of tracked
content. Most entries are data and historical analysis artifacts rather than
pipeline source: `data/` accounts for 3,874 entries and `analysis/` for 468;
`scripts/`, `runs/`, and `protocol/` contain 56, 51, and 37 entries.

## Reuse Decision Matrix

| Component | Decision | Reason / adaptation |
|---|---|---|
| PRISMA-S protocol and immutable search artifacts | Reuse method | Essential for reproducibility; replace review question, dates, sources, and queries. |
| Database-specific query translation | Reuse pattern | Keep one canonical query per database and source-specific caveats; use causal-design anchors. |
| Raw -> normalize -> deduplicate -> enrich -> screen stages | Reuse | Stable review pipeline topology. |
| Exact DOI/PMID/arXiv/title deduplication | Reuse core | Conservative and auditable; extend with provenance and preprint/published review flags. |
| Longest-abstract representative selection | Reuse | Prevents a weaker source record from degrading screening evidence. |
| Two independent criterion reviewers | Reuse topology | Separates broad eligibility from technical causal-design assessment. |
| Criterion-level `yes/no/unclear` JSON | Reuse | Makes LLM output inspectable and permits deterministic gating. |
| Python gate and selective adjudication | Reuse topology | The model does not issue the final inclusion label; only conflicts/uncertainty escalate. |
| External prompt templates and exact runtime copies | Reuse | Supports versioning, hashing, regression, and reporting. |
| Repeat-run agreement analysis | Reuse | Needed because LLM screening is nondeterministic. |
| Full-text section extraction and audit | Reuse pattern | Useful after title/abstract screening; causal assumptions require full text. |
| Existing search corpus and historical runs | Do not reuse | They describe a different review and would corrupt PRISMA denominators. |
| `must_find` text-bio models | Do not reuse | Topic-specific recall anchors. New benchmark needs causal multi-omics positives and hard negatives. |
| Text/language bridge criteria | Replace | No relevance to the new review. |
| Generative/foundation-model criteria | Replace | No relevance to the new review. |
| Rule-based keyword baseline | Replace | Original pattern groups encode text-bio and model-architecture vocabulary. |
| Hard-coded run paths/model names | Replace | They prevent portability and clean replication. |
| Hard-coded response schemas and gate functions | Replace architecture | New engine reads role fields and gate criteria from versioned JSON. |
| Tracked large raw/full-text artifacts | Do not copy | Keep manifests and checksums in Git; use external storage for large corpora. |

## Findings From Repository History

The source repository's commit history shows which practices were learned by
failure and should be baseline requirements here:

1. Absolute paths were removed only after a portability audit. This repository
   uses relative in-repo references from the first commit.
2. Prompts were externalized after the initial runner. Here prompt files are
   canonical artifacts and are hashed into every run manifest.
3. A one-shot single-agent classifier was deprecated in favor of
   criterion-level screening. This repository does not provide a one-shot
   final-label path.
4. Foundation-model evidence was removed as a gate after calibration. This
   confirms that retrieval/screening criteria must be benchmarked rather than
   treated as self-evident.
5. Evidence modes and full-text audit logging were late additions. They are
   explicit pipeline stages here.
6. Search wording variants (`multi-omics`, `multi omics`, `multiomics`) changed
   recall materially. The new query pack preserves spelling/proximity variants
   and source-native syntax.

## Engineering Gaps Not Carried Forward

The reference repo has no package-level dependency contract, automated test
suite, or CI workflow. Several analysis scripts hard-code input paths, model
names, run registries, field lists, and exclusion rules. Data and code are also
interleaved at a scale that makes cloning expensive.

This repository therefore adds:

- a `src/` package with dependency-free deterministic core logic;
- JSON-configured screening criteria and role schemas;
- unit tests for gates and deduplication;
- CI for linting, tests, and protocol validation;
- Git-ignored generated data with committed manifests only;
- explicit separation of search calibration counts from frozen PRISMA counts.

## New Task Boundary

The new review includes primary empirical biological/health studies that
measure or jointly integrate at least two omics layers and permit assessment of
a causal biological claim. Causal relevance is design-based, not phrase-based.
Eligible design families include genetic instruments, randomized and
non-randomized interventions, direct perturbations, temporal designs, formal
mediation, and directed models when an identification argument can be assessed.

Reviews, protocols, resources, method-only papers, single-omics studies, and
association/prediction studies without an assessable causal design remain
useful calibration or context records but are not empirical causal-evidence
inclusions.
