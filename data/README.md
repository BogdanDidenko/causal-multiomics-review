# Data Stages

Generated records are excluded from Git by default.

- `raw/`: source-native responses and exports, one immutable directory per
  database and retrieval date.
- `normalized/`: shared bibliographic schema, provenance, deduplication logs,
  and canonical records.
- `screening/`: title/abstract and full-text ledgers.

Every formal run must preserve query text/hash, retrieval timestamp, source
count, pagination state, software revision, and normalization errors. Commit
small manifests and summaries; store large corpora in versioned external
storage when needed.
