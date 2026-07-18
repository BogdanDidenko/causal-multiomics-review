# PRISMA Protocol

**Protocol version:** 0.1.0  
**Initialized:** 2026-07-18  
**Search window:** 2018-01-01 through the execution date  
**Review type:** scoping review

## Identification

Run one documented, database-native query in PubMed, Scopus, Europe PMC,
Semantic Scholar, Springer Nature, OpenAlex, and Google Scholar. Google Scholar
is a manual supplementary source because it has no official reproducible API.
Record source counts separately and preserve raw responses before any local
validation.

The 2026-07-18 calibration counts are not final PRISMA counts. Formal counts
begin only when all enabled sources are executed into one frozen run manifest.

## Normalization and Deduplication

Normalize source fields while retaining original records and provenance.
Collapse exact DOI, PMID, arXiv identifier, and normalized title/year matches.
Link preprint/published pairs conservatively and keep all merge decisions in a
deduplication log. Choose the longest available abstract for screening.

## Selection

1. Validate a benchmark and prompts before full-corpus screening.
2. Run two independent criterion reviewers on title and abstract.
3. Apply deterministic gates and selectively adjudicate uncertainty/conflict.
4. Retrieve full text for retained or unresolved reports.
5. Apply eligibility criteria and assess causal assumptions at full text.
6. Link multiple reports from the same study before synthesis.

## Audit Requirements

For each run preserve the Git revision, input hash, query/prompt/schema/gate
hashes, model/provider, decoding settings, evidence mode, timestamps, raw model
outputs, parse errors, criterion decisions, gate results, adjudication reason,
final decision, exclusion code, and human overrides.

## Amendments

Every change to scope, query, date, criterion, prompt, schema, gate, benchmark,
or model must create a dated amendment. Never edit an executed run's manifest
or denominator in place.
