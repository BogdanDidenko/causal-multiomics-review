# Screening Contracts

The unversioned prompt files and `gate_config.json` are the immutable legacy
`v0.1.0` title/abstract contract. They remain available for reproduction.

The active suite is `configs/prompt_suite_v0.11.0.json`:

- title/abstract prompts are version `0.7.0`;
- full-text prompts are version `0.2.0`;
- every active agent uses isolated `codex exec` calls with `gpt-5.6-terra` and
  medium reasoning effort; the runs are ephemeral, read-only, and ignore local
  Codex configuration and project rules; a temporary authentication-only Codex
  home prevents global skills, plugins, and MCP servers from entering calls;
- explicit criterion-level exclusions take precedence over unrelated
  `unclear` fields; the immutable legacy gate retains its original precedence;
- `prompt_manifest.json` records exact prompt, schema, and config hashes;
- schemas use JSON Schema Draft 2020-12 and permit nested evidence objects.

Round A runs `scope_reviewer` and `causal_design_reviewer` independently. A
record advances directly only when both gates return `include`. Any `exclude`,
`unclear`, parse failure, or missing required field is sent to adjudication in
the sensitivity-oriented default configuration. The adjudicator returns a
consolidated criterion record; Python then emits `seek_full_text`, `exclude`,
or `manual_review`.

Prompts use `{{RECORD_ID}}`, `{{TITLE}}`, `{{ABSTRACT}}`, `{{YEAR}}`, and
`{{SOURCE}}`. The runner stores prompt/schema hashes and raw responses.

At full text, a section selector chooses stable section IDs before independent
eligibility and causal-evidence reviewers run. Python validates every cited
section ID, adjudicates conflicts, derives evidence Levels 0-4, and writes the
existing ledger-compatible fields.

Invalid JSON is retried once. A second failure, missing abstract, insufficient
full text, invalid section citation, or decisive uncertainty becomes
`manual_review`; records are never silently dropped. `--resume` skips completed
record IDs and appends new checkpointed outputs.

The annotation-pending benchmark candidates and acceptance gates are under
`benchmarks/`. Run `scripts/run_stability.py` before any deployment: it makes
five independent calls per record and writes the exact disagreeing criterion
paths. The active prompts are not approved production classifiers until both
the stability gate and expert benchmark pass and the manifest status is updated.
