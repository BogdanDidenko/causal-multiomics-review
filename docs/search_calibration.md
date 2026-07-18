# Search Calibration

## Live Count Probe

The exact queries in `protocol/queries/` were executed at
2026-07-18T11:01:44Z using the documented official API routes.

| Source | Count | Intended role |
|---|---:|---|
| PubMed | 1,705 | Primary biomedical index |
| Scopus | 1,129 | Primary multidisciplinary citation index |
| Europe PMC | 1,793 | Primary biomedical and preprint index |
| Semantic Scholar | 1,907 | Supplementary recall source |
| Springer Nature Meta | 391 | Supplementary publisher source |
| OpenAlex | 298 | Supplementary high-precision source |
| Google Scholar | Manual | Supplementary manual pass |

Counts can change while the date-bounded expression remains unchanged because
databases index, correct, merge, or reclassify records. A formal PRISMA search
must freeze raw pages and counts in one dated execution rather than reuse this
probe table.

## Precision/Recall Calibration Decisions

- PubMed and Europe PMC preserve broad title/abstract recall and produced
  overlapping but non-identical pools. They are primary sources.
- Scopus was tightened from two broad `TITLE-ABS-KEY` concept blocks to a
  title-anchored multi-omics block. The broad form returned 2,582 records with
  many context mentions; the calibrated form returned about 1.1k and showed
  materially better title-level topical precision.
- Semantic Scholar uses its Boolean bulk endpoint. It is useful for recall, but
  page order is not relevance-ranked and every record requires local
  title/abstract validation.
- Springer Nature's accessible Meta API searches more broadly than title and
  abstract. Premium-only field constraints were not used. Returned metadata
  therefore requires local validation before merge.
- OpenAlex's broad search across title, abstract, and full text returned 37,010
  records with many review/context matches. Two strict `title.search` filters
  reduced the calibrated pool to about 300 and retained direct MR,
  Perturb-seq, trial, and Bayesian-network examples. It is a high-precision
  supplementary path, not the primary recall source.
- Google Scholar has no official reproducible API. Record the exact manual
  query, year UI, date, result range examined, and exported citations.

## Remaining Calibration Work

Before freezing the formal search, draw a shared stratified sample from every
source and label it with one title/abstract codebook. Report apparent precision
by source and design family, cross-source unique yield, benchmark recall, and
the contribution of records found only through each supplementary source.
