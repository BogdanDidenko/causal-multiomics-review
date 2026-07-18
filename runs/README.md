# Run Registry

Use one immutable directory per execution, for example
`runs/2026-07-18-screening-pilot-001/`. A run manifest must identify the Git
commit, model/provider, decoding settings, prompt and schema hashes, input
hash, evidence mode, start/end time, errors, and record counts.

Never edit an earlier run to incorporate a later search or screening batch.
Create a successor run and document the relationship.
