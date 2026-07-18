# Database-Native Queries

These are the exact calibrated expressions for protocol version `0.1.0`.
They are intentionally different because each database supports different
fields, operators, proximity syntax, publication filters, and API behavior.

| Source | Important implementation constraint |
|---|---|
| PubMed | Uses `[tiab]`, publication types, date/language fields, and documented proximity. |
| Scopus | Title-anchors multi-omics for precision; causal design uses `TITLE-ABS-KEY` and `W/n`. |
| Europe PMC | Expands every term into `TITLE:`/`ABSTRACT:` to avoid uncontrolled full-text matches. |
| Semantic Scholar | Bulk API uses `+` for AND and `|` for OR; page order is not relevance-ranked. |
| Springer Nature | Accessible Meta API plan supports keyword/Boolean/date/type but not premium title/abstract fields. |
| OpenAlex | Uses two strict `title.search` filters because broad search produced full-text false positives. |
| Google Scholar | Manual supplementary query; no official reproducible API. |

Calibration counts in `../search_config.json` were measured at
2026-07-18T11:01:44Z. They are not final PRISMA denominators. See
`../../docs/search_calibration.md` for the interpretation and sampling audit.

Official syntax references:

- [PubMed help](https://pubmed.ncbi.nlm.nih.gov/help/)
- [Scopus Search API](https://dev.elsevier.com/documentation/SCOPUSSearchAPI.wadl)
- [Semantic Scholar Academic Graph API](https://api.semanticscholar.org/api-docs/)
- [Springer Nature advanced queries](https://dev.springernature.com/docs/advanced-querying/complex-queries-boolean-ops/)
- [Europe PMC web services](https://europepmc.org/RestfulWebService)
- [OpenAlex filtering](https://developers.openalex.org/guides/filtering)
- [Google Scholar search help](https://scholar.google.com/intl/us/scholar/help.html)
