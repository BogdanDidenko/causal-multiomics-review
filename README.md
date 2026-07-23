# Causal Multi-omics Review

Reproducible PRISMA-oriented pipeline for a scoping review of biological and
health studies that integrate multiple omics layers and make causal claims.

This repository reuses the methodological architecture of
[`BogdanDidenko/text-bio-fundational-models-review`](https://github.com/BogdanDidenko/text-bio-fundational-models-review):
database-native searches, conservative deduplication, criterion-level LLM
screening, deterministic gates, conflict adjudication, repeated-run checks,
and a complete audit trail. The review question, eligibility rules, search
queries, schemas, and prompts are new and specific to causal multi-omics.

## Review Question

Which empirical multi-omics studies support a biological causal claim, and
what provides identification: a randomized or non-randomized intervention,
direct perturbation, genetic instrument, temporal design, formal mediation,
or a graphical/directed model?

The retrieval strategy does not require the exact phrases `causal inference`
or `causal discovery`. It searches for design-specific causal anchors.

## Pipeline

```mermaid
flowchart LR
  A["Protocol and database-native queries"] --> B["Raw source exports"]
  B --> C["Normalization and provenance"]
  C --> D["Conservative deduplication"]
  D --> E["Scope reviewer"]
  D --> F["Causal-design reviewer"]
  E --> G["Deterministic criterion gates"]
  F --> G
  G -->|"conflict or unclear"| H["Adjudicator"]
  G -->|"concordant"| I["Title/abstract decision"]
  H --> I
  I --> J["Full-text eligibility"]
  J --> K["Causal assumptions and evidence level"]
  K --> L["PRISMA flow and synthesis"]
```

An LLM never emits the final inclusion decision directly. Reviewers return
criterion-level JSON; Python applies versioned rules. Unclear evidence is
retained for adjudication or full-text review.

## Repository Layout

- `protocol/`: review question, eligibility criteria, PRISMA process, exact
  database queries, agent prompts, schemas, and gate configuration.
- `src/causal_multiomics_review/`: reusable normalization, deduplication,
  screening gates, and audit utilities.
- `scripts/`: command-line entry points for validation, deduplication,
  screening, and replicate comparison.
- `tests/`: regression tests for deterministic pipeline behavior.
- `data/`: local pipeline stages; generated study data are ignored by Git.
- `runs/`: immutable run manifests and summaries; large/raw outputs are
  ignored unless deliberately curated.
- `docs/reference-repo-audit.md`: detailed reuse analysis of the source repo.

## Quick Start

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
python scripts/validate_protocol.py
pytest
```

Deduplicate a normalized CSV:

```bash
python scripts/deduplicate.py input.csv data/normalized/canonical.csv \
  --log data/normalized/deduplication_log.csv
```

Run the active title/abstract prompt suite with an OpenAI-compatible endpoint:

```bash
export OPENAI_API_KEY=...
python scripts/run_screening.py data/normalized/canonical.csv runs/pilot-001 \
  --stage title_abstract
```

Full-text screening accepts JSONL records with a `sections` array containing
stable `section_id`, `heading`, and `text` fields:

```bash
python scripts/run_screening.py full_text_records.jsonl runs/fulltext-pilot-001 \
  --stage full_text --resume
```

The active suite is declared in
`protocol/screening/configs/prompt_suite_v0.3.0.json`; exact prompt/schema
hashes are in `protocol/screening/prompt_manifest.json`.

The active suite runs every agent with `gpt-5.6-luna` at medium reasoning
effort. Establish stability before deployment with five independent repeats:

```bash
python scripts/run_stability.py data/normalized/canonical.csv runs/stability-title \
  --stage title_abstract
```

API keys are read only from environment variables. The local helper
`academic-api-env` can load the academic database credentials already stored
in macOS Keychain; no key belongs in this repository.

Probe current database counts without committing credentials:

```bash
eval "$(academic-api-env)"
python scripts/probe_searches.py runs/search-calibration
```

## Current Status

The protocol, calibrated query pack, seven-prompt suite, config-driven
gates, benchmark candidate sets, audit utilities, tests, and CI are
initialized. Prompts remain `draft_pending_stability_and_benchmark` until the
five-run stability gate and expert benchmark acceptance gates pass. Search
counts from 2026-07-18 are calibration evidence, not final PRISMA counts.

## License

MIT. See `LICENSE`.
